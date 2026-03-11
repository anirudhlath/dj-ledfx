# dj-ledfx MVP Design Spec

## Overview

dj-ledfx is a standalone LED effect engine driven by Pro DJ Link network data. It connects to Pioneer/AlphaTheta DJ equipment (XDJ-AZ, CDJ-3000, etc.), extracts real-time beat/phase information, and drives LED lighting devices with latency-compensated, beat-synced effects.

**Key differentiator:** Pre-computed waveform data enables lookahead scheduling — each device receives commands early by its measured latency, so all lights hit beats simultaneously regardless of their response time.

**MVP goal:** Beat-synced color pulse across all connected OpenRGB devices, proving the full pipeline end-to-end.

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  dj-ledfx                                                       │
│                                                                  │
│  ┌─────────────┐   ┌──────────────┐   ┌──────────────────────┐  │
│  │ ProDJLink   │──▶│  BeatClock   │──▶│  EffectEngine        │  │
│  │ Listener    │   │              │   │  (renders FUTURE     │  │
│  │ (passive)   │   │  phase       │   │   frames into        │  │
│  │             │   │  interpolation│   │   timestamped ring   │  │
│  │ port 50001  │   │  drift corr  │   │   buffer)            │  │
│  └─────────────┘   └──────────────┘   └──────────┬───────────┘  │
│                                                   │              │
│                                        ┌──────────▼───────────┐  │
│                                        │ LookaheadScheduler   │  │
│                                        │                      │  │
│                                        │ Per device:          │  │
│                                        │ read frame at        │  │
│                                        │ now + device_latency │  │
│                                        │ send immediately     │  │
│                                        └──────────┬───────────┘  │
│                                                   │              │
│                              ┌────────────────────┼──────┐       │
│                              ▼                    ▼      ▼       │
│                        ┌──────────┐        ┌───────┐┌───────┐   │
│                        │ OpenRGB  │        │ LIFX  ││ Govee │   │
│                        │ Adapter  │        │(future)││(future│   │
│                        │ (MVP)    │        │       ││      )│   │
│                        └──────────┘        └───────┘└───────┘   │
└──────────────────────────────────────────────────────────────────┘
```

## Components

### 1. ProDJLink Listener (`prodjlink/`)

Asyncio UDP listener on port 50001 (beat/sync broadcast). MVP uses **passive mode only** — no virtual CDJ registration required. Beat packets are broadcast and can be received by simply binding to the port.

**Passive mode provides:**
- BPM (pitch-adjusted)
- Beat position within bar (1-4)
- Milliseconds to next beat
- Player number / device ID

**Not needed for MVP (requires active/virtual CDJ mode):**
- Player status (play/pause/cue) — port 50002, needs keepalive handshake
- Track metadata, waveforms — needs dbserver TCP connection
- Track loading, media browsing

**Packet parsing:** Uses `struct` module against documented binary formats from [DJ Link Ecosystem Analysis](https://djl-analysis.deepsymmetry.org/djl-analysis/beats.html). Beat packets are 96 bytes with a known header structure.

**Protocol version scope (MVP):** Only CDJ-3000 generation packets (capability byte `0x1F`) are fully supported. Packets from older hardware (NXS2, NXS) are silently ignored with a DEBUG log. This can be extended post-MVP.

**Network interface:** Must bind to the correct network interface where Pro DJ Link traffic lives. Configurable in TOML config, with auto-detection as default (scan interfaces for DJ Link broadcast traffic).

**XDJ-AZ consideration:** The XDJ-AZ is an all-in-one 4-deck unit. It may send beat packets from a single device ID with deck identifiers, rather than separate device IDs per deck. The listener must track player/deck numbers, not assume one device = one player.

**Files:**
- `listener.py` — asyncio UDP protocol, socket binding, interface selection
- `packets.py` — binary packet parsing with `struct.unpack_from()`
- `constants.py` — packet type codes, byte offsets, magic bytes, port numbers

### 2. BeatClock (`beat/`)

Maintains continuous beat phase by consuming beat packets and interpolating between them.

**Outputs (synchronous, non-async, lock-free reads):**
- `beat_phase: float` — 0.0 (on beat) → 1.0 (next beat), continuous
- `bar_phase: float` — 0.0 (beat 1) → 1.0 (beat 1 of next bar), continuous
- `bpm: float` — current pitch-adjusted BPM
- `is_playing: bool` — **inferred from packet flow in passive mode** (see below)
- `next_beat_time: float` — monotonic timestamp of predicted next beat

**Concurrency model:** All components run on a single asyncio event loop. BeatClock state is written by the listener coroutine and read by the render loop coroutine. Since asyncio is cooperative and single-threaded, no locks are needed. BeatClock's read methods (`beat_phase`, `bar_phase`, etc.) are synchronous pure computations using `time.monotonic()` — they must never await or perform I/O.

**Interpolation:** Between beat packets, phase advances linearly using `time.monotonic()` and current BPM. BPM must be pitch-adjusted: `track_bpm * (1 + pitch/100)`.

**Drift correction (hybrid):**
Drift is defined as the absolute difference in milliseconds between the predicted beat time (from interpolation) and the actual beat time (from the incoming packet's timestamp). At each beat packet resync:
- If drift < 5ms: soft correction — slightly adjust internal BPM to converge over the next beat period
- If drift >= 5ms: hard snap to packet phase

**`is_playing` in passive mode:** In passive mode (MVP), there is no explicit play/pause signal — beat packets on port 50001 do not contain play state. `is_playing` is inferred entirely from packet flow:
- Packets arriving regularly → `is_playing = True`
- No packets for >2s → `is_playing = False`, phase freezes
- Packets resume → `is_playing = True`, resync to new beat data

This is a known MVP limitation. Active mode (future) will provide explicit play/pause via status packets on port 50002.

**Edge cases:**
- No packets for >2s: `is_playing = False`, phase freezes
- BPM = 0: stopped state
- Rapid packets (scratch): accept latest, ignore intermediate
- Phase wrapping (0.98 → 0.02): effects must handle this (documented contract)

**Demo mode:** `BeatSimulator` generates synthetic beat events at a configurable BPM for testing without DJ hardware. Simulates: bar position cycling (1-2-3-4), configurable BPM with optional tempo drift, and start/stop transitions. Implements the same interface as the real listener so BeatClock is agnostic to the source.

**Files:**
- `clock.py` — BeatClock with phase interpolation and drift correction
- `simulator.py` — BeatSimulator for demo/testing mode

### 3. Effect Engine (`effects/`)

60fps render loop that computes LED colors from beat phase. Critically, the engine renders **future frames** for the lookahead scheduler.

**LED count model:** The engine renders at a fixed `led_count` configured globally (default: max LED count across all connected devices, or a user-configured value). Each device adapter maps/truncates the rendered frame to its actual LED count. This avoids per-device rendering in the engine and keeps the ring buffer simple (uniform frame size).

**Render loop timing:** Uses monotonic deadline tracking with adaptive sleep. Each tick targets `last_tick_time + frame_period`. After rendering and buffer write, sleeps for `max(0, deadline - now)`. If a tick runs late, the next deadline stays on the grid (no drift accumulation). Frame period = `1.0 / fps`.

**Render loop (each tick):**
1. The engine renders one frame per tick for the **future edge** of the buffer: `target_time = now + max_lookahead`
2. Query BeatClock for extrapolated phase at `target_time`
3. Pass phase + metadata to active effect, receive RGB array
4. Store `RenderedFrame` in ring buffer with `target_display_time`
5. The buffer gradually fills on startup — see warm-up policy below

**Ring buffer warm-up policy:** On startup, the buffer is empty. It takes `max_lookahead / frame_period` ticks (60 ticks = 1 second at 60fps) to fill. During warm-up:
- Devices whose `effective_latency` exceeds the current buffer depth receive no frames (silent/black)
- Low-latency devices (e.g., OpenRGB at 10ms) start receiving frames almost immediately (after 1 tick)
- The scheduler logs which devices are waiting for buffer fill at DEBUG level
- No blocking — the system is fully operational for devices it can serve

**Ring buffer indexing:** Flat circular array with a write index that advances modulo buffer size. Each slot stores a `RenderedFrame` with a monotonic timestamp. The scheduler scans for the frame with `target_time` closest to `now + device_latency` using nearest-neighbor selection (no interpolation — at 60fps / 16.6ms granularity, the maximum timing error is 8.3ms, well below visual perception for LED effects).

**RenderedFrame** (canonical definition in `types.py`):
```python
@dataclass
class RenderedFrame:
    colors: np.ndarray       # shape (n_leds, 3), dtype uint8
    target_time: float       # monotonic time when this should be displayed
    beat_phase: float        # for debugging/logging
    bar_phase: float
