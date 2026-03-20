# Persistence & Robust Device Discovery

**Date:** 2026-03-19
**Status:** Draft

## Problem

Every app restart requires full device discovery (blocking startup), loses the active effect state, and resets latency measurements. The user must reconfigure everything from scratch each time. The system only supports a single scene — no way to define multiple rooms or run concurrent spatial layouts.

## Goals

1. **Instant startup** — load previously registered devices, scenes, effect state from persistent storage; never block on discovery
2. **Background discovery** — multi-wave subnet-wide scanning finds every device without missing any
3. **Offline device handling** — registered devices show as offline and reconnect automatically
4. **Single source of truth** — all state lives in SQLite; TOML is an import/export format only
5. **Auto-save** — state changes persist automatically (debounced where appropriate)
6. **Multiple concurrent scenes** — define and run multiple scenes simultaneously, each with independent device groups, effects, and spatial mappings

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
-- Section uses dotted paths: "engine", "network", "devices.lifx", "discovery", etc.
config (
    section TEXT NOT NULL,        -- e.g. "engine", "devices.lifx", "discovery"
    key TEXT NOT NULL,            -- e.g. "fps", "max_fps", "waves"
    value TEXT NOT NULL,           -- JSON-encoded value
    PRIMARY KEY (section, key)
)

