# dj-ledfx

Beat-synced LED effect engine driven by Pro DJ Link network data with per-device latency compensation.

## Superpowers Skill Guidelines

- Use opus with max effort from brainstorming and planning.
- Use /executing-plans skill for executing the plan.
- Use sonnet or opus for implementing the plan.
- Use opus for reviewing and simplification stages.
- Use haiku for committing.
- Prefer latest internet grounded knowledge over training knowledge.
- Use context7 to check latest docs and for external dependencies.
- Add code architect review step as a task for each plan you implement. Fix every issue that comes up during the code architect review step.
- Add /simplify skill step as a task for each plan you implement. Fix every issue that comes up during the simplify step.
- Add claude md skill as a task to improve and revise claude context, memories etc.
- Finally create a PR with the changes.


## Commands

```bash
uv sync                          # Install dependencies
uv sync --extra web              # Install with web UI extras
uv run -m dj_ledfx              # Run the app
uv run -m dj_ledfx --demo       # Run with simulated beats (no DJ hardware)
uv run -m dj_ledfx --demo --web # Run with web UI (requires: uv sync --extra web)
uv run -m dj_ledfx --demo --web dev  # Run with hot-reload dev server (frontend + backend)
uv run pytest                    # Run tests
uv run pytest -x -v              # Run tests, stop on first failure
uv run ruff check .              # Lint
uv run ruff format .             # Format
uv run mypy src/                 # Type check
cd frontend && npm run build     # Build frontend static assets
cd frontend && npx tsc --noEmit  # TypeScript type check
cd frontend && npm run dev       # Frontend dev server (proxies to :8080)
```

## Architecture

src/dj_ledfx/ layout:
- `prodjlink/` — Pro DJ Link UDP protocol (passive listener on port 50001)
- `beat/` — BeatClock phase interpolation + BeatSimulator for demo mode
- `transport.py` — TransportState enum (stopped/playing/simulating) — engine and scheduler gate on this
- `effects/` — Effect ABC + 60fps render engine writing future frames to ring buffer
- `effects/color.py` — Color math: hex/RGB conversion, HSV→RGB vectorized, palette interpolation
- `effects/easing.py` — Easing functions: lerp, ease_in/out, sine_ease
- `effects/energy.py` — BPM→energy mapping (0-1 linear between 100-150 BPM)
- `scheduling/` — LookaheadScheduler: per-device send loops with FrameSlot depth-1 slots, FPS cap, RTT measurement
- `metrics.py` — Contextmanager-based timing metrics for performance measurement
- `devices/` — DeviceAdapter ABC + OpenRGB adapter (asyncio.to_thread wrapped) + device-type heuristics
- `devices/backend.py` — DeviceBackend ABC for protocol-level adapters
- `devices/govee/` — Govee WiFi LED protocol (UDP segment control, SKU registry, transport)
- `devices/lifx/` — LIFX LAN protocol (bulb/strip/tile discovery, packet encoding, transport)
- `latency/` — ProbeStrategy protocol + StaticLatency/EMA/WindowedMean strategies
- `config.py` — Nested dataclass config (EngineConfig, EffectConfig, NetworkConfig, WebConfig, DevicesConfig) with load/save via tomllib/tomli_w
- `effects/params.py` — EffectParam descriptor for runtime introspection
- `effects/registry.py` — Effect auto-registry via __init_subclass__, get_effect_classes/schemas/create
- `effects/deck.py` — EffectDeck hot-swap wrapper (shared between engine and web API)
- `effects/presets.py` — PresetStore with TOML persistence
- `devices/manager.py` — DeviceManager: discovery, lifecycle, group management
- `web/` — FastAPI app factory, REST routers (effects, devices, config, scene), WebSocket hub, Pydantic schemas
- `web/ws.py` — WebSocket hub: binary LED frame broadcast (2-byte name + 4-byte seq + RGB), beat/status/transport JSON channels, EventBus-driven transport broadcast
- `web/router_transport.py` — Transport REST endpoints (GET/PUT /api/transport)
- `web/state.py` — Shared app state dataclass passed via FastAPI app.state
- `web/router_scene.py` — Scene REST endpoints (placement CRUD, mapping config, auto-creates SceneModel)
- `spatial/mapping.py` — mapping_from_config() shared factory for LinearMapping/RadialMapping
- `spatial/compositor.py` — Spatial compositor for multi-device LED frame distribution
- `spatial/geometry.py` — 3D geometry utilities for spatial calculations
- `spatial/scene.py` — SceneModel: device placements, spatial configuration
- `types.py` — Canonical location for all shared types (RGB, DeviceInfo, RenderedFrame, BeatState, DeviceStats)
- `events.py` — Typed callback event bus (sync, non-blocking callbacks only) + TransportStateChangedEvent
- `persistence/` — SQLite-backed state persistence (state_db.py, toml_io.py, debounced_writer.py, migrations/)
- `devices/discovery.py` — DiscoveryOrchestrator: multi-wave scanning, fast reconnect, ghost promote/demote
- `devices/ghost.py` — GhostAdapter: placeholder for offline devices (is_connected=False, send_frame no-op)
- `status.py` — SystemStatus health tracking
- `main.py` — Application coordinator (startup/shutdown orchestration)