```

**Effect ABC:**
```python
class Effect(ABC):
    @abstractmethod
    def render(
        self,
        beat_phase: float,
        bar_phase: float,
        dt: float,
        led_count: int,
    ) -> np.ndarray:
        """Return shape (led_count, 3) uint8 RGB array."""
        ...
```

**MVP effect — BeatPulse:**
- `brightness = (1.0 - beat_phase) ** gamma` — flash on beat, exponential decay
- Color cycles through a 4-color palette indexed by beat position in bar
- Gamma and palette configurable via TOML

**Files:**
- `engine.py` — render loop, ring buffer management
- `base.py` — Effect ABC
- `beat_pulse.py` — MVP effect

### 4. Lookahead Scheduler (`scheduling/`)

Reads from the timestamped ring buffer and dispatches frames to each device at the right time.

**Ring buffer:**
- Size: 60 frames (1 second at 60fps) — provides margin for devices up to ~900ms latency
- Frames indexed by `target_display_time` (monotonic timestamp)
- Memory: 60 frames × 1000 LEDs × 3 bytes = 180KB (negligible)

**Per-device dispatch:**
- Each device runs an async task
- Task selects the frame where `target_display_time` is closest to `now + device.effective_latency`
- Copies frame data before passing to device thread (avoids race condition with render loop)
- Sends via `adapter.send_frame(frame_copy)`

**Direction (critical):** High-latency devices read *newer* frames (further into the future). A LIFX bulb at 450ms reads the frame for `now + 450ms` and sends it now — it arrives 450ms later, exactly on time. A 5ms OpenRGB device reads the frame for `now + 5ms`.

**Failure isolation:** Each device task has independent error handling. A device send timeout logs and retries; it never blocks other devices. Uses `asyncio.TaskGroup` for lifecycle management.

**Files:**
- `scheduler.py` — ring buffer, per-device dispatch tasks

### 5. Device Abstraction (`devices/`)

Adapter pattern for vendor-agnostic device control.

**DeviceAdapter protocol:**
```python
class DeviceAdapter(Protocol):
    @property
    def device_info(self) -> DeviceInfo: ...

    @property
    def is_connected(self) -> bool: ...

    @property
    def led_count(self) -> int: ...

    async def connect(self) -> None: ...
    async def disconnect(self) -> None: ...
    async def send_frame(self, colors: np.ndarray) -> None: ...

    @staticmethod
    async def discover() -> list[DeviceInfo]: ...