-- Registered devices. PK is a stable composite identity, not the display name.
devices (
    id TEXT PRIMARY KEY,           -- stable ID: "{backend}:{mac_hex}" for LIFX,
                                   -- "{backend}:{device_id}" for Govee,
                                   -- "{backend}:{host}:{port}:{index}" for OpenRGB
    name TEXT NOT NULL,            -- display name (user-editable, not used for matching)
    backend TEXT NOT NULL,         -- "lifx", "govee", "openrgb"
    led_count INTEGER,
    ip TEXT,
    mac TEXT,                      -- NULL for backends that don't expose MAC
    device_id TEXT,                -- Govee hardware ID (stable across IP changes)
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

-- Scenes: named spatial configurations that can run concurrently
scenes (
    id TEXT PRIMARY KEY,           -- slug identifier (e.g. "dj-booth", "dance-floor")
    name TEXT NOT NULL,            -- display name (e.g. "DJ Booth")
    mapping_type TEXT NOT NULL DEFAULT 'linear',
    mapping_params TEXT,           -- JSON (origin, direction, etc.)
    effect_mode TEXT NOT NULL DEFAULT 'independent',  -- "independent" or "shared"
    effect_source TEXT REFERENCES scenes(id) ON DELETE SET NULL,  -- NULL for independent; scene_id for shared (max depth 1)
    is_active INTEGER NOT NULL DEFAULT 0  -- 1 if scene should run on startup
)

-- Per-scene effect state
scene_effect_state (
    scene_id TEXT PRIMARY KEY REFERENCES scenes(id) ON DELETE CASCADE,
    effect_class TEXT NOT NULL,
    params TEXT NOT NULL            -- JSON
)

-- Scene device placements (device must be registered; FK enforced)
scene_placements (
    scene_id TEXT NOT NULL REFERENCES scenes(id) ON DELETE CASCADE,
    device_id TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
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
    cols INTEGER,
    PRIMARY KEY (scene_id, device_id)
)

-- Presets
presets (
    name TEXT PRIMARY KEY,
    effect_class TEXT NOT NULL,
    params TEXT NOT NULL            -- JSON
)
```

#### Device Identity

Device names are not stable (LIFX names include IP, OpenRGB uses indices). The `devices.id` column uses a composite stable identity:

- **LIFX:** `"lifx:{mac_hex}"` — MAC is available from StateService responses
- **Govee:** `"govee:{device_id}"` — Govee protocol exposes a stable hardware `device_id` in scan responses (globally unique, survives IP changes)
- **OpenRGB:** `"openrgb:{host}:{port}:{index}"` — server-managed, stable within a server instance

`DeviceInfo` gains:
- `mac: str | None = None` — LIFX populates from `LifxDeviceRecord.mac`
- `stable_id: str | None = None` — computed stable ID, set at DeviceInfo construction

**Note:** `DeviceInfo` is `frozen=True, slots=True`. New fields use defaults so all existing positional constructors remain valid. However, both Govee adapters (`GoveeSegmentAdapter.device_info`, `GoveeSolidAdapter.device_info`) and LIFX adapters construct `DeviceInfo` as `@property` methods (computed on every access), not stored fields. The `mac`/`stable_id` kwargs must be added to the `DeviceInfo(...)` call inside each adapter's `@property`, not at adapter `__init__` time.

**Display names vs stable IDs in APIs:** All REST and WebSocket APIs use display names (`DeviceInfo.name`) in responses. Stable IDs are internal only — used for DB keys, device matching, and FK references. The web layer maps between display names and stable IDs. API routes use display names in paths (e.g., `PUT /api/scenes/{scene_id}/devices/{device_name}`).

#### Config Table Section Convention

Dotted paths map to nested `AppConfig` dataclasses:
- `section="engine"`, `key="fps"` → `config.engine.fps`
- `section="devices.lifx"`, `key="max_fps"` → `config.devices.lifx.max_fps`
- `section="discovery"`, `key="waves"` → `config.discovery.waves`

#### StateDB Class

- Owns the SQLite connection (stdlib `sqlite3` + `asyncio.to_thread()`, consistent with project's pattern for sync I/O wrapping)
- Debounced writes: `asyncio.call_later()` per-table schedules a callback that calls `loop.create_task(asyncio.to_thread(self._flush_<table>))` for the actual DB write. Shutdown hook cancels pending timers and flushes all dirty state synchronously.
- Passed around via dependency injection (replaces current `config_path` on `app.state` in `web/app.py`)
- Methods: `load_config()`, `save_config_key()`, `load_devices()`, `upsert_device()`, `load_scenes()`, `save_scene()`, `load_scene_placements()`, `save_placement()`, `load_scene_effect_state()`, `save_scene_effect_state()`, `load_presets()`, `save_preset()`, etc.

### Auto-save Triggers

| Event | What's saved | Debounce |
|-------|-------------|----------|
| Device discovered/promoted | Device row (ip, mac, device_id, sku, led_count, last_seen) | Immediate |
| Device goes offline | last_seen timestamp | Immediate |
| Latency updated | last_latency_ms | 10s (batch via `call_later`) |
| Effect changed (swap or param tweak) | scene_effect_state row | 2s (coalesce rapid knob turns via `call_later`) |
| Preset saved/deleted | presets row | Immediate |
| Scene created/updated/deleted | scenes row | Immediate |
| Scene placement changed | scene_placements row | Immediate |
| Config changed via API | config rows | Immediate |
| Device group changed | device_groups rows | Immediate |
| Scene activated/deactivated | scenes.is_active | Immediate |
| Shutdown | Flush all pending debounced writes | Immediate |

---

## Multi-Scene Architecture

### Concepts

A **scene** is a named spatial configuration: a set of device placements, a mapping type (linear/radial), and an optional effect. Scenes can run concurrently — each drives its own set of devices independently.

**Constraints:**
- A device can only belong to one active scene at a time (enforced at runtime, not DB level — allows a device to be placed in multiple scene definitions but only one can be active with that device)
- Each active scene has its own `EffectDeck` and `SpatialCompositor`
- Each active scene produces frames independently for its devices

### Effect Modes

Each scene has an `effect_mode`:
- **`independent`** — scene has its own `EffectDeck` with its own effect and parameters. Saved in `scene_effect_state`.
- **`shared`** — scene's `EffectDeck` references another scene's deck (via `effect_source` = source scene ID). Both scenes render the same effect but through their own spatial mapping/compositor. Changing the effect on the source scene changes it on the shared scene too.

### Runtime Model

```
ScenePipeline (one per active scene):
  ├── scene_id: str
  ├── deck: EffectDeck          (own or shared reference)
  ├── ring_buffer: RingBuffer   (own per scene — sized to scene's max LED count)
  ├── compositor: SpatialCompositor
  ├── devices: list[ManagedDevice]  (subset of DeviceManager's devices)
  └── mapping: LinearMapping | RadialMapping
```

**Multi-scene rendering architecture:**

The current `EffectEngine` owns a single `EffectDeck`, single `RingBuffer`, and single `led_count`. This becomes a multi-pipeline model:

- Each `ScenePipeline` owns its own `RingBuffer` (sized to that scene's `max_led_count` across its device subset, not the global max).
- `EffectEngine` gains a `pipelines: list[ScenePipeline]` and iterates them each tick.
- For each pipeline, the engine calls `deck.render(beat_phase, bar_phase, dt, led_count)` (matching the existing 4-arg signature) and writes the result to that pipeline's ring buffer.
- Shared-effect pipelines share the same `EffectDeck` reference — both call `render()` but get separate output buffers (since `led_count` may differ between scenes).
- The `LookaheadScheduler` is updated: each device's send task knows which pipeline (and thus which `RingBuffer`) to read from. The scheduler stores a `device_id → ScenePipeline` mapping, updated when scenes are activated/deactivated.
- `led_count` is no longer global. Each pipeline computes it from its device subset via `max(d.adapter.led_count for d in pipeline.devices)`.

### Scene API

- `GET /api/scenes` — list all scenes with active status
- `POST /api/scenes` — create a new scene
- `GET /api/scenes/{scene_id}` — get scene details (placements, mapping, effect)
- `PUT /api/scenes/{scene_id}` — update scene config (mapping, effect_mode, etc.)
- `DELETE /api/scenes/{scene_id}` — delete scene
- `POST /api/scenes/{scene_id}/activate` — start running this scene
- `POST /api/scenes/{scene_id}/deactivate` — stop running this scene
- `PUT /api/scenes/{scene_id}/devices/{device_name}` — add/update device placement
- `DELETE /api/scenes/{scene_id}/devices/{device_name}` — remove device from scene
- `PUT /api/scenes/{scene_id}/mapping` — update mapping type/params
- `PUT /api/scenes/{scene_id}/effect` — set effect for this scene
- `POST /api/scenes/{scene_id}/effect/share/{source_scene_id}` — share effect from another scene

### Device Conflict Resolution

Conflicts are checked at two points:

**On scene activation** (`POST /api/scenes/{scene_id}/activate`):
- If any device in the scene is already assigned to another active scene → return 409 with conflicting device list
- User must deactivate the conflicting scene or remove the device from one scene first

**On device placement in an active scene** (`PUT /api/scenes/{scene_id}/devices/{device_name}`):
- If the scene is currently active and the device is already in another active scene → return 409
- If the scene is inactive, placement is saved regardless (conflict checked at activation time)

### Shared Effect Constraints

- `effect_source` must reference an existing scene. Add `REFERENCES scenes(id) ON DELETE SET NULL` — if the source scene is deleted, shared scenes fall back to independent mode with BeatPulse defaults.
- Circular references prevented at the API level: `POST /api/scenes/{id}/effect/share/{source_id}` validates that the source scene is not itself in shared mode pointing back (direct or transitive). Max chain depth = 1 (shared scenes always point to an independent scene).

---

## Startup Flow

1. **Open `state.db`** — create with schema if missing; run migrations via `PRAGMA user_version`
2. **Migration check** — if `config.toml` and/or `presets.toml` exist and DB is fresh (version 0), auto-import them; rename originals to `.bak`. Migration from `EffectConfig` flat fields: if `active_effect == "beat_pulse"`, construct `params = {"palette": beat_pulse_palette, "gamma": beat_pulse_gamma}`; other effects use defaults. Existing `scene_config` dict parsed via `SceneModel.from_config()` logic into a single default scene.
3. **Load config** — build `AppConfig` dataclasses from config table (rest of codebase works unchanged)
4. **Load devices** — create `ManagedDevice` entries with `status="offline"`, seed latency from `last_latency_ms` (passed as `initial_value_ms` to the latency strategy constructor)
5. **Load scenes** — for each scene with `is_active=1`: build `ScenePipeline`. Load order matters: independent-effect scenes first, then shared-effect scenes (so their source deck exists). For each independent scene, load its `scene_effect_state` row and instantiate the effect + deck. For each shared scene, check `effect_mode == "shared"` and skip `scene_effect_state` lookup — instead reference the source scene's already-built deck. If source scene is not active or not found, fall back to independent mode with BeatPulse defaults.
6. **App is ready** — active scenes render to their devices (offline devices skipped), UI shows device status
7. **Launch background discovery** — multi-wave scan (see below)
8. **Launch reconnect loop** — 30s interval for remaining offline devices

---

## Device Lifecycle

### ManagedDevice Changes

`ManagedDevice` gains:
- `status: Literal["online", "offline", "reconnecting"]`
- `adapter: DeviceAdapter` — uses a `GhostAdapter` when offline instead of `None`. `GhostAdapter` is a concrete `DeviceAdapter` subclass that: provides stored `device_info`/`led_count`/`is_connected=False`, `supports_latency_probing=False`, raises on `send_frame()`. This avoids null-safety refactoring across scheduler, web routers, and all code that accesses `device.adapter.*`.
- Device info always available (from ghost adapter when offline, from real adapter when online)

Scheduler skips devices where `adapter.is_connected == False` (ghost returns `False`; existing check at `scheduler.py:138` already handles this).

### DeviceManager Changes

- `add_device(adapter_or_info, tracker, max_fps)` — if passed a DeviceInfo, wraps in GhostAdapter
- `promote_device(stable_id, adapter)` — swap ghost for real adapter, set status to online
- `demote_device(stable_id)` — swap real adapter for ghost, set status to offline
- `remove_device(stable_id)` — remove from managed list entirely
- `rediscover()` — deprecated, replaced by DiscoveryOrchestrator
- Device list is dynamic: scheduler handles add/remove at runtime (see Scheduler section)

### Scheduler Dynamic Device Handling

The `LookaheadScheduler` currently takes a fixed device list at construction with positionally-indexed `_slots` and `_send_counts`.

To support dynamic devices, replace positional list indexing with **dict keyed by stable_id**. Currently `_devices`, `_slots`, and `_send_counts` are parallel lists indexed by position — send tasks capture their index at creation time, which breaks on insertion/removal. New design:

- `_device_state: dict[str, DeviceSendState]` where `DeviceSendState` bundles the `ManagedDevice`, `FrameSlot`, `send_count`, `send_task`, and `pipeline` reference
- `add_device(managed, pipeline)` — create `DeviceSendState`, insert into dict, spawn send task
- `remove_device(stable_id)` — cancel send task, remove from dict
- Send tasks look up their own state by stable_id (no positional index)
- Distributor loop iterates `_device_state.values()` — dict mutation between iterations is safe on a single event loop
- GhostAdapter devices have send tasks that skip immediately (`is_connected=False`)

### Device Matching (for promoting offline → online)

Priority order:
1. `(backend, mac)` — stable identity across IP changes (LIFX)
2. `(backend, device_id)` — Govee hardware ID (stable across IP changes)
3. `(backend, name)` — last resort (OpenRGB)

---

## Robust Network Discovery

### DiscoveryOrchestrator (`devices/discovery.py`)

New class that owns the multi-wave discovery logic. Replaces `DeviceBackend.discover_all()` as the entry point. Also replaces `DeviceManager.rediscover()` (which also calls `discover_all()`).

**Backend lifecycle:** The orchestrator instantiates each backend **once** at construction and reuses them across waves. This is critical: LIFX transport's `discover()` swaps packet handlers (concurrent calls would conflict), and Govee transport binds port 4002 (rebinding fails). Backends are shut down when the orchestrator is stopped.

### Multi-wave Scanning

3 waves, ~5s apart. Each wave **must complete fully** (all backends, all response collection) before the next wave starts. The 5s interval is measured from wave completion, not wave start. All backends within a wave run in parallel via `asyncio.gather()`.

**Expected wall-clock time:** Unicast sweep of 254 hosts at 50 concurrent probes with 500ms timeout ≈ 2.6s per sweep. With broadcast + unicast per wave, ~13s per wave. Total for 3 waves with 5s gaps ≈ 49s. This is acceptable for background operation.

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
   - Subnet determined from resolved network interface + configurable mask
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
# Resolve "auto" interface to actual IP (reuse Pro DJ Link interface detection logic)
interface_ip = resolve_interface(config.network.interface)
subnet = IPv4Network(f"{interface_ip}/{config.discovery.subnet_mask}", strict=False)
```

When `config.network.interface == "auto"`, resolve to the actual IP of the default network interface (same logic Pro DJ Link uses for binding). The resolved IP is cached for the discovery session.

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
- `device_offline` — device disconnected or unreachable
- `discovery_wave_complete` — wave N finished, N devices found
- `discovery_complete` — all waves done

### API Endpoints

- `POST /api/devices/scan` — trigger immediate full multi-wave scan (including subnet sweep). Replaces existing `POST /api/devices/discover`.
- `POST /api/devices/scan?wave=1` — single wave (quick check)
- `DELETE /api/devices/{device_name}` — unregister device from DB (cascades to groups and scene_placements). Resolves display name to stable ID internally.
- `PUT /api/devices/{device_name}` — edit device metadata (rename, override LED count, etc.)

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

Dumps entire DB into a single structured TOML file. The marshaling layer (`persistence/toml_io.py`) converts between DB flat columns and TOML nested structures (e.g., `position_x/y/z` columns ↔ `position = [x, y, z]` array, `section + key` ↔ nested TOML tables).

```toml
[config.engine]
fps = 60
max_lookahead_ms = 1000

[config.network]
interface = "192.168.1.100"

[config.discovery]
waves = 3
subnet_mask = 24

[devices."Kitchen Strip"]
backend = "lifx"
led_count = 60
ip = "192.168.1.42"
mac = "D0:73:D5:XX:YY:ZZ"
last_latency_ms = 48.5

[devices."Desk Light"]
backend = "govee"
led_count = 100
ip = "192.168.1.55"
device_id = "XX:XX:XX:XX:XX:XX:XX:XX"
sku = "H6159"
last_latency_ms = 95.2

[scenes."dj-booth"]
name = "DJ Booth"
mapping_type = "linear"
effect_mode = "independent"
is_active = true

[scenes."dj-booth".effect]
effect_class = "beat_pulse"
params = { gamma = 3.0, palette = ["#ff0000", "#0000ff"] }

[scenes."dj-booth".placements."Kitchen Strip"]
position = [0.0, 0.0, 0.0]
geometry = "strip"
direction = [1.0, 0.0, 0.0]
length = 1.5

[scenes."dance-floor"]
name = "Dance Floor"
mapping_type = "radial"
mapping_params = { center = [1.0, 0.0, 0.0], max_radius = 3.0 }
effect_mode = "shared"
effect_source = "dj-booth"
is_active = true

[scenes."dance-floor".placements."Desk Light"]
position = [2.0, 0.0, 0.0]
geometry = "point"

[groups."main-stage"]
color = "#ff6600"
devices = ["Kitchen Strip", "Desk Light"]

[presets."My Preset"]
effect_class = "beat_pulse"
params = { gamma = 2.5 }
```

TOML export/import uses **display names** for devices (human-readable). On import, display names are resolved to stable IDs via the devices table.

### Import

`POST /api/state/import` or CLI `--import state.toml`

- Parses TOML, validates, upserts into DB
- Partial imports supported (e.g., TOML with only `[devices]` updates just devices)
- Existing data not in the import file is left untouched

### First-launch Migration

- If `state.db` missing but `config.toml` exists → auto-import:
  - Config key-value pairs mapped to `config` table
  - `EffectConfig`: if `active_effect == "beat_pulse"`, construct `params = {"palette": beat_pulse_palette, "gamma": beat_pulse_gamma}`; other effects use empty params (defaults)
  - `scene_config` dict parsed using existing `SceneModel.from_config()` logic into a single default scene named "Default"
- If `presets.toml` exists → merge into `presets` table
- Rename originals to `.bak` after successful migration

---

## Impact on Existing Code

### Files Modified

- `config.py` — `load_config()` reads from StateDB instead of TOML; `AppConfig` gains `DiscoveryConfig` dataclass; `EffectConfig` removed from `AppConfig` (effect state now lives in `scene_effect_state` table, not config)
- `types.py` — `DeviceInfo` gains `mac: str | None = None` and `stable_id: str | None = None` fields (frozen dataclass, added with defaults so all existing constructors remain valid)
- `main.py` — new startup flow (DB init → load state → build ScenePipelines → background discovery → reconnect loop)
- `devices/backend.py` — `discover_all()` deprecated; individual `discover()` methods retained, called by `DiscoveryOrchestrator`
- `devices/manager.py` — `ManagedDevice` gains `status` field; add `promote_device()`/`demote_device()`; device list becomes dynamic; `rediscover()` deprecated
- `devices/lifx/transport.py` — unicast sweep, increased timeouts (100ms→500ms), broadcast retries (3x)
- `devices/lifx/discovery.py` — all three adapter constructors (`LifxBulbAdapter`, `LifxStripAdapter`, `LifxTileChainAdapter`) pass `mac=record.mac.hex()` to `DeviceInfo`
- `devices/govee/transport.py` — unicast sweep, port 4002 bind retry with backoff (socket creation), increased window (5s→10s)
- `devices/govee/backend.py` — pass `stable_id=f"govee:{record.device_id}"` to `DeviceInfo` at adapter construction
- `devices/openrgb_backend.py` — connection timeout (5s), retry on failure
- `effects/deck.py` — auto-save effect state on swap/param change (calls StateDB via callback)
- `effects/presets.py` — `PresetStore` backed by StateDB instead of TOML file
- `effects/engine.py` — render loop iterates `pipelines: list[ScenePipeline]` instead of single deck; each pipeline gets its own `deck.render()` call and ring buffer write; `led_count` per-pipeline not global
- `scheduling/scheduler.py` — replace positional `_devices`/`_slots`/`_send_counts` lists with `_device_state: dict[str, DeviceSendState]`; each `DeviceSendState` holds its pipeline reference (and thus which `RingBuffer` to read from); dynamic `add_device()`/`remove_device()` methods
- `spatial/scene.py` — `SceneModel` updated to support multiple named scenes; `from_config()` still works for migration
- `spatial/compositor.py` — per-scene compositor instances (no structural change, just multiple instances)
- `web/app.py` — `create_app()` accepts `StateDB` instead of `config_path`; stored on `app.state`
- `web/router_config.py` — reads/writes config via StateDB
- `web/router_effects.py` — effect changes trigger auto-save; scene-aware effect endpoints
- `web/router_scene.py` — rewritten for multi-scene CRUD, activation/deactivation, per-scene placements/effects/mapping. Routes use display names. Replaces single-scene endpoints.
- `web/router_devices.py` — `POST /devices/discover` replaced by `POST /devices/scan`; device status field in responses
- `web/ws.py` — device stats include `status` field; frame channel uses display names (no change to protocol)
- `events.py` — add event types: `DeviceDiscoveredEvent`, `DeviceOnlineEvent`, `DeviceOfflineEvent`, `DiscoveryWaveCompleteEvent`, `DiscoveryCompleteEvent`, `SceneActivatedEvent`, `SceneDeactivatedEvent`

### New Files

- `persistence/state_db.py` — `StateDB` class (SQLite connection, load/save methods, debounce logic with `call_later` + `create_task(to_thread(...))`, schema migrations)
- `persistence/migrations/` — sequential SQL migration scripts (`001_initial.sql`, etc.)
- `persistence/toml_io.py` — TOML ↔ DB marshaling for import/export (handles `position_x/y/z` ↔ `position = [x,y,z]`, `section+key` ↔ nested tables, display name ↔ stable ID resolution)
- `devices/discovery.py` — `DiscoveryOrchestrator` (backend lifecycle, multi-wave scanning, subnet probing, reconnect loop, interface resolution for "auto")
- `devices/ghost.py` — `GhostAdapter(DeviceAdapter)` with `is_connected=False`, `supports_latency_probing=False`, stored `device_info`/`led_count`, raises on `send_frame()`
- `spatial/pipeline.py` — `ScenePipeline` dataclass: bundles `EffectDeck`, `RingBuffer`, `SpatialCompositor`, device list, mapping per active scene

### Files Removed (after migration)

- `presets.toml` — data migrated to DB (renamed to `.bak`)
- `config.toml` — data migrated to DB (renamed to `.bak`)

### Unchanged

- `effects/` (render logic, registry, params) — no changes to effect implementations
- `beat/` — no changes
- `prodjlink/` — no changes
- `latency/` — no changes (strategy `initial_value_ms` used for seeding from DB, already supported)
- Frontend — no breaking changes to existing APIs. New endpoints and device status field available for future UI integration. Multi-scene UI is additive.
