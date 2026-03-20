# Persistence & Robust Device Discovery

**Date:** 2026-03-19
**Status:** Draft

## Problem

Every app restart requires full device discovery (blocking startup), loses the active effect state, and resets latency measurements. The user must reconfigure everything from scratch each time.

## Goals

1. **Instant startup** — load previously registered devices, scene, effect state from persistent storage; never block on discovery
2. **Background discovery** — multi-wave subnet-wide scanning finds every device without missing any
3. **Offline device handling** — registered devices show as offline and reconnect automatically
4. **Single source of truth** — all state lives in SQLite; TOML is an import/export format only
5. **Auto-save** — state changes persist automatically (debounced where appropriate)

## Non-Goals

- Cloud sync or multi-instance state sharing
- Device firmware updates or OTA
- Historical latency analytics (only last-known value persisted)

---

## Architecture

### State Store: SQLite (`state.db`)

Single file alongside the project root (same directory as current `config.toml`). Replaces `config.toml` and `presets.toml` as the runtime source of truth. WAL mode enabled for concurrent reads during writes.

Uses `PRAGMA user_version` for schema versioning. On open, check version against expected; run sequential migration scripts (plain SQL) to bring schema up to date. Initial version = 1.

#### Schema

```sql
-- Engine/network/web/discovery settings (key-value, grouped by section)
config (
    section TEXT NOT NULL,        -- "engine", "network", "web", "devices.openrgb", "discovery", etc.
    key TEXT NOT NULL,
    value TEXT NOT NULL,           -- JSON-encoded value
    PRIMARY KEY (section, key)
)

-- Registered devices. PK is a stable composite identity, not the display name.
devices (
    id TEXT PRIMARY KEY,           -- stable ID: "{backend}:{mac}" when MAC available,
                                   -- "{backend}:{ip}" for Govee (no MAC),
                                   -- "{backend}:{host}:{port}:{index}" for OpenRGB
    name TEXT NOT NULL,            -- display name (user-editable, not used for matching)
    backend TEXT NOT NULL,         -- "lifx", "govee", "openrgb"
    led_count INTEGER,
    ip TEXT,
    mac TEXT,                      -- NULL for backends that don't expose MAC (Govee, OpenRGB)
    sku TEXT,                      -- Govee-specific
    last_latency_ms REAL,
    last_seen TEXT,                -- ISO 8601
    extra TEXT                     -- JSON for backend-specific fields
)

-- Group metadata
groups (
    name TEXT PRIMARY KEY,
    color TEXT NOT NULL DEFAULT '#888888'  -- hex color for UI display
)

-- Device-group membership (many-to-many)
device_groups (
    group_name TEXT NOT NULL REFERENCES groups(name) ON DELETE CASCADE,
    device_id TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    PRIMARY KEY (group_name, device_id)
)

-- Active effect state per deck
effect_state (
    deck_id INTEGER PRIMARY KEY DEFAULT 1,  -- supports future multi-deck
    effect_class TEXT NOT NULL,
    params TEXT NOT NULL                     -- JSON
)

-- Presets
presets (
    name TEXT PRIMARY KEY,
    effect_class TEXT NOT NULL,
    params TEXT NOT NULL            -- JSON
)

-- Scene placements
scene_placements (
    device_id TEXT PRIMARY KEY REFERENCES devices(id) ON DELETE CASCADE,
    position_x REAL NOT NULL DEFAULT 0,
    position_y REAL NOT NULL DEFAULT 0,
    position_z REAL NOT NULL DEFAULT 0,
    geometry_type TEXT NOT NULL DEFAULT 'point',
    direction_x REAL,
    direction_y REAL,
    direction_z REAL,
    length REAL,
    width REAL,
    rows INTEGER,
    cols INTEGER
)

-- Scene-level config (single row)
scene_config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    mapping_type TEXT NOT NULL DEFAULT 'linear',
    mapping_params TEXT             -- JSON
)
```

#### Device Identity

Device names are not stable (LIFX names include IP, OpenRGB uses indices). The `devices.id` column uses a composite stable identity:

- **LIFX:** `"lifx:{mac_hex}"` — MAC is available from StateService responses
- **Govee:** `"govee:{ip}"` — Govee protocol doesn't expose MAC; IP is the best available. If IP changes, treated as a new device (user can merge manually)
- **OpenRGB:** `"openrgb:{host}:{port}:{index}"` — server-managed, stable within a server instance