```

**DeviceInfo** (canonical definition in `types.py`, imported by all device modules):
```python
@dataclass
class DeviceInfo:
    name: str
    device_type: str        # "openrgb", "lifx", "govee"
    led_count: int
    address: str            # host:port or identifier
```

**OpenRGB adapter (MVP):**
- Uses `openrgb-python` library
- All calls wrapped in `asyncio.to_thread()` (library is synchronous TCP)
- `send_frame()` uses `set_color()` with `fast=True` to skip state verification
- Discovery via OpenRGB SDK device enumeration

**DeviceManager:**
- Orchestrates discovery, connection, reconnection
- Periodic rediscovery for hot-plugged devices
- Marks failed devices as disconnected, attempts periodic reconnection
- Does not block healthy devices when one fails

**Files:**
- `adapter.py` — DeviceAdapter protocol (imports DeviceInfo from types.py)
- `openrgb.py` — OpenRGB adapter implementation
- `manager.py` — discovery, lifecycle, reconnection

### 6. Latency System (`latency/`)

Per-device latency measurement with swappable strategies.

**ProbeStrategy protocol:**
```python
class ProbeStrategy(Protocol):
    def update(self, new_sample: float) -> None: ...
    def get_latency(self) -> float: ...
    def reset(self) -> None: ...
