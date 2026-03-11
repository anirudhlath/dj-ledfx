# dj-ledfx

Beat-synced LED effect engine driven by Pro DJ Link network data with per-device latency compensation.

## Workflow

- Use `/feature-dev` skill with **opus model** for all feature development
- Use `/superpowers:brainstorming` before any new feature design
- Use `/superpowers:writing-plans` to create implementation plans from specs
- Spec documents live in `docs/superpowers/specs/`

## Commands

```bash
uv run -m dj_ledfx              # Run the app
uv run -m dj_ledfx --demo       # Run with simulated beats (no DJ hardware)
uv run pytest                    # Run tests
uv run pytest -x -v              # Run tests, stop on first failure
uv run ruff check .              # Lint
uv run ruff format .             # Format
uv run mypy src/                 # Type check
```

## Architecture

src/dj_ledfx/ layout:
- `prodjlink/` — Pro DJ Link UDP protocol (passive listener on port 50001)
- `beat/` — BeatClock phase interpolation + BeatSimulator for demo mode
- `effects/` — Effect ABC + 60fps render engine writing future frames to ring buffer
- `scheduling/` — LookaheadScheduler: per-device latency-compensated frame dispatch
- `devices/` — DeviceAdapter protocol + OpenRGB adapter (asyncio.to_thread wrapped)
- `latency/` — ProbeStrategy protocol + StaticLatency/EMA/WindowedMean strategies
- `config.py` — TOML config loading (stdlib tomllib)
- `types.py` — Canonical location for all shared types (RGB, DeviceInfo, RenderedFrame, BeatState)
- `events.py` — Typed callback event bus (sync, non-blocking callbacks only)
- `status.py` — SystemStatus health tracking
- `main.py` — Application coordinator (startup/shutdown orchestration)

## Code Style

- Use `uv` for everything (never pip, never poetry)
- Use `loguru` for all logging (never stdlib logging)
- Use `ruff` for linting and formatting
- Use `mypy` strict mode for type checking
- All device I/O must be async. Synchronous libs (openrgb-python) wrapped in `asyncio.to_thread()`
- Effect render methods are synchronous (pure numpy math, no I/O)
- BeatClock read methods are synchronous and lock-free (called from render loop)
- Adapter pattern for devices and latency strategies — always code to the Protocol/ABC
- All components run on a single asyncio event loop — no cross-thread state access

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

## Gotchas

- `openrgb-python` is synchronous TCP — MUST wrap in `asyncio.to_thread()` or it blocks the event loop
- XDJ-AZ is an all-in-one 4-deck unit — may send multi-deck beat data from a single device ID
- Beat packets on port 50001 are broadcast (free), but status packets on port 50002 require virtual CDJ registration
- Phase wraps from ~1.0 to ~0.0 at each beat — effects must handle this discontinuity
- Pro DJ Link requires binding to the correct network interface (not localhost)
- Ring buffer needs ~1s to warm up — high-latency devices get no frames until buffer fills to their latency depth
- Only CDJ-3000 generation packets (0x1F) supported in MVP; older hardware silently ignored