frontend/ (Vite + React 19 + TypeScript + shadcn/ui + Tailwind CSS v4):
- `src/lib/ws-client.ts` — Multiplexed WS client with reconnection
- `src/lib/api-client.ts` — Typed REST client
- `src/hooks/` — React hooks for beat, effects, devices, scene state
- `src/pages/` — Views: Live Performance, Devices, Config, Scene (3D editor)
- `src/components/` — transport-section, effect-deck, device-monitor (Live page); scene/ (3D editor)
- `src/components/scene/` — R3F scene editor: viewport, device meshes, mapping helpers, bounds box, panels

## Code Style

- Use `uv` for everything (never pip, never poetry)
- Use `loguru` for all logging (never stdlib logging)
- Use `ruff` for linting and formatting
- Use `mypy` strict mode for type checking
- All device I/O must be async. Synchronous libs (openrgb-python) wrapped in `asyncio.to_thread()`
- Effect render signature is `render(self, ctx: BeatContext, led_count: int)` — BeatContext bundles beat_phase, bar_phase, bpm, dt
- New effects must: import in `effects/__init__.py` to trigger auto-registry via `__init_subclass__`
- Use shared utilities from `effects/color.py` (hex_to_rgb, rgb_to_hex, hsv_to_rgb_array, palette_lerp) and `effects/easing.py`
- Effect render methods are synchronous (pure numpy math, no I/O)
- BeatClock read methods are synchronous and lock-free (called from render loop)
- BeatClock write method is `on_beat(bpm, beat_number, next_beat_ms, timestamp, ...)` (not `update()`)
- DeviceAdapter is ABC (abstract base class). ProbeStrategy remains Protocol. Always code to the interface.
- All components run on a single asyncio event loop — no cross-thread state access
- AppConfig uses nested dataclasses: `config.engine.fps`, `config.devices.openrgb.host` (not flat)
- EffectEngine accepts `deck: EffectDeck` (not raw `effect: Effect`)
- Frontend uses shadcn/ui components (based on @base-ui/react, NOT Radix — different APIs)
- Frontend hooks in `src/hooks/`, one per domain (use-beat, use-devices, use-effects, use-scene, use-transport)
- WebSocket binary frame protocol: 2-byte name length, UTF-8 name, 4-byte sequence, then RGB bytes

## Key Design Decisions

- Ring buffer stores FUTURE frames. High-latency devices read newer (further-future) frames.
- Effect engine renders at `now + max_lookahead`. Scheduler picks frame at `now + device_latency`.
- Frame data must be copied before passing to device threads (race condition prevention).
- Passive Pro DJ Link mode for MVP (no virtual CDJ handshake needed for beat packets).
- BeatClock drift correction: soft correct if <5ms, hard snap if >=5ms.
- BPM must always be pitch-adjusted: `track_bpm * (1 + pitch/100)`.
- `is_playing` inferred from packet flow in passive mode (no explicit play/pause signal).
- LED count is global (max across devices); adapters map/truncate to their actual count.
- Event bus callbacks must be non-blocking (<1ms). Async work uses `create_task()`.
- Per-device send loops: each device runs at its natural FPS (bounded by configurable cap). Distributor writes target_time floats to depth-1 FrameSlots — no numpy copies until actual send.
- Device-type heuristic latency: Govee WiFi=100ms, LIFX WiFi=50ms, USB=5ms. Seeds the latency strategy. OpenRGB adapters use heuristics permanently (supports_latency_probing=False).
- DeviceAdapter is ABC (not Protocol). Provides supports_latency_probing class attribute. discover() excluded from base — adapters own their own discovery.
- SQLite `state.db` is single source of truth at runtime; TOML is import/export format only
- Device identity: MAC-based `stable_id` for cross-session matching via `DeviceInfo.effective_id` (falls back to name)
- Web layer resolves display names → stable_ids before any DB write (placements, deletions)
- Multi-scene: scenes activate/deactivate independently; conflict detection prevents same device in two active scenes
- Ghost/promote/demote lifecycle: offline devices stay registered as GhostAdapters, get promoted when rediscovered
- Discovery `skip_ids` must exclude offline devices — otherwise ghosts can never be re-promoted
- Transport controls: app starts STOPPED, user must play. SIMULATING renders to web UI only (skips send_frame). Device state captured on connect (when stopped), restored on stop.
- DeviceAdapter provides default `capture_state()` (50% white) and `restore_state()` — adapters override as protocol support is added