```

**Strategies:**

| Strategy | Behavior | Best for |
|----------|----------|----------|
| `StaticLatency` | Fixed value, no probing | Local/USB devices (OpenRGB) |
| `EMALatency` | Exponential moving average, outlier rejection (>2σ) | Stable network devices |
| `WindowedMeanLatency` | Averages N samples, resets each window | WiFi devices, shifting conditions |

**LatencyTracker (per device):**
- `strategy: ProbeStrategy` — swappable at runtime or via config
- `manual_offset: float` — user-configurable tweak (ms)
- `probe_interval: float` — seconds between probes (default 30s)
- `effective_latency = strategy.get_latency() + manual_offset`
- On connect: initial burst of 5 probes (for non-static strategies)
- Periodic: re-probe every `probe_interval` seconds

**OpenRGB probing (MVP):** Use `StaticLatency` with a configurable default of 10ms. OpenRGB has no echo/ack mechanism for measuring physical LED response time. TCP round-trip only measures network, not LED driver latency.

**Files:**
- `tracker.py` — LatencyTracker
- `strategies.py` — StaticLatency, EMALatency, WindowedMeanLatency

### 7. Application Coordinator (`main.py`)

Orchestrates startup, shutdown, and cross-component wiring.

**Startup sequence:**
1. Load TOML config
2. Initialize event bus
3. Discover network interface (or use configured)
4. Start ProDJLink listener (or BeatSimulator in demo mode)
5. Initialize BeatClock, wire to listener
6. Discover devices via DeviceManager
7. Connect devices, initialize LatencyTrackers
8. Start EffectEngine with active effect
9. Start LookaheadScheduler with connected devices
10. Log system status

**Shutdown (SIGINT/SIGTERM):**
1. Stop scheduler
2. Stop effect engine
3. Disconnect all devices
4. Close UDP sockets
5. Log final status

**Graceful degradation:**
- No DJ Link traffic: wait and scan periodically, log status
- DJ Link lost: BeatClock coasts at last BPM for 2s, then stops
- Device disconnect: scheduler task logs error, DeviceManager retries connection
- All devices gone: effect engine optionally pauses rendering
- OpenRGB server not running: discovery returns empty, periodic retry

### 8. Event Bus (`events.py`)

Simple typed callback system for cross-component notifications.

**Events:**
- `BeatEvent(bpm, beat_position, timestamp)`
- `PlayerStateChanged(player_id, is_playing)`
- `DeviceConnected(device_info)`
- `DeviceDisconnected(device_info, reason)`
- `BPMChanged(old_bpm, new_bpm)`

Components subscribe to events they care about. Lightweight — just a dict of event type → list of callbacks.

**Execution model:** Event callbacks are invoked synchronously in the emitter's coroutine context. Callbacks MUST be non-blocking (no I/O, no awaiting, complete in <1ms). For subscribers that need to do async work (e.g., logging a device disconnect to a file), the callback should schedule an async task via `asyncio.get_event_loop().create_task()` rather than doing the work inline. This ensures the beat processing hot path is never blocked by a slow subscriber.

**Data flow clarification:** The hot path (BeatClock reads → effect render → frame dispatch) uses direct synchronous method calls for minimum latency. The event bus is for notifications about state changes (BPM changed, device connected/disconnected, player state) that are not on the frame-by-frame hot path.

### 9. System Status (`status.py`)

Tracks health of all subsystems for logging and future UI.

```python
@dataclass
class SystemStatus:
    prodjlink_connected: bool
    active_player_count: int
    current_bpm: float | None
    connected_devices: list[str]
    device_errors: dict[str, str]
    buffer_fill_level: float
    avg_frame_render_time_ms: float
```

Periodic log summary (every 10s at INFO level).

### 10. Configuration (`config.py`)

TOML-based configuration with dataclass validation. Uses stdlib `tomllib` (Python 3.11+).

```toml
[network]
interface = "auto"

[prodjlink]
passive_mode = true

[engine]
fps = 60
max_lookahead_ms = 1000

[effect]
active = "beat_pulse"

[effect.beat_pulse]
palette = ["#ff0000", "#00ff00", "#0000ff", "#ffff00"]
gamma = 2.0

