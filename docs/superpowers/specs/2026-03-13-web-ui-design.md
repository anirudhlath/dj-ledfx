# dj-ledfx Web UI Design Specification

## Overview

A fully featured web UI for dj-ledfx providing live performance control and deep device/scene configuration. The UI serves as both a real-time control surface during DJ sets and a comprehensive setup tool for device placement, spatial mapping, and effect management.

**Tech stack:** FastAPI + Granian (embedded ASGI) backend, Svelte 5 + Threlte + shadcn-svelte + Tailwind frontend.

**Design language:** "Studio Hardware" — matte-black recessed panels inspired by Pioneer DJM mixers and modular synth racks. Unified JetBrains Mono typography. Electric cyan (#00e5ff) as sole accent color.

---

## 1. Architecture

### 1.1 System Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    Browser (Svelte 5 SPA)                │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │Transport │ │ Effect   │ │ Device   │ │  3D Scene │  │
│  │Display   │ │ Deck     │ │ Manager  │ │  Editor   │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────┬─────┘  │
│       └─────────┬───┴────────────┴─────────────┘        │
│            WebSocket Client (single connection)          │
│            REST Client (fetch wrapper)                   │
└────────────────────┬──────────────────────────────────────┘
                     │ ws:// + http://
┌────────────────────┴──────────────────────────────────────┐
│               FastAPI Backend (src/dj_ledfx/web/)         │
│  ┌───────────────┐  ┌────────────────────────────────┐   │
│  │ REST API      │  │ WebSocket Hub                  │   │
│  │ /api/effects  │  │  - beat state (30fps poll)     │   │
│  │ /api/devices  │  │  - frame snapshots (pull)      │   │
│  │ /api/scene    │  │  - device stats (1fps)         │   │
│  │ /api/presets  │  │  - commands (bidirectional)     │   │
│  │ /api/config   │  │  - system status (0.1fps)      │   │
│  └───────┬───────┘  └────────────┬───────────────────┘   │
│          └──────────┬────────────┘                        │
│               App Coordinator (main.py)                   │
│    ┌────────┬───────┴──────┬────────────┐                │
│    │BeatClk │EffectEngine  │Scheduler   │SceneModel      │
│    │        │ + Deck       │+ Snapshots │+ Compositor    │
└────┴────────┴──────────────┴────────────┴────────────────┘
```

### 1.2 Granian Embedded Server Integration

The web server runs as an asyncio task on the existing event loop using Granian's embedded server mode. This avoids signal handler conflicts and process management complexity.

```python
from granian.server.embed import Server
from granian.constants import Interfaces

async def _run(args):
    # ... existing component creation (BeatClock, EffectEngine, etc.) ...

    # Create EffectDeck wrapping the active effect
    deck = EffectDeck(effect)
    engine = EffectEngine(clock=clock, deck=deck, ...)

    if args.web:
        from dj_ledfx.web.app import create_app
        app = create_app(
            beat_clock=clock,
            effect_deck=deck,           # For effect switching + param control
            effect_engine=engine,
            device_manager=device_manager,
            scheduler=scheduler,
            scene_model=scene_model,    # None if no [scene] config
            compositor=compositor,      # None if no scene
        )
        web_server = Server(
            target=app,
            address=config.web_host,  # default "127.0.0.1"
            port=config.web_port,     # default 8080
            interface=Interfaces.ASGI,
            websockets=True,
        )
        tasks.append(asyncio.create_task(web_server.serve()))
    # ... existing task scheduling ...

    # On shutdown:
    if args.web:
        web_server.stop()
```

**Note on Granian embedded API:** The `granian.server.embed.Server` class provides `async serve()`, `stop()`, and `reload()` methods. It runs on the existing event loop as a single worker (no process spawning). Requires `granian>=1.7`. If the embedded API changes in a future Granian release, `uvicorn` can serve as a drop-in fallback with `install_signal_handlers=False`.

**Key properties:**
- Embedded mode runs on the existing event loop — no separate process/thread
- No signal handler installation — existing `stop_event` mechanism handles SIGINT/SIGTERM
- Single worker (inherent to embedded mode) — sufficient since all I/O is async
- WebSocket support enabled via `websockets=True`

### 1.3 Optional Dependency

FastAPI and Granian are optional dependencies. The headless CLI mode works without them.

```toml
[project.optional-dependencies]
web = ["fastapi>=0.115", "granian>=1.7", "pydantic>=2.10"]

[project.dependencies]
# ... existing deps ...
tomli_w = ">=1.0"  # Core dependency — needed for preset/config persistence even without web UI
```

- `uv run -m dj_ledfx` — headless mode, no web deps required
- `uv run -m dj_ledfx --web` — starts with web UI enabled
- `uv run -m dj_ledfx --web --web-port 9090` — custom port

The `--web` flag triggers a conditional import of `dj_ledfx.web`. If the web dependencies are not installed, the import fails with a clear error message suggesting `uv pip install dj-ledfx[web]`.

### 1.4 No Authentication

This is a LAN-only tool by design. No authentication, no authorization. The web server binds to `127.0.0.1` by default. Users can override to `0.0.0.0` via config for access from other devices on the local network. CORS middleware is included with configurable `allowed_origins` (defaults to `["*"]`) for development flexibility.

---

## 2. WebSocket Protocol

A single WebSocket connection at `ws://host:port/ws` with multiplexed channels.

### 2.1 Message Envelope

**JSON messages (server → client):**
```json
{ "ch": "beat", "d": { "bpm": 128.0, "beat_phase": 0.73, "bar_phase": 0.43, "is_playing": true, "beat_pos": 3, "pitch_percent": 2.3, "deck_number": 1, "deck_name": "XDJ-AZ" }}
{ "ch": "stats", "d": { "devices": [{ "device_name": "shelf_strip", "send_fps": 42.1, "effective_latency_ms": 52.3, "frames_dropped": 0, "connected": true }] }}
{ "ch": "status", "d": { "buffer_fill": 0.95, "render_ms": 0.3, "player_count": 1, "engine_fps": 59.8 }}
{ "ch": "ack", "id": "cmd-123", "ok": true }
{ "ch": "error", "id": "cmd-123", "msg": "Unknown effect: foo" }
```

**Beat channel field mapping:** `BeatState` provides `beat_phase`, `bar_phase`, `bpm`, `is_playing`. The `next_beat_time` field from `BeatState` is intentionally omitted from the WS beat channel — it's a monotonic clock timestamp meaningful only to the server, not the browser. The client derives timing from `beat_phase` interpolation instead. Additional fields require expanding both `BeatEvent` and `BeatClock`:
- `beat_pos` (1-4): Derived from `bar_phase` as `floor(bar_phase * 4) + 1`, clamped to [1,4].
- `pitch_percent`: Must be added to `BeatEvent` (extracted from beat packet in `parse_beat_packet()`). CDJ-3000 beat packets carry raw pitch data. In passive mode (port 50001 only), this is the pitch value as reported in the beat packet — no separate track-BPM vs adjusted-BPM calculation is available without status packets on port 50002.
- `deck_number`, `deck_name`: Mapped from `BeatEvent.device_number` and `BeatEvent.device_name` respectively.
- All three are stored on `BeatClock` via an extended `on_beat()` signature (see Section 15.1). Added as optional properties on `BeatClock` (default `None` when no beat received yet).

**Stats channel field mapping:** Field names match `DeviceStats` dataclass (`device_name`, `send_fps`, `effective_latency_ms`, `frames_dropped`). The `connected` field is added to `DeviceStats`.

**Status channel field mapping:** WS field names are intentional short aliases of `SystemStatus` fields: `buffer_fill` ← `buffer_fill_level`, `render_ms` ← `avg_frame_render_time_ms`, `player_count` ← `active_player_count`. The `engine_fps` field is the actual measured render FPS (add to `SystemStatus` — track via EMA in `EffectEngine`, since configured FPS and achieved FPS may differ).

**JSON messages (client → server):**
```json
{ "ch": "cmd", "id": "cmd-123", "action": "set_effect", "params": { "effect": "beat_pulse", "gamma": 2.5 }}
{ "ch": "cmd", "id": "cmd-124", "action": "subscribe_frames", "fps": 30, "devices": ["all"] }
{ "ch": "cmd", "id": "cmd-125", "action": "subscribe_frames", "fps": 60, "devices": ["shelf_strip"] }
```

**Binary messages (server → client, frame data):**
```
[2 bytes device_name_len (little-endian uint16)][N bytes device_name UTF-8][4 bytes timestamp (little-endian float32)][LED_count * 3 bytes RGB]
```

All multi-byte values use **little-endian** byte order (native for x86/ARM, which covers all realistic deployment targets).

Using device name strings (not position-based indices) ensures stability across device reconnections and runtime discovery. The 2-byte length prefix allows parsing without knowing LED count in advance (compute from `msg_len - 2 - device_name_len - 4`).

**Device identity:** Devices are identified by `DeviceInfo.name` throughout the system — this is the existing unique identifier used by `DeviceManager`, `SceneModel`, and `LookaheadScheduler`. Device names are used directly in REST URL paths (URL-encoded where necessary). No separate `id` field is introduced to avoid a parallel identity system.

### 2.2 Channel Rates and Drivers

| Channel | Rate | Driver | Notes |
|---------|------|--------|-------|
| `beat` | ~30fps | Polling loop (asyncio task) | `BeatClock.get_state()` is lock-free. Not event-driven — EventBus beats arrive at BPM rate (~2Hz), not 30fps. Client interpolates between samples. |
| `frames` | Client-requested | Pull from snapshot slots | Server caps at 60fps max. Client sends `subscribe_frames` with desired FPS and device filter. |
| `stats` | ~1fps | Polling loop | `scheduler.get_device_stats()` |
| `status` | ~0.1fps | Polling loop | `SystemStatus.summary()` |
| `cmd` | On demand | Client-initiated | Request/response with `id` for correlation |

### 2.3 Frame Snapshot Slots

Per-device "last sent" snapshot slots replace push-based frame streaming. Zero hot-path overhead.

**Mechanism:**
1. `LookaheadScheduler._send_loop` already copies the frame before calling `adapter.send_frame(colors)`.
2. After a successful send, the send loop writes: `self._frame_snapshots[device_name] = (colors, time.monotonic())`
3. The WebSocket handler runs a separate polling loop at the client's requested FPS. Each tick: read all subscribed device snapshot slots, compare timestamps to last-sent, serialize and send only changed frames.

**Safety:** Python reference assignment is atomic under the GIL. The WS handler either reads the old or new reference, never a torn state. The colors array is already copied (for the device thread), so no mutation risk.

**Bandwidth:** At 100 LEDs/device, 10 devices, 60fps: `10 × 300 × 60 = 180KB/s`. Manageable on localhost. For remote connections, the client can request a lower FPS via `subscribe_frames`.

### 2.4 Reconnection Protocol

On WebSocket disconnect:
- Server cleans up subscription state (frame polling task cancelled, slot readers removed)
- Client auto-reconnects with exponential backoff (100ms, 200ms, 400ms... max 5s)
- On reconnect, client re-sends `subscribe_frames` to restore frame streaming
- No handshake/version check for MVP. Future: add protocol version in initial message.

---

## 3. REST API

### 3.1 Effect Endpoints

```
GET    /api/effects              # List available effect classes + parameter schemas
GET    /api/effects/active       # Current active effect + parameter values
PUT    /api/effects/active       # Switch effect and/or update parameters
  Body: { "effect": "beat_pulse", "params": { "gamma": 2.5, "palette": ["#ff0000", "#00ff00"] } }
  - If only "params" provided: updates current effect parameters in-place
  - If "effect" provided: hot-swaps to new effect class with given params
```

### 3.2 Preset Endpoints

```
GET    /api/presets              # List all saved presets
POST   /api/presets              # Save current effect state as preset
  Body: { "name": "Rainbow Pulse" }
PUT    /api/presets/{name}       # Update existing preset
DELETE /api/presets/{name}       # Delete preset
POST   /api/presets/{name}/load  # Load preset (applies to active deck)
```

### 3.3 Device Endpoints

```
GET    /api/devices                    # List all managed devices + stats
POST   /api/devices/discover           # Trigger device discovery scan
POST   /api/devices/{name}/identify      # Flash physical device for 3 seconds
PUT    /api/devices/{name}/latency       # Update latency config
  Body: { "strategy": "ema", "manual_offset_ms": 5.0 }
PUT    /api/devices/{name}/group         # Assign device to group
  Body: { "group": "dj_booth" }
GET    /api/devices/groups             # List all device groups
POST   /api/devices/groups             # Create group
  Body: { "name": "DJ Booth", "color": "#00e5ff" }
PUT    /api/devices/groups/{name}      # Update group (rename, color)
DELETE /api/devices/groups/{name}      # Delete group (devices become ungrouped)
```

### 3.4 Scene Endpoints

```
GET    /api/scene                      # Current scene model (placements + mapping config)
PUT    /api/scene/mapping              # Update spatial mapping config
  Body: { "type": "linear", "params": { "direction": [1,0,0] } }
GET    /api/scene/devices              # List device placements with LED positions
PUT    /api/scene/devices/{name}         # Add/update device placement
  Body: { "position": [1.0, 0.0, 1.5], "geometry": "matrix", "group": "dj_booth" }
DELETE /api/scene/devices/{name}         # Remove device from scene
```

### 3.5 Config Endpoints

```
GET    /api/config                     # Current app configuration
PUT    /api/config                     # Update config (partial update, validates)
  Body: { "engine": { "engine_fps": 90 }, "effect": { "active_effect": "beat_pulse" } }
GET    /api/config/export              # Download full config as TOML
POST   /api/config/import              # Upload TOML to apply
```

### 3.6 Response Format

All endpoints return JSON. Errors use standard HTTP status codes with body:
```json
{ "error": "Device not found", "detail": "No device with name 'foo'" }
```

---

## 4. Effect Parameter Introspection

The `Effect` ABC currently has no mechanism for parameter enumeration or runtime modification. This must be added.

### 4.1 EffectParam Descriptor

Effects declare tunable parameters using a descriptor that provides type, range, default, and metadata:

```python
# effects/params.py

@dataclass(frozen=True)
class EffectParam:
    type: Literal["float", "int", "color", "color_list", "bool", "choice"]
    default: Any
    min: float | None = None        # for float/int
    max: float | None = None        # for float/int
    step: float | None = None       # for float/int (UI slider step)
    choices: list[str] | None = None  # for choice type
    label: str | None = None        # human-readable label
    description: str | None = None
```

### 4.2 Effect ABC Modifications

```python
# effects/base.py

class Effect(ABC):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        """Return parameter schema for this effect. Override in subclasses."""
        return {}

    def get_params(self) -> dict[str, Any]:
        """Return current parameter values."""
        ...

    def set_params(self, **kwargs: Any) -> None:
        """Update parameters at runtime. Only accepts keys from parameters().
        Validates against EffectParam constraints and raises ValueError for
        unknown keys or out-of-range values. Clamping is NOT done — the caller
        (REST layer) should validate before calling, but set_params is the
        authoritative validation point."""
        schema = self.parameters()
        for key, value in kwargs.items():
            if key not in schema:
                raise ValueError(f"Unknown parameter: {key}")
            param = schema[key]
            if param.type in ("float", "int"):
                if param.min is not None and value < param.min:
                    raise ValueError(f"{key}={value} below min {param.min}")
                if param.max is not None and value > param.max:
                    raise ValueError(f"{key}={value} above max {param.max}")
            if param.type == "choice" and value not in (param.choices or []):
                raise ValueError(f"{key}={value} not in {param.choices}")
        self._apply_params(**kwargs)

    def _apply_params(self, **kwargs: Any) -> None:
        """Subclass hook: apply validated parameters. Override in subclasses."""
        ...

    @abstractmethod
    def render(self, beat_phase: float, bar_phase: float, dt: float, led_count: int) -> NDArray[np.uint8]:
        ...
```

### 4.3 BeatPulse Example

```python
class BeatPulse(Effect):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "gamma": EffectParam(type="float", default=2.0, min=0.5, max=5.0, step=0.1, label="Gamma"),
            "palette": EffectParam(type="color_list", default=["#ff0000", "#00ff00", "#0000ff"], label="Palette"),
        }

    def get_params(self) -> dict[str, Any]:
        return {"gamma": self._gamma, "palette": [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in self._palette]}

    def _apply_params(self, **kwargs: Any) -> None:
        if "gamma" in kwargs:
            self._gamma = float(kwargs["gamma"])
        if "palette" in kwargs:
            self._palette = _parse_palette(kwargs["palette"])
```

### 4.4 Effect Registry

At startup, discover all `Effect` subclasses via `__init_subclass__` (same pattern as `DeviceBackend` in `devices/backend.py`):

```python
# effects/base.py — add __init_subclass__ to Effect ABC

class Effect(ABC):
    _registry: ClassVar[dict[str, type[Effect]]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if not inspect.isabstract(cls):
            # Name derived from class: BeatPulse → "beat_pulse" (snake_case)
            name = _to_snake_case(cls.__name__)
            Effect._registry[name] = cls
```

```python
# effects/registry.py — convenience functions

def get_effect_classes() -> dict[str, type[Effect]]:
    """Return all registered effect classes."""
    return dict(Effect._registry)

def get_effect_schemas() -> dict[str, dict[str, EffectParam]]:
    """Return parameter schemas for all registered effects."""
    return {name: cls.parameters() for name, cls in Effect._registry.items()}

def create_effect(name: str, **params: Any) -> Effect:
    """Instantiate an effect by registered name with given parameters."""
    cls = Effect._registry[name]
    return cls(**params)
```

**Constructor contract:** Effect constructor keyword argument names MUST match the keys in `parameters()`. The registry's `create_effect()` passes params directly as `cls(**params)`.

Effect names are derived by converting the class name to snake_case: `BeatPulse` → `"beat_pulse"`, `RainbowWave` → `"rainbow_wave"`. This matches the existing `active_effect` config key convention.

The REST API `/api/effects` returns the full schema for all effects, enabling the frontend to auto-generate parameter controls (sliders for floats, color pickers for colors, etc.).

---

## 5. Effect Deck

### 5.1 EffectDeck

A thin wrapper around the active Effect instance that manages lifecycle and parameter state:

```python
# effects/deck.py

class EffectDeck:
    def __init__(self, effect: Effect) -> None:
        self._effect = effect

    @property
    def effect_name(self) -> str: ...

    @property
    def effect(self) -> Effect: ...

    def swap_effect(self, new_effect: Effect) -> None:
        """Hot-swap the active effect. Thread-safe on the event loop."""
        self._effect = new_effect

    def render(self, beat_phase: float, bar_phase: float, dt: float, led_count: int) -> NDArray[np.uint8]:
        return self._effect.render(beat_phase, bar_phase, dt, led_count)
```

**Integration:** `EffectEngine.__init__` signature changes from `effect: Effect` to `deck: EffectDeck`. Internally, `EffectEngine.render()` calls `self._deck.render()` instead of `self._effect.render()`. The deck reference is passed to both `EffectEngine` and the web API layer (`create_app()`) — the single `EffectDeck` instance is shared.

**Hot-swap behavior:** When the effect is swapped, the ring buffer still contains frames rendered by the old effect (up to `max_lookahead_s` of future frames). High-latency devices will display old-effect frames until the buffer cycles. This is acceptable — a ~1 second transition at worst. No crossfade needed for MVP.

### 5.2 Presets

```python
# effects/presets.py

@dataclass(frozen=True)
class Preset:
    name: str
    effect_class: str  # registered effect name
    params: dict[str, Any]

class PresetStore:
    def __init__(self, path: Path) -> None: ...  # presets.toml
    def list(self) -> list[Preset]: ...
    def save(self, preset: Preset) -> None: ...
    def delete(self, name: str) -> None: ...
    def load(self, name: str) -> Preset: ...
```

**Persistence:** Presets are stored in a separate `presets.toml` file (not the main config). Writes use atomic rename (`write to .tmp`, `os.replace`) to prevent corruption.

---

## 6. Config Persistence Strategy

### 6.1 What Persists vs. Ephemeral

| Data | Persistence | File |
|------|-------------|------|
| Effect presets | Persisted | `presets.toml` |
| Scene placements | Persisted | Main config `[scene]` section |
| Device groups | Persisted | Main config `[device_groups]` section |
| App settings (FPS, lookahead, etc.) | Persisted | Main config |
| Current active effect + params | Ephemeral | In-memory only |
| Live parameter tweaks | Ephemeral | In-memory only |
| Device latency strategy/offset | Persisted | Main config `[devices.*]` |

### 6.2 Write-Back Mechanism

Config writes use `tomli_w` (or stdlib `tomllib` for read + manual TOML string building for write) with atomic file replacement:

```python
def save_config(config: AppConfig, path: Path) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(serialize_toml(config))
    os.replace(tmp, path)  # atomic on POSIX
```

Config changes via REST API update the in-memory `AppConfig` immediately and trigger an async background write. Most changes apply without restart. Network interface changes require restart (the API returns `{ "restart_required": true }`).

---

## 7. Runtime Scene Editing & Compositor Rebuild

### 7.1 SceneModel Mutations

The `SceneModel` (from the spatial mapping branch) is currently constructed once from TOML at startup. For the web UI, it needs mutation methods:

```python
class SceneModel:
    # Existing...
    def add_placement(self, placement: DevicePlacement) -> None: ...
    def update_placement(self, device_id: str, position: tuple[float,float,float] | None = None, geometry: DeviceGeometry | None = None) -> None: ...
    def remove_placement(self, device_id: str) -> None: ...
```

Each mutation invalidates the `_position_cache` for the affected device.

### 7.2 Compositor Rebuild

When scene placements change via the web UI, the compositor's precomputed `_strip_indices` cache must be rebuilt. The approach is **full replacement** (option 1 from architect review — simple, aligned with codebase philosophy):

1. REST handler receives scene update
2. Mutate `SceneModel` (add/update/remove placement)
3. Construct a new `SpatialCompositor(scene, mapping)`
4. Swap the scheduler's compositor reference: `scheduler.compositor = new_compositor`

The scheduler's `_send_loop` reads `self._compositor` synchronously per frame. Since reference assignment is atomic (GIL), the send loop either uses the old or new compositor — never a half-built one. There may be a single frame during the swap where some devices use the old compositor and others use the new one. This is imperceptible.

### 7.3 Mapping Changes

When the spatial mapping type or parameters change (e.g., switching from linear to radial), the same rebuild process applies: create a new `SpatialMapping` instance, create a new `SpatialCompositor`, swap.

---

## 8. 3D Scene Editor

### 8.1 Layout

Three-panel layout with toolbar and mapping preview bar:

- **Top toolbar** — Camera view presets (Perspective/Top/Front/Side), transform tools (Move/Rotate), grid snap settings
- **Left panel (240px)** — Device list grouped by zone with connection status LEDs. "Unplaced" section for discovered-but-not-positioned devices. Drag to add to scene.
- **Center** — Threlte 3D viewport with `<OrbitControls>`, `<TransformControls>`, `<Grid>`. Devices rendered as geometry-appropriate meshes with live LED colors.
- **Right panel (260px)** — Properties for selected device: position XYZ inputs, geometry info, group assignment, latency tuning (strategy + manual offset fader), spatial mapping config.
- **Bottom bar (44px)** — Mapping preview: 1D gradient strip showing effect→3D mapping result with device position markers.

### 8.2 Device Rendering in 3D

| Geometry | 3D Representation |
|----------|-------------------|
| `PointGeometry` | Glowing sphere, color = device's current LED color |
| `StripGeometry` | Line of small spheres along direction vector, each colored per LED |
| `MatrixGeometry` | Grid of small spheres matching tile layout, each colored per LED |

LED colors come from the frame snapshot WebSocket channel. The scene editor subscribes to frames for the selected device at full rate, and all devices at a lower rate for ambient visualization.

### 8.3 Interactions

- **Click** to select a device in the viewport or the device list (bi-directional selection sync)
- **Drag** (TransformControls) to reposition devices — updates position in real-time, sends `PUT /api/scene/devices/{name}` on mouse-up
- **Identify** button flashes the physical device via `POST /api/devices/{name}/identify`
- **Add to scene** — drag from "Unplaced" list into the viewport, or click "Add" which places at origin

---

## 9. Live Performance View

### 9.1 Layout (top to bottom)

1. **Navigation bar (38px)** — Logo, tab navigation (LIVE / SCENE / DEVICES / CONFIG), system status indicators (Pro DJ Link connection, device count, buffer health)
2. **Transport display (120px)** — Three columns:
   - *Left:* BPM (48px JetBrains Mono, largest element on screen), pitch %, track BPM, deck info
   - *Center:* Beat position indicators (1-2-3-4, 48x48px, active beat has aggressive glow: `box-shadow: 0 0 30px, 0 0 60px`), beat phase meter, bar phase meter
   - *Right:* Play state indicator, render time, buffer fill bar, engine FPS, drift measurement
3. **Main area (flex)** — Split `1fr 320px`:
   - *Left:* 3D scene preview with live LED colors, vignette effect, recessed bezel shadow
   - *Right:* Effect deck panel — presets grid (top, most accessible), then parameters (larger faders: 10px track, 18x24px thumb)
4. **Device monitors (bottom)** — Horizontal strip of per-device monitors in recessed display windows (inset shadow), each showing: LED indicator, device name, actual FPS, latency ms, color strip of last-sent frame

### 9.2 Preset-First Effect Deck

Presets are positioned above parameters in the deck panel because switching presets is the most frequent live action. The preset grid uses 2-column layout with hardware-style buttons showing preset name and metadata (effect type, key parameter).

### 9.3 Visual Feedback for State Changes

| Event | Visual |
|-------|--------|
| Preset switch | Active button flashes cyan (0.3s ease-out), color strip cross-dissolves |
| Parameter change | Value text highlights cyan then fades back (0.5s) |
| Device connect | LED fades in green with expanded glow |
| Device disconnect | LED pulses red 3x then turns off |
| Drift warning (>5ms) | Drift value turns amber |
| Buffer low (<50%) | Buffer bar turns amber, <20% turns red |

---

## 10. Device Management View

### 10.1 Layout

Full-width table/list with expandable rows.

| Column | Content |
|--------|---------|
| Status | LED indicator |
| Name | Device name + type badge |
| Group | Color-coded group tag |
| LEDs | Count |
| FPS | Current send rate |
| Latency | Effective latency + strategy badge |
| Connection | IP/address |
| Actions | Identify / Disconnect |

### 10.2 Features

- **Discovery panel** — "Scan for Devices" button at top, shows newly found devices with "Add" action
- **Group management** — Create/rename/delete groups, assign color, drag devices between groups
- **Bulk actions** — Multi-select devices, assign group, change latency strategy, set FPS cap
- **Device detail expand** — Click row to expand: latency history sparkline, FPS over time, packet stats, manual offset slider
- **Identify** — Flashes physical device for 3 seconds

---

## 11. Config View

### 11.1 Sections

- **Network** — Interface selector (detected interfaces or "auto"), Pro DJ Link passive mode toggle
- **Engine** — FPS slider (30-120), max lookahead slider (500-2000ms)
- **Web** — Host/port, CORS origins
- **Devices** — Per-backend enable/disable, OpenRGB host/port, LIFX discovery timeout
- **Export/Import** — Download TOML, upload TOML

### 11.2 Apply Behavior

Config changes apply immediately via REST. The API validates before applying. For settings requiring restart (network interface), the UI shows a warning banner: "Network interface change requires restart to take effect."

---

## 12. Backend Package Structure

```
src/dj_ledfx/web/
├── __init__.py          # Conditional import guard
├── app.py               # FastAPI app factory, CORS middleware, static file mount
├── router_effects.py    # /api/effects, /api/presets endpoints
├── router_devices.py    # /api/devices, /api/devices/groups endpoints
├── router_scene.py      # /api/scene endpoints
├── router_config.py     # /api/config endpoints
├── ws.py                # WebSocket endpoint, multiplexed hub, frame/beat broadcast loops
├── state.py             # FrameSnapshotSlot, WS subscription manager
└── schemas.py           # Pydantic request/response models
```

**Separate router files** instead of one monolithic `router.py` — each domain (effects, devices, scene, config) gets its own file. This keeps files focused and under ~200 lines each.

**`app.py` receives component references** at construction:

```python
def create_app(
    beat_clock: BeatClock,
    effect_deck: EffectDeck,
    effect_engine: EffectEngine,
    device_manager: DeviceManager,
    scheduler: LookaheadScheduler,
    scene_model: SceneModel | None,
    compositor: SpatialCompositor | None,
) -> FastAPI:
    app = FastAPI(title="dj-ledfx")
    app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)
    app.state.beat_clock = beat_clock
    app.state.effect_engine = effect_engine
    # ... etc
    app.include_router(effects_router, prefix="/api")
    app.include_router(devices_router, prefix="/api")
    app.include_router(scene_router, prefix="/api")
    app.include_router(config_router, prefix="/api")
    app.mount("/", StaticFiles(directory=static_dir, html=True))
    return app
```

---

## 13. Frontend Package Structure

```
frontend/
├── package.json
├── svelte.config.js
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
├── src/
│   ├── app.html
│   ├── app.css                    # Tailwind base + CSS variables (studio theme tokens)
│   ├── lib/
│   │   ├── stores/
│   │   │   ├── beat.svelte.ts     # Beat state (from WS, Svelte 5 runes)
│   │   │   ├── devices.svelte.ts  # Device list + stats + groups
│   │   │   ├── effects.svelte.ts  # Active effect, params, presets
│   │   │   └── scene.svelte.ts    # Scene placements, mapping config
│   │   ├── ws/
│   │   │   └── client.ts          # WebSocket client, multiplexed channels, reconnection
│   │   ├── api/
│   │   │   └── client.ts          # REST API typed fetch wrapper
│   │   ├── components/
│   │   │   ├── ui/                # shadcn-svelte components (copied, customized)
│   │   │   ├── transport/         # BpmDisplay, BeatGrid, PhaseMeter, PlayState
│   │   │   ├── deck/              # EffectDeck, PresetGrid, ParamSlider, PaletteEditor
│   │   │   ├── scene/             # ThrelteViewport, DeviceMesh, TransformGizmo, MappingPreview
│   │   │   ├── devices/           # DeviceTable, DeviceRow, GroupManager, DiscoveryPanel
│   │   │   └── common/            # LedIndicator, HwButton, Fader, Field (design system)
│   │   └── theme/
│   │       └── tokens.ts          # Design tokens: colors, shadows, typography, spacing
│   └── routes/
│       ├── +layout.svelte         # Nav bar, WS connection init, global stores
│       ├── +page.svelte           # Live performance view (default route)
│       ├── scene/
│       │   └── +page.svelte       # 3D scene editor
│       ├── devices/
│       │   └── +page.svelte       # Device management
│       └── config/
│           └── +page.svelte       # App configuration
```

### 13.1 Frontend Build Pipeline

```bash
# Development
cd frontend && npm install
npm run dev                          # Vite dev server on :5173, proxies /api + /ws to :8080

# Production build
npm run build                        # Outputs to frontend/build/
```

**Vite proxy config** (`vite.config.ts`):
```typescript
export default defineConfig({
    server: {
        proxy: {
            '/api': 'http://localhost:8080',
            '/ws': { target: 'ws://localhost:8080', ws: true },
        }
    }
})
```

**Production serving:** FastAPI mounts `StaticFiles(directory=...)` pointing to the built frontend assets. The path is configurable via `--web-static-dir` flag. Resolution order:
1. Explicit `--web-static-dir` argument (absolute or relative path)
2. `web.static_dir` in TOML config
3. `frontend/build/` relative to the project root (for development checkouts)
4. `importlib.resources.files("dj_ledfx") / "web" / "static"` (for installed packages)

Built assets are NOT committed to git — they are built in CI or by the developer before running in production mode. For distribution as a Python package, the built assets would be included via `package_data` in `pyproject.toml`.

**SvelteKit adapter:** The frontend uses `@sveltejs/adapter-static` for pure client-side SPA rendering (no SSR). This outputs a fully static site that FastAPI can serve directly. Configure in `svelte.config.js`:
```javascript
import adapter from '@sveltejs/adapter-static';
export default { kit: { adapter: adapter({ fallback: 'index.html' }) } };
```

### 13.2 Design Tokens

The "Studio Hardware" theme is defined as CSS variables and TypeScript constants:

```typescript
// theme/tokens.ts
export const colors = {
    accent: '#00e5ff',
    surface: '#0c0c0e',
    surfaceDeep: '#060608',
    surfaceRaised: '#141416',
    panelHeader: '#09090b',
    border: '#1a1a1e',
    borderActive: '#00e5ff44',
    textPrimary: '#eeeeee',
    textSecondary: '#888888',
    textDim: '#444444',
    textMuted: '#333333',
    statusGreen: '#22c55e',
    statusAmber: '#f59e0b',
    statusRed: '#ef4444',
    axisX: '#ef4444',
    axisY: '#22c55e',
    axisZ: '#3b82f6',
} as const;
```

---

## 14. Responsive Behavior

### 14.1 Breakpoints

| Breakpoint | Layout |
|------------|--------|
| Desktop (>1024px) | Full layout as designed |
| Tablet (768-1024px) | Transport stacks to 2 columns (BPM+beats left, stats right). Effect deck slides in as overlay. |
| Mobile (<768px) | Performance mode: BPM + beat grid + preset buttons + collapsed 3D preview. Device monitors wrap to rows. |

### 14.2 Mobile Performance Mode

On narrow screens, the live view collapses to essentials:
- BPM display (full width, large)
- Beat grid (1-2-3-4 indicators)
- Preset grid (2 columns, fills available space)
- 3D preview collapses to a thin strip showing device monitor colors
- Stats and parameters accessible via expandable drawer

Scene editor and config views redirect to a "use a larger screen" message on mobile — these are setup-time tools, not live-performance tools.

---

## 15. Modifications to Existing Code

### 15.1 Files Modified

| File | Change |
|------|--------|
| `main.py` | Add `--web`, `--web-port`, `--web-host`, `--web-static-dir` args. Conditionally import and start web server. Create `EffectDeck` and pass to both `EffectEngine` and `create_app()`. |
| `config.py` | Refactor `AppConfig` from flat fields to nested dataclasses: `EngineConfig` (`engine_fps`, `max_lookahead_s`), `EffectConfig` (`active_effect`, `led_count`), `NetworkConfig` (`interface`, `passive_mode`), `WebConfig` (`enabled`, `host`, `port`, `static_dir`, `cors_origins`), `DevicesConfig` (per-backend settings). Each maps to a TOML section (`[engine]`, `[effect]`, `[network]`, `[web]`, `[devices]`). The REST config PUT body mirrors this nested structure. Add `save_config()` function with atomic write via `tomli_w`. |
| `events.py` | Add `pitch_percent: float` field to `BeatEvent` dataclass. |
| `prodjlink/listener.py` | Pass `BeatPacket.pitch_percent` through to `BeatEvent` in `datagram_received()` (the packet parser already extracts it into `BeatPacket`). |
| `beat/clock.py` | Extend `on_beat()` signature to accept `pitch_percent: float | None = None`, `device_number: int | None = None`, `device_name: str | None = None`. Add corresponding read-only properties. Update `main.py`'s `on_beat` wrapper to forward these fields from `BeatEvent`. |
| `types.py` | Add `connected: bool` field to `DeviceStats`. |
| `effects/base.py` | Add `_registry` classvar, `__init_subclass__`, `parameters()` classmethod, `get_params()`, `set_params()` to Effect ABC. |
| `effects/beat_pulse.py` | Implement `parameters()`, `get_params()`, `set_params()`. |
| `effects/engine.py` | Accept `EffectDeck` instead of raw `Effect`. Call `deck.render()`. |
| `devices/manager.py` | Add `rediscover()`, `identify_device()`, group management methods. |
| `scheduling/scheduler.py` | Add `_frame_snapshots` dict. Write snapshot after each device send. Add `compositor` property with setter for runtime swap. |
| `pyproject.toml` | Add `[project.optional-dependencies]` web group. Add `tomli_w` as core dependency. |

### 15.2 Files Added (Backend)

| File | Purpose |
|------|---------|
| `effects/params.py` | `EffectParam` dataclass |
| `effects/deck.py` | `EffectDeck` wrapper |
| `effects/presets.py` | `PresetStore` + `Preset` dataclass |
| `effects/registry.py` | Effect class auto-registration + schema discovery |
| `web/__init__.py` | Conditional import guard |
| `web/app.py` | FastAPI app factory |
| `web/router_effects.py` | Effect + preset endpoints |
| `web/router_devices.py` | Device + group endpoints |
| `web/router_scene.py` | Scene + mapping endpoints |
| `web/router_config.py` | Config endpoints |
| `web/ws.py` | WebSocket hub |
| `web/state.py` | Snapshot slots + subscription manager |
| `web/schemas.py` | Pydantic models |

### 15.3 Files Added (Frontend)

The entire `frontend/` directory as described in Section 13.

### 15.4 Spatial Mapping Branch Integration

**Prerequisite:** The `feature/3d-spatial-mapping` branch must be merged to master before **Phase 2** (3D Scene Editor) begins. **Phase 1** (core web UI: transport, effect deck, device management) can be built without it.

**Phase 1 (no spatial dependency):**
- Live performance view (transport, effect deck, presets, device monitors)
- Device management view (discovery, groups, latency tuning)
- Config view
- WebSocket protocol (beat, frames, stats)
- Effect parameter introspection + deck system
- Scene endpoints return `null`/empty when no spatial module is available

**Phase 2 (requires spatial mapping merge):**
- 3D scene editor (Section 8)
- Scene REST endpoints (Section 3.4)
- Runtime compositor rebuild (Section 7)
- Live LED colors in 3D viewport

The web UI depends on these spatial mapping types:
- `spatial/scene.py` — `SceneModel` with new mutation methods (Section 7.1)
- `spatial/compositor.py` — `SpatialCompositor` (rebuilt on scene change, Section 7.2)
- `spatial/geometry.py` — `PointGeometry`, `StripGeometry`, `MatrixGeometry` (serialized to JSON for frontend)
- `spatial/mapping.py` — `LinearMapping`, `RadialMapping` (configured via REST API)
- `devices/adapter.py` — `geometry` property on DeviceAdapter (used for auto-detection in scene editor)

### 15.5 DeviceManager Additions

The existing `DeviceManager` needs these methods for the web UI:

```python
class DeviceManager:
    # Existing methods...

    async def rediscover(self) -> list[DiscoveredDevice]:
        """Trigger a fresh discovery scan across all backends."""
        ...

    async def identify_device(self, device_name: str, duration_s: float = 3.0) -> None:
        """Flash a device to identify it physically. Sends white frames for duration_s."""
        ...

    # Group management (in-memory state, persisted to config)
    def get_groups(self) -> dict[str, DeviceGroup]: ...
    def create_group(self, name: str, color: str) -> DeviceGroup: ...
    def delete_group(self, name: str) -> None: ...
    def assign_to_group(self, device_name: str, group_name: str) -> None: ...
```
