# dj-ledfx

Beat-synced LED effect engine driven by Pro DJ Link network data with per-device latency compensation.

## Quick Start

```bash
uv run -m dj_ledfx --demo          # Simulated beats (no DJ hardware)
uv run -m dj_ledfx                  # Pro DJ Link listener mode
```

## Profiling

### Sampling profiler (py-spy)

Captures a low-overhead CPU profile viewable in [Speedscope](https://www.speedscope.app/):

```bash
sudo uv run -m dj_ledfx --profile --demo
# Ctrl-C to stop — profile saved to profiles/profile-<timestamp>.json
```

`--profile` defaults to `sampling` mode. py-spy requires elevated permissions on macOS (SIP).

### Deep profiler (VizTracer)

Captures function-level traces viewable in [Perfetto](https://ui.perfetto.dev/):

```bash
uv run -m dj_ledfx --profile deep --demo
# Ctrl-C to stop — profile saved to profiles/profile-<timestamp>.json
```

Deep mode traces all function calls in `dj_ledfx/` with >50us duration. Use for investigating specific timing issues — higher overhead than sampling.

## Monitoring

Real-time Prometheus metrics and Grafana dashboard.

### Enable metrics

```bash
uv run -m dj_ledfx --metrics --demo        # Metrics on default port 9091
uv run -m dj_ledfx --metrics --metrics-port 8080 --demo  # Custom port
```

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
prometheus --config.file=monitoring/prometheus.yml &
brew services start grafana
uv run -m dj_ledfx --metrics --demo

# Open Grafana at http://localhost:3000 (admin/admin)
# Import monitoring/grafana-dashboard.json
```

See [monitoring/README.md](monitoring/README.md) for details.