## Logging Discipline

- Default production level: INFO
- TRACE: per-frame data (only with `--log-level TRACE`)
- DEBUG: per-beat data, device sends
- INFO: state changes, periodic status (every 10s), startup/shutdown
- WARNING: device disconnect, network issues, drift > threshold
- ERROR: unrecoverable failures
- Never log at INFO in the render loop hot path

## Testing

- Tests mirror src structure: `tests/prodjlink/`, `tests/beat/`, etc.
- Use `pytest-asyncio` for async tests
- Packet parsing tests use hex dump fixtures from `tests/fixtures/`
- Mock `openrgb-python` for device tests
- Integration tests run BeatSimulator → full pipeline → mock DeviceAdapter
- Web tests use `httpx.AsyncClient` with FastAPI's `TestClient` pattern
- `tests/web/` covers all REST routers and WebSocket hub
- Tests that call `engine.run()` or `scheduler.run()` must set `_resume_event.set()` first (STOPPED-by-default)

## Gotchas

- `openrgb-python` is synchronous TCP — MUST wrap in `asyncio.to_thread()` or it blocks the event loop
- XDJ-AZ is an all-in-one 4-deck unit — may send multi-deck beat data from a single device ID
- Beat packets on port 50001 are broadcast (free), but status packets on port 50002 require virtual CDJ registration
- Phase wraps from ~1.0 to ~0.0 at each beat — effects must handle this discontinuity
- Pro DJ Link requires binding to the correct network interface (not localhost)
- Ring buffer needs ~1s to warm up — high-latency devices get no frames until buffer fills to their latency depth
- Only CDJ-3000 generation packets (0x1F) supported in MVP; older hardware silently ignored
- R3F: `<threeLine>` is the correct intrinsic for THREE.Line (not `<line_>`) — crashes if wrong
- R3F: `useFrame` for live-updating geometry; drei `Line` component only updates on prop change via React state
- R3F: TransformControls `onChange` prop for live drag callbacks (not useEffect + ref — refs don't trigger effects)
- R3F: optimistic state updates needed when dragging 3D objects to avoid position jumps during API round-trips
- Config persistence: `dataclasses.asdict()` serializes field names as-is; `load_config` must match (e.g. `scene_config` not `scene`)
- Device adapter: use `managed.adapter.device_info.name` (not `managed.adapter.name`) to get device name
- SQLite: never use `INSERT OR REPLACE` on tables with FK cascades — it's `DELETE + INSERT`, silently wiping child rows. Use `INSERT ... ON CONFLICT DO UPDATE SET` instead
- SQLite: `executescript()` issues implicit COMMIT before running — breaks transactional migrations. Use manual `BEGIN`/`COMMIT` with individual `execute()` calls
- SQLite: single `asyncio.Lock` on StateDB protects the `sqlite3.Connection` object (not thread-safe despite `check_same_thread=False`), not DB-level locking
- Scheduler hot path: don't `list()` wrap `dict.values()` iteration — unnecessary allocation at 60fps on single event loop
- TOML serialization: use `json.dumps(v)` not `str(v)` for config values — `str(True)` produces `"True"` which fails `json.loads()` round-trip
- `close()` on StateDB must acquire the lock to prevent races with in-flight `to_thread` operations
- Engine/scheduler start STOPPED by default — tests that call `run()` must set `_resume_event.set()` or `set_transport_state(PLAYING)` first, otherwise they hang forever on `await _resume_event.wait()`
- `engine.stop()` must set `_resume_event` to unblock `run()` when transport is STOPPED — without this, stop() has no effect since the coroutine is blocked on the event wait
- numpy `np.clip(...).astype()` returns `Any` per mypy — use `# type: ignore[no-any-return]` (not `[return-value]`)