`DeviceInfo` gains an optional `mac: str | None` field to surface MAC from backend-specific records to the common layer. LIFX populates it from `LifxDeviceRecord.mac`. Govee and OpenRGB leave it as `None`.

#### StateDB Class

- Owns the SQLite connection
- All writes go through `asyncio.to_thread()` (SQLite is blocking)
- Debounced writes use `asyncio.call_later()` per-table; shutdown hook flushes all pending
- Passed around via dependency injection (replaces current `config_path` on `app.state`)
- Methods: `load_config()`, `save_config_key()`, `load_devices()`, `upsert_device()`, `load_effect_state()`, `save_effect_state()`, `load_presets()`, `save_preset()`, `load_scene()`, `save_placement()`, etc.

### Auto-save Triggers

| Event | What's saved | Debounce |
|-------|-------------|----------|
| Device discovered/promoted | Device row (ip, mac, sku, led_count, last_seen) | Immediate |
| Device goes offline | last_seen timestamp | Immediate |
| Latency updated | last_latency_ms | 10s (batch via `call_later`) |
| Effect changed (swap or param tweak) | effect_state row | 2s (coalesce rapid knob turns via `call_later`) |
| Preset saved/deleted | presets row | Immediate |
| Scene placement changed | scene_placements row | Immediate |
| Config changed via API | config rows | Immediate |
| Device group changed | device_groups rows | Immediate |
| Shutdown | Flush all pending debounced writes | Immediate |

---

## Startup Flow

1. **Open `state.db`** — create with schema if missing; run migrations via `PRAGMA user_version`
2. **Migration check** — if `config.toml` and/or `presets.toml` exist and DB is fresh (version 0), auto-import them; rename originals to `.bak`
3. **Load config** — build `AppConfig` dataclasses from config table (rest of codebase works unchanged)
4. **Load devices** — create `ManagedDevice` entries with `status="offline"`, seed latency from `last_latency_ms`
5. **Load effect state** — instantiate last-used effect with its params (fallback to BeatPulse if missing/invalid). Migration from `EffectConfig` flat fields: `active_effect` → `effect_class`, `{beat_pulse_palette, beat_pulse_gamma}` → `params` JSON
6. **Load scene** — build `SceneModel` from scene_placements + scene_config
7. **App is ready** — effects render, scene works, UI shows devices as offline
8. **Launch background discovery** — multi-wave scan (see below)
9. **Launch reconnect loop** — 30s interval for remaining offline devices

---

## Device Lifecycle

### ManagedDevice Changes

`ManagedDevice` gains:
- `status: Literal["online", "offline", "reconnecting"]`
- `adapter: DeviceAdapter` — uses a `GhostAdapter` when offline instead of `None`. `GhostAdapter` is a concrete `DeviceAdapter` subclass that: provides stored `device_info`/`led_count`/`is_connected=False`, raises on `send_frame()`. This avoids null-safety refactoring across scheduler, web routers, and all code that accesses `device.adapter.*`.
- Device info always available (from ghost adapter when offline, from real adapter when online)

Scheduler skips devices where `status != "online"` (checks `adapter.is_connected`; ghost returns `False`).

### DeviceManager Changes

- `add_device(adapter_or_info, tracker, max_fps, adapter=None)` — accepts either a real adapter or DeviceInfo+GhostAdapter for offline registration
- `promote_device(id, adapter)` — swap ghost for real adapter, set status to online
- `demote_device(id)` — swap real adapter for ghost, set status to offline
- `remove_device(id)` — remove from managed list entirely
- Device list is dynamic: scheduler must handle devices being added/removed at runtime (see Scheduler section)

### Scheduler Dynamic Device Handling

The `LookaheadScheduler` currently takes a fixed device list at construction. To support promote/demote at runtime:
- Scheduler gains `add_device(managed)` and `remove_device(id)` methods
- `add_device()` creates a new `FrameSlot`, appends to `_send_counts`, and spawns a new per-device send task
- `remove_device()` cancels the device's send task and cleans up its slot
- The distributor loop iterates a mutable device collection (list with a lock, or copy-on-write)
- GhostAdapter devices are added to the scheduler but their send tasks immediately skip (is_connected=False), so no special-casing needed in the distributor

### Device Matching (for promoting offline → online)

Priority order:
1. `(backend, mac)` — stable identity across IP changes (LIFX)
2. `(backend, ip)` — fallback when MAC unavailable (Govee)
3. `(backend, name)` — last resort (OpenRGB)