[devices.openrgb]
enabled = true
host = "127.0.0.1"
port = 6742
latency_strategy = "static"
latency_ms = 10
manual_offset_ms = 0
```

All values have sensible defaults. Config file is optional — app runs with defaults.

**Validation:** Invalid config aborts startup with a clear error message listing all validation failures (missing keys, wrong types, out-of-range values). Uses dataclass `__post_init__` for validation.

**OpenRGB port:** Must match the user's OpenRGB server configuration (6742 is the SDK default).

**Network auto-detection:** When `interface = "auto"`, the app listens on all available non-loopback interfaces for Pro DJ Link broadcast traffic (magic header on port 50001) with a 10-second timeout. If no traffic is found, it logs a warning and retries every 30 seconds. The user can skip auto-detection by specifying an interface name explicitly.

### 11. Shared Types (`types.py`)

Shared dataclasses and type aliases used across modules to avoid circular imports. This is the **canonical location** for all cross-module types.

- `RGB = tuple[int, int, int]`
- `DeviceInfo` — device metadata (name, type, LED count, address)
- `RenderedFrame` — timestamped LED color array for the ring buffer
- `BeatState` — snapshot of BeatClock state (phase, BPM, is_playing)

### 12. Metrics / Observability

For debugging beat-sync quality. MVP: periodic log lines.

**Tracked metrics:**
- Phase error at each beat packet resync
- Frame render time (ms)
- Device send latency per frame
- Ring buffer fill level
- Dropped frames (if render falls behind)

Logged every 10s as a summary line at INFO. Per-frame data at TRACE level only.

**Logging discipline (default production log level: INFO):**
- `logger.trace()` — per-frame data (only active when log level explicitly set to TRACE via config or CLI flag `--log-level TRACE`)
- `logger.debug()` — per-beat data, device sends
- `logger.info()` — state changes, periodic status, startup/shutdown
- `logger.warning()` — device disconnect, network issues, drift > threshold
- `logger.error()` — unrecoverable failures

## Project Structure

```
dj-ledfx/
├── pyproject.toml
├── config.example.toml
├── src/
│   └── dj_ledfx/
│       ├── __init__.py
│       ├── __main__.py              # uv run -m dj_ledfx
│       ├── main.py                  # Application coordinator
│       ├── config.py                # TOML config loading + dataclass models
│       ├── types.py                 # RGB, DeviceInfo, RenderedFrame, BeatState
│       ├── events.py                # Typed event bus
│       ├── status.py                # SystemStatus, periodic health logging
│       │
│       ├── prodjlink/
│       │   ├── __init__.py
│       │   ├── listener.py          # Passive UDP listener (port 50001)
│       │   ├── packets.py           # Binary packet parsing (struct)
│       │   └── constants.py         # Packet types, offsets, magic bytes
│       │
│       ├── beat/
│       │   ├── __init__.py
│       │   ├── clock.py             # BeatClock — interpolation, drift correction
│       │   └── simulator.py         # BeatSimulator for demo/testing
│       │
│       ├── effects/
│       │   ├── __init__.py
│       │   ├── engine.py            # 60fps render loop, ring buffer writes
│       │   ├── base.py              # Effect ABC
│       │   └── beat_pulse.py        # MVP BeatPulse effect
│       │
│       ├── scheduling/
│       │   ├── __init__.py
│       │   └── scheduler.py         # Timestamped ring buffer, per-device dispatch
│       │
│       ├── devices/
│       │   ├── __init__.py
│       │   ├── adapter.py           # DeviceAdapter protocol
│       │   ├── openrgb.py           # OpenRGB adapter (asyncio.to_thread wrapping)
│       │   └── manager.py           # Discovery, lifecycle, reconnection
│       │
│       └── latency/
│           ├── __init__.py
│           ├── tracker.py           # LatencyTracker (strategy + manual offset)
│           └── strategies.py        # StaticLatency, EMALatency, WindowedMeanLatency
│
└── tests/                           # Strategy: unit tests use mocked devices and
    │                                # captured packet fixtures. Integration tests
    │                                # verify full pipeline from BeatSimulator
    │                                # through to a mock DeviceAdapter.
    ├── conftest.py                  # Shared fixtures
    ├── fixtures/                    # Captured packet hex dumps from XDJ-AZ
    ├── prodjlink/
    │   ├── test_packets.py
    │   └── test_listener.py
    ├── beat/
    │   └── test_clock.py
    ├── effects/
    │   └── test_engine.py
    ├── scheduling/
    │   └── test_scheduler.py
    ├── devices/
    │   └── test_openrgb.py
    └── latency/
        └── test_strategies.py
```

## Dependencies

**Runtime:**
- `openrgb-python` — OpenRGB SDK client
- `numpy` — array math for effects
- `loguru` — structured logging

**Dev:**
- `pytest` — testing
- `pytest-asyncio` — async test support
- `ruff` — linting and formatting
- `mypy` — static type checking

## Tooling

- `uv` for all package management: `uv init`, `uv add`, `uv run`
- `ruff` for linting (replaces flake8/isort/black) and formatting
- `mypy` for static type checking (strict mode)
- `loguru` for all logging (never stdlib `logging`)

## Future Roadmap (post-MVP)

1. **Active virtual CDJ mode** — keepalive handshake, player status, play/pause detection
2. **Waveform retrieval** — dbserver/NFS, WaveformHD with RGB frequency data
3. **Phrase detection** — intro/verse/chorus/bridge/outro boundaries for auto-switching effects
4. **Track metadata** — genre, energy, key to influence effect selection
5. **Multi-effect routing** — different effects on different lights
6. **LIFX adapter** — direct LAN control with EMA/Windowed latency probing
7. **Govee adapter** — LAN API control
8. **3D scene mapping** — floor plan/photo/3D scan upload, place lights in space
9. **Spatial effects** — waves, sweeps, gradients respecting 3D positioning
10. **AI-driven effects** — automatic effect selection/generation from track analysis
11. **Web UI** — configuration, visualization, effect preview
12. **GPU acceleration** — Taichi Lang for complex spatial effects at scale
