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
uv run -m dj_ledfx --profile deep      # VizTracer function tracing (accepts overhead, see note)
uv run -m dj_ledfx --metrics           # Prometheus metrics endpoint on :9091
uv run -m dj_ledfx --metrics-port 8080 # Custom metrics port
```

All flags are composable (e.g., `--profile --metrics --demo`).

Output files are written to `profiles/` directory (gitignored), named `profile-<timestamp>.json`.

**argparse definition**:
```python
parser.add_argument(
    "--profile",
    nargs="?",
    const="sampling",
    default=None,
    choices=["sampling", "deep"],
    help="Enable profiling: 'sampling' (default, py-spy) or 'deep' (VizTracer)",
)
parser.add_argument("--metrics", action="store_true", help="Enable Prometheus metrics endpoint")
parser.add_argument("--metrics-port", type=int, default=9091, help="Prometheus metrics port (default: 9091)")
```

When `--profile` is passed without a value, `args.profile == "sampling"`. When `--profile deep` is passed, `args.profile == "deep"`. When omitted, `args.profile is None`.

---

## Component 1: py-spy Sampling Profiler (`--profile` / `--profile sampling`)

**Tool**: py-spy — out-of-process sampling profiler that reads CPython VM memory without injecting into the target process.

**Mechanism**: The `__main__.py` entry point detects `--profile` (with value `sampling` or no value) and re-executes itself under `py-spy record`. This means py-spy wraps the entire process lifecycle with zero code changes to the application.

**Re-exec flow**:
1. `__main__.py` checks for `--profile` in `sys.argv` AND checks that the environment variable `_LEDFX_UNDER_PYSPY` is NOT set (sentinel to prevent infinite recursion)
2. If `--profile deep` is found, skips re-exec (VizTracer handles it in `main.py`)
3. Strips `--profile` (and optional `sampling` value) from args
4. Ensures `profiles/` directory exists
5. Sets `_LEDFX_UNDER_PYSPY=1` in the environment
6. Execs: `py-spy record --format speedscope -o profiles/profile-<timestamp>.json -- uv run -m dj_ledfx <remaining args>`
7. On shutdown, prints the output path to stdout

**Output**: Speedscope JSON, opened interactively at [speedscope.app](https://www.speedscope.app/) (local file, no upload).

**Overhead**: ~0.1% — safe to use during normal operation without affecting 60fps render loop.

**macOS note**: py-spy may require `sudo` or SIP configuration. The re-exec prints a helpful error message if permission is denied.

---

## Component 2: VizTracer Deep Profiler (`--profile deep`)

**Tool**: VizTracer — function-level tracer with native async support. On Python 3.12+, uses `sys.monitoring` for lower overhead (~8-10%). On Python 3.11, falls back to `sys.settrace` with higher overhead (~15-20%).

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
        # Fires on both normal return (stop_event set) and KeyboardInterrupt.
        # asyncio.run() returns normally after signal handler sets stop_event,
        # so the finally block always executes before process exit.
        tracer.stop()
        path = f"profiles/profile-{timestamp}.json"
        tracer.save(path)
        print(f"VizTracer profile saved to {path}")
```