---

## Robust Network Discovery

### DiscoveryOrchestrator (`devices/discovery.py`)

New class that owns the multi-wave discovery logic. Replaces the current `DeviceBackend.discover_all()` as the entry point for discovery. Individual backends retain their `discover()` methods but the orchestrator calls them.

`DeviceBackend.discover_all()` is deprecated. The orchestrator calls `backend.discover(config)` directly on each registered backend.

### Multi-wave Scanning

3 waves, ~5s apart. Each wave runs all backends in parallel via `asyncio.gather()`.

### Per-wave Pipeline

```
Wave N:
  +----- LIFX broadcast ------+
  +----- Govee multicast -----+-- collect responses (10s window)
  +----- OpenRGB TCP ----------+
  |
  +----- LIFX unicast sweep --+
  +----- Govee unicast sweep --+-- collect responses (10s window)
  |
  Deduplicate -> register new -> promote known offline
```

### Subnet-wide Unicast Probing

After each broadcast wave, send unicast probes to every IP in the subnet:

**LIFX:**
1. Broadcast GetService as before (catches responsive devices)
2. Unicast GetService to every IP in the subnet (e.g., all 254 hosts on a /24)
   - Subnet determined from `config.network.interface` + configurable mask
   - Rate-limited: ~50 concurrent UDP probes
   - 500ms timeout per probe
   - Catches devices that ignore broadcasts but respond to unicast

**Govee:**
1. Multicast scan as before
2. Unicast scan command to every IP on port 4001
   - Same rate limiting and timeout
   - Some Govee devices respond better to direct UDP than multicast

**OpenRGB:**
- No subnet scan (server-based protocol). Retry with 5s timeout.

**Subnet detection:**
```python
interface_ip = config.network.interface  # e.g., "192.168.1.100"
subnet = IPv4Network(f"{interface_ip}/{config.discovery.subnet_mask}", strict=False)
```

### Per-backend Fixes

- **LIFX:** Increase GetVersion timeout from 100ms to 500ms. Retry failed version queries once. Run broadcast 3x per wave.
- **Govee:** Handle port 4002 bind failure with retry + exponential backoff. Increase discovery window to 10s. Log warning if bind fails after retries.
- **OpenRGB:** Add explicit 5s connection timeout. Retry once on failure.

### Reconnect Loop (30s interval)

For offline devices specifically:
1. Unicast probe at last known IP (fast path)
2. If that fails after 3 consecutive cycles, back off to 2-minute interval for that device
3. Full subnet sweep only on explicit user request (`POST /api/devices/scan`), not in the reconnect loop
4. Configurable interval: `discovery.reconnect_interval_s`

### Discovery Events

- `device_discovered` — new device found (not in DB)
- `device_online` — known device reconnected
- `discovery_wave_complete` — wave N finished, N devices found
- `discovery_complete` — all waves done

### API Endpoints

- `POST /api/devices/scan` — trigger immediate full multi-wave scan (including subnet sweep)
- `POST /api/devices/scan?wave=1` — single wave (quick check)
- `DELETE /api/devices/{id}` — unregister device from DB (cascades to groups and scene_placements)
- `PUT /api/devices/{id}` — edit device metadata (rename, override LED count, etc.)

### Discovery Config (new `DiscoveryConfig` dataclass in `config.py`)

```python
@dataclass
class DiscoveryConfig:
    waves: int = 3
    wave_interval_s: float = 5.0
    unicast_concurrency: int = 50
    unicast_timeout_s: float = 0.5
    subnet_mask: int = 24
    reconnect_interval_s: float = 30.0
```

Added to `AppConfig` as `config.discovery`.

---

## TOML Import/Export

### Export

`GET /api/state/export` or CLI `--export state.toml`

Dumps entire DB into a single structured TOML file. The marshaling layer converts between DB flat columns and TOML nested structures (e.g., `position_x/y/z` columns ↔ `position = [x, y, z]` array in TOML).

