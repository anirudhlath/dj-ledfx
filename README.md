# dj-ledfx

Beat-synced LED lighting engine driven by Pioneer Pro DJ Link. A passive UDP listener picks beat packets straight off the DJ booth network, a 60 fps effect engine renders frames ahead of time into a future-frame ring buffer, and a lookahead scheduler sends each device the frame that matches its measured latency — so USB peripherals (~5 ms), LIFX (~50 ms), and Govee (~100 ms) fixtures all hit the beat together. Ships with a FastAPI + WebSocket backend, a React control UI with a three.js 3D scene editor, and Prometheus/Grafana monitoring.

## How it works

```
CDJ/XDJ decks ──UDP:50001──▶ Pro DJ Link listener ──▶ BeatClock (phase interpolation)
                                                              │
                     ring buffer of FUTURE frames ◀── 60 fps effect engine
                                                              │
                LookaheadScheduler — per-device send loops pick the frame at
                now + device_latency (static / EMA / windowed-mean strategies)
                                                              │
                        OpenRGB · LIFX LAN · Govee LAN adapters
```

The key idea: the ring buffer stores *future* frames. The engine renders at `now + max_lookahead`; each device's send loop picks the frame at `now + device_latency`, so higher-latency devices simply read further into the future.

## Features

- **Passive Pro DJ Link listener** — parses broadcast beat packets on UDP 50001 with no virtual-CDJ handshake. BPM is pitch-adjusted (`track_bpm * (1 + pitch/100)`) and the BeatClock applies drift correction (soft-correct under 5 ms, hard snap above). Currently supports CDJ-3000-generation beat packets.
- **60 fps effect engine** — effects are pure-NumPy render functions behind an auto-registry, with a hot-swappable effect deck, runtime-introspectable parameters, and TOML presets. Built-in effects: beat_pulse, breathe, color_chase, fire_storm, rainbow_wave, strobe.
- **Per-device latency compensation** — per-device send loops run at each device's natural FPS; latency is estimated by static, EMA, or windowed-mean strategies, seeded with device-type heuristics.
- **Device adapters** — OpenRGB (USB/desktop RGB), LIFX LAN (bulbs, strips, tile chains), Govee LAN (UDP segment control with SKU registry). Discovery orchestrator with multi-wave scanning, fast reconnect, and ghost placeholders for offline devices.
- **Multi-scene 3D spatial mapping** — place devices in 3D space, map effects spatially (linear/radial), and run independent scene pipelines with conflict detection.
- **Web control** — FastAPI REST + WebSocket backend (binary LED frame broadcast) with a React 19 + TypeScript UI: live performance view, effect deck, transport controls, device monitor, and a react-three-fiber 3D scene editor.
- **Persistence** — SQLite state DB as the runtime source of truth, with TOML import/export and debounced writes.
- **Observability** — Prometheus metrics with a ready-made Grafana dashboard, plus py-spy and VizTracer profiling modes.
- **Demo mode** — built-in beat simulator; run the whole stack with no DJ hardware.

## Quick Start

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run -m dj_ledfx --demo          # Simulated beats (no DJ hardware)
uv run -m dj_ledfx                  # Pro DJ Link listener mode
```

Configuration starts from `config.toml` (see `config.example.toml`; override with `--config <path>`). Once the app has run, runtime state lives in the SQLite `state.db` and TOML becomes an import/export format.

### Web UI

```bash
uv sync --extra web
cd frontend && npm install && npm run build && cd ..
uv run -m dj_ledfx --demo --web        # Serve the built frontend
uv run -m dj_ledfx --demo --web dev    # Hot-reload dev server (frontend + backend)
```

For frontend-only development: `cd frontend && npm run dev` (proxies API/WS to `:8080`).

## Monitoring

Real-time Prometheus metrics and Grafana dashboard.

### Enable metrics

```bash
uv run -m dj_ledfx --metrics --demo        # Metrics on default port 9091
uv run -m dj_ledfx --metrics --metrics-port 8080 --demo  # Custom port
```

> **Note:** If port 9091 is already in use by another process, use `--metrics-port` to pick a different port and update `monitoring/prometheus.yml` targets to match.

Exposes a `/metrics` endpoint with:

| Metric | Type | Description |
|--------|------|-------------|
| `ledfx_render_duration_seconds` | Histogram | Frame render time |
| `ledfx_render_fps` | Gauge | Target render FPS |
| `ledfx_frames_rendered_total` | Counter | Total frames rendered |
| `ledfx_frames_dropped_total` | Counter | Frames dropped per device |
| `ledfx_device_send_duration_seconds` | Histogram | Device send time |
| `ledfx_device_fps` | Gauge | Target device FPS |
| `ledfx_device_latency_seconds` | Gauge | Effective device latency |
| `ledfx_beat_bpm` | Gauge | Current BPM |
| `ledfx_beat_phase` | Gauge | Beat phase (0-1) |
| `ledfx_beats_received_total` | Counter | Total beat events |
| `ledfx_ring_buffer_depth` | Gauge | Ring buffer fill (0-1) |
| `ledfx_event_loop_lag_seconds` | Histogram | Event loop scheduling lag |

### Grafana dashboard

```bash
# One-time setup (macOS)
./scripts/setup-monitoring.sh

# Start the stack
prometheus --config.file=monitoring/prometheus.yml --log.level=warn &>/dev/null &
brew services start grafana
uv run -m dj_ledfx --metrics --demo
```

Then in Grafana:

1. Open http://localhost:3000 (default credentials: admin / admin)
2. Add Prometheus datasource: **Connections → Data sources → Add → Prometheus**, set URL to `http://localhost:9090`, click **Save & test**
3. Import dashboard: **Dashboards → Import → Upload JSON file**, select `monitoring/grafana-dashboard.json`

> **Note:** Device discovery takes ~15s (Govee 5s + LIFX 10s). Grafana panels will populate after discovery completes and Prometheus scrapes a few times.

See [monitoring/README.md](monitoring/README.md) for details.

## Profiling

### Sampling profiler (py-spy)

Captures a low-overhead CPU profile viewable in [Speedscope](https://www.speedscope.app/):

```bash
# Install py-spy first (optional dependency)
uv pip install py-spy

# Requires root on macOS (SIP restriction)
sudo uv run -m dj_ledfx --profile --demo
# Ctrl-C to stop — profile saved to profiles/profile-<timestamp>.json
```

`--profile` defaults to `sampling` mode.

### Deep profiler (VizTracer)

Captures function-level traces viewable in [Perfetto](https://ui.perfetto.dev/):

```bash
uv run -m dj_ledfx --profile deep --demo
# Ctrl-C to stop — profile saved to profiles/profile-<timestamp>.json
```

Deep mode traces all function calls in `dj_ledfx/` with >50us duration. Use for investigating specific timing issues — higher overhead than sampling.

## Development

```bash
uv run pytest                    # Test suite (pytest + pytest-asyncio, ~10k lines of tests)
uv run ruff check .              # Lint
uv run ruff format .             # Format
uv run mypy src/                 # Type check (strict mode)
cd frontend && npx tsc --noEmit  # Frontend type check
```

The Python codebase is typed end-to-end under `mypy --strict`; all device I/O is async on a single event loop.
