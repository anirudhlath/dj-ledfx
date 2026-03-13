# Profiling & Real-Time Monitoring Design

**Date**: 2026-03-13
**Status**: Draft

## Overview

Add comprehensive profiling and real-time monitoring to dj-ledfx to visualize performance bottlenecks and understand system behavior. Two profiling modes (sampling and deep tracing) behind a single `--profile` CLI flag, plus a Prometheus/Grafana metrics stack behind `--metrics`.

## Goals

- Interactive flame charts for offline analysis of call stacks and time distribution
- Real-time Grafana dashboard for live performance monitoring
- Near-zero overhead when profiling is enabled (sampling mode)
- Zero overhead when profiling/metrics are disabled (no-op pattern)

## Non-Goals

- Production continuous profiling (Pyroscope-style)
- Memory profiling (Scalene-style)
- Distributed tracing (OpenTelemetry)

---

## CLI Interface

```
uv run -m dj_ledfx --profile           # py-spy sampling (~0.1% overhead)
uv run -m dj_ledfx --profile deep      # VizTracer function tracing (accepts ~8-10% overhead)
uv run -m dj_ledfx --metrics           # Prometheus metrics endpoint on :9090
uv run -m dj_ledfx --metrics-port 8080 # Custom metrics port
```

All flags are composable (e.g., `--profile --metrics --demo`).

Output files are written to `profiles/` directory (gitignored), named `profile-<timestamp>.json`.

---

## Component 1: py-spy Sampling Profiler (`--profile`)

**Tool**: py-spy — out-of-process sampling profiler that reads CPython VM memory without injecting into the target process.

**Mechanism**: The `__main__.py` entry point detects `--profile` in `sys.argv` and re-executes itself under `py-spy record`. This means py-spy wraps the entire process lifecycle with zero code changes to the application.

**Re-exec flow**:
1. `__main__.py` checks for `--profile` (but not `--profile deep`) in `sys.argv`
2. Strips `--profile` from args
3. Ensures `profiles/` directory exists
4. Execs: `py-spy record --format speedscope -o profiles/profile-<timestamp>.json -- uv run -m dj_ledfx <remaining args>`
5. On shutdown, prints the output path to stdout