**Output**: Chrome Trace Event JSON, loadable in [Perfetto UI](https://ui.perfetto.dev/). Shows coroutine interleaving, async task scheduling, and exact call sequences.

**Overhead**: ~8-10% on Python 3.12+ (sys.monitoring), ~15-20% on Python 3.11 (sys.settrace). Will cause frame drops at 60fps. Intended for targeted debugging sessions, not everyday use.

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
| `ledfx_beats_received_total` | Counter | — | on_beat callback in main.py |
| `ledfx_ring_buffer_depth` | Gauge | — | _status_loop in main.py |
| `ledfx_event_loop_lag_seconds` | Histogram | — | Event loop lag task in main.py |

### Custom Histogram Buckets

Default Prometheus buckets are too coarse for sub-millisecond render times. Custom buckets for latency-sensitive metrics:

```python
# For render and send durations (budget: 16.6ms at 60fps)
FAST_DURATION_BUCKETS = (0.0001, 0.0005, 0.001, 0.002, 0.005, 0.01, 0.0166, 0.05, 0.1)

# For event loop lag
LAG_BUCKETS = (0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0)
```

### Event Loop Lag Measurement

A coroutine in `main.py` measures event loop responsiveness. Created alongside other tasks in `_run()`, cancelled during shutdown.

```python
async def _event_loop_lag_loop() -> None:
    """Measure event loop lag by comparing expected vs actual sleep wake time."""
    interval = 0.1  # 100ms
    while True:
        t0 = time.monotonic()
        await asyncio.sleep(interval)
        lag = time.monotonic() - t0 - interval
        EVENT_LOOP_LAG.observe(max(0.0, lag))
```

This uses `asyncio.sleep()` (not `call_later()`) for simplicity. The difference between requested and actual sleep duration is the lag.

### metrics.py Module

New file: `src/dj_ledfx/metrics.py`

Owns all metric definitions. Exposes an `init(enabled: bool, port: int)` function called from `main.py`.

**No-op pattern**: When `--metrics` is not passed, all metric objects are no-op stubs. The `prometheus-client` package is only imported when metrics are enabled (optional dependency with guarded import).

```python
from __future__ import annotations
from contextlib import contextmanager
from typing import Any, Generator

class _NoOpMetric:
    def observe(self, v: float) -> None: ...
    def inc(self, v: float = 1) -> None: ...
    def set(self, v: float) -> None: ...
    def labels(self, **kw: str) -> _NoOpMetric: return self

    @contextmanager
    def time(self) -> Generator[None, None, None]:
        yield

# Module-level metric references (start as no-ops)
RENDER_DURATION: Any = _NoOpMetric()
RENDER_FPS: Any = _NoOpMetric()
# ... etc

def init(enabled: bool, port: int = 9091) -> None:
    global RENDER_DURATION, RENDER_FPS  # ... etc
    if not enabled:
        return
    from prometheus_client import Counter, Gauge, Histogram, start_http_server
    RENDER_DURATION = Histogram(
        "ledfx_render_duration_seconds", "...", buckets=FAST_DURATION_BUCKETS
    )
    # ... etc
    start_http_server(port)
```

**HTTP server**: `prometheus_client.start_http_server(port)` runs in a daemon thread — never touches the asyncio event loop.

### Instrumented Files

| File | Change |
|------|--------|
| `__main__.py` | py-spy re-exec logic with `_LEDFX_UNDER_PYSPY` sentinel |
| `main.py` | Parse `--profile`, `--metrics`, `--metrics-port`. Init metrics. VizTracer wrap. Event loop lag task. `BEATS_RECEIVED.inc()` in on_beat callback. `RING_BUFFER_DEPTH.set()` in _status_loop. |
| `metrics.py` | **New**. All metric definitions + no-op stubs + `init()` |
| `effects/engine.py` | 2 lines: import + `RENDER_DURATION.observe(dt)` in existing timing code |
| `scheduling/scheduler.py` | ~4 lines: import + observe send duration, inc dropped frames, set device FPS |
| `beat/clock.py` | 2 lines: import + `BEAT_BPM.set()` on beat update |

**Note**: `events.py` and `status.py` are NOT modified. Beat counting goes in the existing `on_beat` callback in `main.py`. Ring buffer depth goes in `_status_loop` in `main.py`. This avoids polluting the generic event bus with metric-specific logic.

---

## Component 4: Grafana & Prometheus Setup

### Setup Script

`scripts/setup-monitoring.sh` automates the full stack:

1. Detects platform — on macOS uses `brew`, on Linux prints manual install instructions with download URLs and exits
2. Installs `prometheus` and `grafana` via `brew` if missing
3. Generates `monitoring/prometheus.yml` scrape config targeting `localhost:9091` (app metrics port) every 5s
4. Drops a pre-built Grafana dashboard JSON into `monitoring/grafana-dashboard.json`
5. Prints start/stop instructions

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
prometheus --config.file=monitoring/prometheus.yml &   # Prometheus on :9090 (default)
brew services start grafana                            # Grafana on :3000
uv run -m dj_ledfx --metrics --demo                   # App metrics on :9091
```

**Port layout**: Prometheus server on :9090 (its default), app metrics endpoint on :9091, Grafana on :3000. No conflicts.

Import `monitoring/grafana-dashboard.json` via Grafana UI (or the setup script provisions it via Grafana HTTP API).

---

## Dependencies

### Python (added to pyproject.toml)

| Package | Purpose | Install group |
|---------|---------|---------------|
| `prometheus-client` | Metrics collection + HTTP server | optional extras `[metrics]` |
| `py-spy` | Sampling profiler | optional extras `[profiling]` |
| `viztracer` | Function-level tracer | optional extras `[profiling]` |

```toml
[project.optional-dependencies]
metrics = ["prometheus-client>=0.20"]
profiling = ["py-spy>=0.4", "viztracer>=1.0"]
dev = ["pytest", "pytest-asyncio", "mypy", "ruff", "prometheus-client>=0.20"]
```

`prometheus-client` is an optional dependency. The `metrics.py` module only imports it when `init(enabled=True)` is called. The no-op stubs are pure Python with no external imports. `prometheus-client` is also included in the `dev` extras so tests can exercise the real metrics path.

### External (via brew on macOS)

| Tool | Default Port | Purpose |
|------|-------------|---------|
| `prometheus` | :9090 | Time-series database, scrapes app's :9091 |
| `grafana` | :3000 | Dashboard visualization |

---

## Testing

- **Unit test**: Import `metrics` module without enabling, call `.observe()` / `.inc()` / `.set()` / `.time()` on no-op stubs — verify no crash
- **Unit test**: Import `metrics` module with enabling, verify metric objects are real `prometheus_client` types
- **Unit test**: Verify `_NoOpMetric.time()` works as context manager
- **Integration test**: Run app with `--metrics`, HTTP GET `localhost:9091/metrics`, verify expected metric names in Prometheus exposition format
- **Unit test**: CLI arg parsing — verify `--profile` gives `"sampling"`, `--profile deep` gives `"deep"`, no flag gives `None`
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
- `pyproject.toml`
- `.gitignore` (add `profiles/`)