```toml
[config.engine]
fps = 60
max_lookahead_ms = 1000

[config.network]
interface = "192.168.1.100"

[config.discovery]
waves = 3
subnet_mask = 24

[effect_state]
effect_class = "beat_pulse"
params = { gamma = 3.0, palette = ["#ff0000", "#0000ff"] }

[devices."lifx:D073D5XXYYZZ"]
name = "Kitchen Strip"
backend = "lifx"
led_count = 60
ip = "192.168.1.42"
mac = "D0:73:D5:XX:YY:ZZ"
last_latency_ms = 48.5

[scene.mapping]
type = "linear"

[scene.placements."lifx:D073D5XXYYZZ"]
position = [0.0, 0.0, 0.0]
geometry = "strip"
direction = [1.0, 0.0, 0.0]
length = 1.5

[groups."main-stage"]
color = "#ff6600"
devices = ["lifx:D073D5XXYYZZ"]

[presets."My Preset"]
effect_class = "beat_pulse"
params = { gamma = 2.5 }
```

### Import

`POST /api/state/import` or CLI `--import state.toml`

- Parses TOML, validates, upserts into DB
- Partial imports supported (e.g., TOML with only `[devices]` updates just devices)
- Existing data not in the import file is left untouched

### First-launch Migration

- If `state.db` missing but `config.toml` exists → auto-import as migration
  - `EffectConfig` flat fields mapped: `active_effect` → `effect_class`, `{beat_pulse_palette, beat_pulse_gamma}` → `params` JSON
  - `scene_config` dict entries mapped to `scene_placements` rows and `scene_config` row
- If `presets.toml` exists → merge into DB
- Rename originals to `.bak` after successful migration

---

## Impact on Existing Code

### Files Modified

- `config.py` — `load_config()` reads from StateDB instead of TOML; `AppConfig` gains `DiscoveryConfig` dataclass; `EffectConfig` fields retained for backward compat but populated from DB
- `types.py` — `DeviceInfo` gains `mac: str | None = None` field
- `main.py` — new startup flow (DB init → load state → background discovery → reconnect loop)
- `devices/backend.py` — `discover_all()` deprecated; individual `discover()` methods retained, called by `DiscoveryOrchestrator`
- `devices/manager.py` — `ManagedDevice` gains `status` field; add `promote_device()`/`demote_device()`; device list becomes dynamic
- `devices/lifx/transport.py` — unicast sweep, increased timeouts (100ms→500ms), broadcast retries (3x)
- `devices/lifx/discovery.py` — populate `DeviceInfo.mac` from `LifxDeviceRecord.mac`
- `devices/govee/transport.py` — unicast sweep, port 4002 bind retry with backoff (socket creation), increased window (5s→10s)
- `devices/govee/backend.py` — discovery orchestration changes to support new transport capabilities
- `devices/openrgb_backend.py` — connection timeout (5s), retry on failure
- `effects/deck.py` — auto-save effect state on swap/param change (calls StateDB)
- `effects/presets.py` — `PresetStore` backed by StateDB instead of TOML file
- `scheduling/scheduler.py` — handle dynamic device list (devices added/removed at runtime); skip devices where `adapter.is_connected == False`
- `web/app.py` — `create_app()` accepts `StateDB` instead of `config_path`; stored on `app.state`
- `web/router_config.py` — reads/writes config via StateDB
- `web/router_effects.py` — effect changes trigger auto-save to StateDB
- `web/router_scene.py` — scene changes write to StateDB; references use device `id` not `name`
- `web/router_devices.py` — null-safe access via GhostAdapter (no code change needed, ghost provides same interface)
- `events.py` — add new event types: `DeviceDiscoveredEvent`, `DeviceOnlineEvent`, `DeviceOfflineEvent`, `DiscoveryWaveCompleteEvent`, `DiscoveryCompleteEvent`

### New Files

- `persistence/state_db.py` — `StateDB` class (SQLite connection, load/save methods, debounce logic, migrations)
- `persistence/migrations/` — sequential SQL migration scripts (001_initial.sql, etc.)
- `persistence/toml_io.py` — TOML ↔ DB marshaling for import/export
- `devices/discovery.py` — `DiscoveryOrchestrator` (multi-wave scanning, subnet probing, reconnect loop)
- `devices/ghost.py` — `GhostAdapter` (offline device placeholder)

### Files Removed (after migration)

- `presets.toml` — data migrated to DB (renamed to `.bak`)
- `config.toml` — data migrated to DB (renamed to `.bak`)

### Unchanged

- `effects/` (render logic, registry, params) — no changes
- `beat/` — no changes
- `prodjlink/` — no changes
- `spatial/` — SceneModel built from DB data instead of config dict, otherwise unchanged
- Frontend — no breaking changes to existing APIs. New endpoints and device status field available for future UI integration.