**Output**: Speedscope JSON, opened interactively at [speedscope.app](https://www.speedscope.app/) (local file, no upload).

**Overhead**: ~0.1% — safe to use during normal operation without affecting 60fps render loop.

**macOS note**: py-spy may require `sudo` or SIP configuration. The re-exec prints a helpful error message if permission is denied.

---

## Component 2: VizTracer Deep Profiler (`--profile deep`)

**Tool**: VizTracer — function-level tracer with native async support. Uses `sys.monitoring` on Python 3.12+ for lower overhead.

**Mechanism**: Programmatic API wrapping the `_run()` coroutine in `main.py`.

**Configuration**:
- `tracer_entries`: 1,000,000 (circular buffer, ~80MB)
- `include_files`: only `dj_ledfx/` module (excludes stdlib, numpy internals)
- `min_duration`: 50 microseconds (filters noise from trivial calls)
- `log_async`: True (visualizes coroutines on separate lanes)

**Integration in main.py**:
```python
if args.profile == "deep":
    from viztracer import VizTracer
    tracer = VizTracer(
        tracer_entries=1_000_000,
        include_files=["*/dj_ledfx/*"],
        min_duration=50,
        log_async=True,
    )
    tracer.start()
    try:
        asyncio.run(_run(args))
    finally:
        tracer.stop()
        tracer.save(f"profiles/profile-{timestamp}.json")
```

**Output**: Chrome Trace Event JSON, loadable in [Perfetto UI](https://ui.perfetto.dev/). Shows coroutine interleaving, async task scheduling, and exact call sequences.

**Overhead**: ~8-10%. Will cause frame drops at 60fps. Intended for targeted debugging sessions, not everyday use.

---

## Component 3: Prometheus Metrics (`--metrics`)

### Metrics Definitions

| Metric | Type | Labels | Source |
|--------|------|--------|--------|
| `ledfx_render_duration_seconds` | Histogram | — | EffectEngine.tick() |
| `ledfx_render_fps` | Gauge | — | EffectEngine (computed) |
| `ledfx_frames_rendered_total` | Counter | — | EffectEngine |
| `ledfx_frames_dropped_total` | Counter | `device` | LookaheadScheduler |
| `ledfx_device_send_duration_seconds` | Histogram | `device` | Scheduler send loop |
| `ledfx_device_fps` | Gauge | `device` | Scheduler (computed) |
| `ledfx_device_latency_seconds` | Gauge | `device` | Latency strategy |
| `ledfx_beat_bpm` | Gauge | — | BeatClock |
| `ledfx_beat_phase` | Gauge | — | BeatClock |
| `ledfx_beats_received_total` | Counter | — | Event bus |
| `ledfx_ring_buffer_depth` | Gauge | — | RingBuffer |
| `ledfx_event_loop_lag_seconds` | Histogram | — | Event loop lag task |

### Event Loop Lag Measurement

A lightweight asyncio task schedules itself every 100ms via `loop.call_later()`. The delta between expected and actual wakeup time is observed as event loop lag. This is the single most important metric — it tells you if anything is blocking the loop.

### metrics.py Module

New file: `src/dj_ledfx/metrics.py`

Owns all metric definitions. Exposes an `init(enabled: bool, port: int)` function called from `main.py`.

**No-op pattern**: When `--metrics` is not passed, all metric objects are replaced with lightweight no-op stubs that share the same `.observe()`, `.inc()`, `.set()` interface. No conditional checks in hot paths.

```python
class _NoOpMetric:
    def observe(self, v: float) -> None: ...
    def inc(self, v: float = 1) -> None: ...
    def set(self, v: float) -> None: ...
    def labels(self, **kw: str) -> "_NoOpMetric": return self

if enabled:
    RENDER_DURATION = Histogram("ledfx_render_duration_seconds", ...)
else:
    RENDER_DURATION = _NoOpMetric()
```

**HTTP server**: `prometheus_client.start_http_server(port)` runs in a daemon thread — never touches the asyncio event loop.

### Instrumented Files

| File | Change |
|------|--------|
| `__main__.py` | py-spy re-exec logic when `--profile` is passed |
| `main.py` | Parse `--profile`, `--metrics`, `--metrics-port`. Init metrics. VizTracer wrap. Event loop lag task. |
| `metrics.py` | **New**. All metric definitions + no-op stubs + `init()` |
| `effects/engine.py` | 2 lines: import + `RENDER_DURATION.observe(dt)` in existing timing code |
| `scheduling/scheduler.py` | ~4 lines: import + observe send duration, inc dropped frames, set device FPS |
| `beat/clock.py` | 2 lines: import + `BEAT_BPM.set()` on beat update |
| `events.py` | 1 line: `BEATS_RECEIVED.inc()` in beat event dispatch |
| `status.py` | 2 lines: set ring buffer depth gauge |

---

## Component 4: Grafana & Prometheus Setup

### Setup Script

`scripts/setup-monitoring.sh` automates the full stack:

1. Checks for `brew`, installs `prometheus` and `grafana` if missing
2. Generates `monitoring/prometheus.yml` scrape config targeting `localhost:9090` every 5s
3. Drops a pre-built Grafana dashboard JSON into `monitoring/grafana-dashboard.json`
4. Prints start/stop instructions

### Directory Structure

```
monitoring/
├── prometheus.yml              # Prometheus scrape config
├── grafana-dashboard.json      # Pre-built dj-ledfx dashboard
└── README.md                   # Quick-start instructions
scripts/
└── setup-monitoring.sh         # One-time setup
```

### Grafana Dashboard Layout

- **Row 1**: Render FPS (gauge panel), Event Loop Lag (timeseries), Beat BPM (stat panel)
- **Row 2**: Render Duration (heatmap), Frame Drop Rate (timeseries)
- **Row 3**: Per-device Send Duration (timeseries), Per-device FPS (timeseries), Per-device Latency (timeseries)

### Running the Stack

```bash
./scripts/setup-monitoring.sh                    # One-time install + config
prometheus --config.file=monitoring/prometheus.yml &
brew services start grafana                      # Grafana on :3000
uv run -m dj_ledfx --metrics --demo             # App with metrics
```

Import `monitoring/grafana-dashboard.json` via Grafana UI (or the setup script provisions it via Grafana HTTP API).

---

## Dependencies

### Python (added to pyproject.toml)

| Package | Purpose | Install group |
|---------|---------|---------------|
| `prometheus-client` | Metrics collection + HTTP server | main (required for no-op import) |
| `py-spy` | Sampling profiler | dev optional |
| `viztracer` | Function-level tracer | dev optional |

**Note**: `prometheus-client` is a main dependency because the no-op pattern requires the module to be importable. The actual HTTP server only starts when `--metrics` is passed. Alternatively, make it optional and guard the import — but given it's a lightweight pure-Python package, keeping it as a main dep is simpler.

### External (via brew)

| Tool | Purpose |
|------|---------|
| `prometheus` | Time-series database, scrapes `/metrics` |
| `grafana` | Dashboard visualization |

---

## Testing

- **Unit test**: Import `metrics` module without enabling, call `.observe()` / `.inc()` / `.set()` on no-op stubs — verify no crash
- **Unit test**: Import `metrics` module with enabling, verify metric objects are real `prometheus_client` types
- **Integration test**: Run app with `--metrics`, HTTP GET `localhost:9090/metrics`, verify expected metric names in Prometheus exposition format
- **No profiling tests**: py-spy and VizTracer are external tools; their correctness is their own concern. We test only that our CLI flag parsing and re-exec logic work.

---

## File Inventory

### New Files
- `src/dj_ledfx/metrics.py`
- `scripts/setup-monitoring.sh`
- `monitoring/prometheus.yml`
- `monitoring/grafana-dashboard.json`
- `monitoring/README.md`

### Modified Files
- `src/dj_ledfx/__main__.py`
- `src/dj_ledfx/main.py`
- `src/dj_ledfx/effects/engine.py`
- `src/dj_ledfx/scheduling/scheduler.py`
- `src/dj_ledfx/beat/clock.py`
- `src/dj_ledfx/events.py`
- `src/dj_ledfx/status.py`
- `pyproject.toml`
- `.gitignore` (add `profiles/`)
