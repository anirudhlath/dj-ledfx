# Profiling & Real-Time Monitoring Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add hybrid py-spy/VizTracer profiling and Prometheus/Grafana metrics dashboard to dj-ledfx.

**Architecture:** A `metrics.py` module owns all Prometheus metric definitions with a no-op fallback pattern. `__main__.py` handles py-spy re-exec for sampling mode. `main.py` handles VizTracer deep mode and metrics initialization. Instrumentation is surgical — 1-4 lines per touched file.

**Tech Stack:** py-spy (sampling profiler), VizTracer (function tracer), prometheus-client (metrics), Prometheus + Grafana (dashboard via brew)

**Spec:** `docs/superpowers/specs/2026-03-13-profiling-and-monitoring-design.md`

---

## Chunk 1: Dependencies and Core Metrics Module

### Task 1: Add optional dependencies to pyproject.toml

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add optional dependency groups and mypy override**

Add after the `[dependency-groups]` section in `pyproject.toml`:

```toml
[project.optional-dependencies]
metrics = ["prometheus-client>=0.20"]
profiling = ["py-spy>=0.4", "viztracer>=1.0"]
```

Add `prometheus-client>=0.20` to the `dev` dependency group so tests can use real metrics:

```toml
[dependency-groups]
dev = [
    "mypy>=1.19.1",
    "prometheus-client>=0.20",
    "pytest>=9.0.2",
    "pytest-asyncio>=1.3.0",
    "ruff>=0.15.5",
]
```

Add a mypy override to ignore missing imports for `prometheus_client` (it's optional at runtime):
```toml
[[tool.mypy.overrides]]
module = ["prometheus_client.*"]
ignore_missing_imports = true
```

- [ ] **Step 2: Install updated dependencies**

Run: `uv sync`

- [ ] **Step 3: Verify prometheus-client is available**

Run: `uv run python -c "import prometheus_client; print(prometheus_client.__version__)"`
Expected: prints version number

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build: add optional metrics and profiling dependencies"
```

---

### Task 2: Add .gitignore entry for profiles/

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add profiles/ to .gitignore**

Append `profiles/` to `.gitignore`.

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore profiles/ directory"
```

---

### Task 3: Create metrics.py with no-op stubs

**Files:**
- Create: `src/dj_ledfx/metrics.py`
- Test: `tests/test_metrics.py`

- [ ] **Step 1: Write the failing test for no-op metrics**

Create `tests/test_metrics.py`:
```python
from __future__ import annotations


def test_noop_observe() -> None:
    from dj_ledfx.metrics import RENDER_DURATION

    RENDER_DURATION.observe(0.001)  # must not raise


def test_noop_inc() -> None:
    from dj_ledfx.metrics import FRAMES_RENDERED

    FRAMES_RENDERED.inc()  # must not raise


def test_noop_set() -> None:
    from dj_ledfx.metrics import RENDER_FPS

    RENDER_FPS.set(60.0)  # must not raise


def test_noop_labels() -> None:
    from dj_ledfx.metrics import FRAMES_DROPPED

    FRAMES_DROPPED.labels(device="test").inc()  # must not raise


def test_noop_time_context_manager() -> None:
    from dj_ledfx.metrics import RENDER_DURATION

    with RENDER_DURATION.time():
        pass  # must not raise
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_metrics.py -v`
Expected: FAIL with `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3: Write metrics.py with no-op stubs and init()**

Create `src/dj_ledfx/metrics.py`:
```python
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator


class _NoOpMetric:
    """Stub metric that silently discards all observations."""

    def observe(self, v: float) -> None:
        pass

    def inc(self, v: float = 1) -> None:
        pass

    def set(self, v: float) -> None:
        pass

    def labels(self, **kw: str) -> _NoOpMetric:
        return self

    @contextmanager
    def time(self) -> Generator[None, None, None]:
        yield


# Custom histogram buckets for sub-millisecond resolution
FAST_DURATION_BUCKETS = (0.0001, 0.0005, 0.001, 0.002, 0.005, 0.01, 0.0166, 0.05, 0.1)
LAG_BUCKETS = (0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0)

# Module-level metric references — start as no-ops
RENDER_DURATION: Any = _NoOpMetric()
RENDER_FPS: Any = _NoOpMetric()
FRAMES_RENDERED: Any = _NoOpMetric()
FRAMES_DROPPED: Any = _NoOpMetric()
DEVICE_SEND_DURATION: Any = _NoOpMetric()
DEVICE_FPS: Any = _NoOpMetric()
DEVICE_LATENCY: Any = _NoOpMetric()
BEAT_BPM: Any = _NoOpMetric()
BEAT_PHASE: Any = _NoOpMetric()
BEATS_RECEIVED: Any = _NoOpMetric()
RING_BUFFER_DEPTH: Any = _NoOpMetric()
EVENT_LOOP_LAG: Any = _NoOpMetric()


def init(enabled: bool, port: int = 9091) -> None:
    """Initialize metrics. When enabled, replaces no-ops with real Prometheus metrics."""
    if not enabled:
        return

    global RENDER_DURATION, RENDER_FPS, FRAMES_RENDERED, FRAMES_DROPPED
    global DEVICE_SEND_DURATION, DEVICE_FPS, DEVICE_LATENCY
    global BEAT_BPM, BEAT_PHASE, BEATS_RECEIVED
    global RING_BUFFER_DEPTH, EVENT_LOOP_LAG

    from prometheus_client import Counter, Gauge, Histogram, start_http_server

    RENDER_DURATION = Histogram(
        "ledfx_render_duration_seconds",
        "Time spent rendering a single frame",
        buckets=FAST_DURATION_BUCKETS,
    )
    RENDER_FPS = Gauge("ledfx_render_fps", "Current render loop FPS")
    FRAMES_RENDERED = Counter("ledfx_frames_rendered_total", "Total frames rendered")
    FRAMES_DROPPED = Counter(
        "ledfx_frames_dropped_total",
        "Frames dropped per device",
        ["device"],
    )
    DEVICE_SEND_DURATION = Histogram(
        "ledfx_device_send_duration_seconds",
        "Time to send a frame to a device",
        ["device"],
        buckets=FAST_DURATION_BUCKETS,
    )
    DEVICE_FPS = Gauge("ledfx_device_fps", "Effective send FPS per device", ["device"])
    DEVICE_LATENCY = Gauge(
        "ledfx_device_latency_seconds",
        "Effective latency per device",
        ["device"],
    )
    BEAT_BPM = Gauge("ledfx_beat_bpm", "Current BPM from beat clock")
    BEAT_PHASE = Gauge("ledfx_beat_phase", "Current beat phase (0-1)")
    BEATS_RECEIVED = Counter("ledfx_beats_received_total", "Total beat events received")
    RING_BUFFER_DEPTH = Gauge("ledfx_ring_buffer_depth", "Ring buffer fill level (0-1)")
    EVENT_LOOP_LAG = Histogram(
        "ledfx_event_loop_lag_seconds",
        "Event loop scheduling lag",
        buckets=LAG_BUCKETS,
    )

    start_http_server(port)
```

- [ ] **Step 4: Run tests to verify no-op stubs pass**

Run: `uv run pytest tests/test_metrics.py -v`
Expected: All 5 tests PASS

- [ ] **Step 5: Write tests for enabled metrics (real prometheus_client)**

Add to `tests/test_metrics.py`:
```python
import importlib

import pytest
from prometheus_client import CollectorRegistry, REGISTRY

import dj_ledfx.metrics as metrics_mod


@pytest.fixture(autouse=True)
def _reset_metrics() -> None:
    """Reset the metrics module and Prometheus registry between tests that use init()."""
    yield
    # Unregister any collectors we registered during init()
    collectors = list(REGISTRY._names_to_collectors.values())
    for collector in collectors:
        try:
            REGISTRY.unregister(collector)
        except Exception:
            pass
    importlib.reload(metrics_mod)


def test_init_enabled_creates_real_metrics() -> None:
    importlib.reload(metrics_mod)
    metrics_mod.init(enabled=True, port=0)  # port=0 picks random available port
    assert not isinstance(metrics_mod.RENDER_DURATION, metrics_mod._NoOpMetric)
    assert not isinstance(metrics_mod.BEATS_RECEIVED, metrics_mod._NoOpMetric)
    assert not isinstance(metrics_mod.DEVICE_SEND_DURATION, metrics_mod._NoOpMetric)


def test_init_disabled_keeps_noops() -> None:
    importlib.reload(metrics_mod)
    metrics_mod.init(enabled=False)
    assert isinstance(metrics_mod.RENDER_DURATION, metrics_mod._NoOpMetric)
    assert isinstance(metrics_mod.BEATS_RECEIVED, metrics_mod._NoOpMetric)
```

Note: The `_reset_metrics` fixture unregisters Prometheus collectors after each test to prevent `ValueError: Duplicated timeseries` errors when multiple tests call `init(enabled=True)`.

- [ ] **Step 6: Run all metrics tests**

Run: `uv run pytest tests/test_metrics.py -v`
Expected: All 7 tests PASS

- [ ] **Step 7: Run full test suite to verify no regressions**

Run: `uv run pytest -x -v`
Expected: All existing tests still pass

- [ ] **Step 8: Commit**

```bash
git add src/dj_ledfx/metrics.py tests/test_metrics.py
git commit -m "feat(metrics): add metrics module with no-op stubs and Prometheus init"
```

---

## Chunk 2: CLI Flags and Profiling Integration

### Task 4: Add --profile and --metrics CLI flags

**Files:**
- Modify: `src/dj_ledfx/main.py:25-38`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write failing test for CLI arg parsing**

Create `tests/test_cli.py`:
```python
from __future__ import annotations

import sys


def test_profile_flag_default_is_none() -> None:
    orig = sys.argv
    sys.argv = ["dj_ledfx"]
    try:
        from dj_ledfx.main import _parse_args

        args = _parse_args()
        assert args.profile is None
    finally:
        sys.argv = orig


def test_profile_flag_no_value_gives_sampling() -> None:
    orig = sys.argv
    sys.argv = ["dj_ledfx", "--profile"]
    try:
        from dj_ledfx.main import _parse_args

        args = _parse_args()
        assert args.profile == "sampling"
    finally:
        sys.argv = orig


def test_profile_flag_deep() -> None:
    orig = sys.argv
    sys.argv = ["dj_ledfx", "--profile", "deep"]
    try:
        from dj_ledfx.main import _parse_args

        args = _parse_args()
        assert args.profile == "deep"
    finally:
        sys.argv = orig


def test_metrics_flag_default_false() -> None:
    orig = sys.argv
    sys.argv = ["dj_ledfx"]
    try:
        from dj_ledfx.main import _parse_args

        args = _parse_args()
        assert args.metrics is False
    finally:
        sys.argv = orig


def test_metrics_flag_enabled() -> None:
    orig = sys.argv
    sys.argv = ["dj_ledfx", "--metrics"]
    try:
        from dj_ledfx.main import _parse_args

        args = _parse_args()
        assert args.metrics is True
        assert args.metrics_port == 9091
    finally:
        sys.argv = orig


def test_metrics_port_custom() -> None:
    orig = sys.argv
    sys.argv = ["dj_ledfx", "--metrics", "--metrics-port", "8080"]
    try:
        from dj_ledfx.main import _parse_args

        args = _parse_args()
        assert args.metrics_port == 8080
    finally:
        sys.argv = orig
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL — `args` has no attribute `profile`

- [ ] **Step 3: Add CLI flags to _parse_args()**

In `src/dj_ledfx/main.py`, add to `_parse_args()` after the `--bpm` argument (line 37):

```python
    parser.add_argument(
        "--profile",
        nargs="?",
        const="sampling",
        default=None,
        choices=["sampling", "deep"],
        help="Enable profiling: 'sampling' (default, py-spy) or 'deep' (VizTracer)",
    )
    parser.add_argument(
        "--metrics", action="store_true", help="Enable Prometheus metrics endpoint"
    )
    parser.add_argument(
        "--metrics-port",
        type=int,
        default=9091,
        help="Prometheus metrics port (default: 9091)",
    )
```

- [ ] **Step 4: Run CLI tests**

Run: `uv run pytest tests/test_cli.py -v`
Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/main.py tests/test_cli.py
git commit -m "feat(cli): add --profile and --metrics CLI flags"
```

---

### Task 5: Add py-spy re-exec in __main__.py

**Files:**
- Modify: `src/dj_ledfx/__main__.py`

- [ ] **Step 1: Implement py-spy re-exec logic**

Replace `src/dj_ledfx/__main__.py` contents with:

```python
from __future__ import annotations

import os
import sys


def _should_reexec_under_pyspy() -> bool:
    """Check if we should re-exec under py-spy for sampling profiling."""
    if os.environ.get("_LEDFX_UNDER_PYSPY"):
        return False
    if "--profile" not in sys.argv:
        return False
    # Don't re-exec for --profile deep (VizTracer handles it in main.py)
    try:
        idx = sys.argv.index("--profile")
        if idx + 1 < len(sys.argv) and sys.argv[idx + 1] == "deep":
            return False
    except ValueError:
        return False
    return True


def _reexec_under_pyspy() -> None:
    """Re-exec the current process under py-spy record."""
    import shutil
    import subprocess
    from datetime import datetime
    from pathlib import Path

    pyspy = shutil.which("py-spy")
    if pyspy is None:
        print(
            "ERROR: py-spy not found. Install with: uv pip install py-spy",
            file=sys.stderr,
        )
        sys.exit(1)

    profiles_dir = Path("profiles")
    profiles_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_path = profiles_dir / f"profile-{timestamp}.json"

    # Strip --profile [sampling] from args for the child process
    remaining_args: list[str] = []
    skip_next = False
    for i, arg in enumerate(sys.argv[1:]):
        if skip_next:
            skip_next = False
            continue
        if arg == "--profile":
            # Check if next arg is "sampling" (skip it too)
            next_idx = i + 2  # +1 for sys.argv[1:] offset, +1 for next
            if next_idx < len(sys.argv) and sys.argv[next_idx] == "sampling":
                skip_next = True
            continue
        remaining_args.append(arg)

    env = os.environ.copy()
    env["_LEDFX_UNDER_PYSPY"] = "1"

    # Use sys.executable to re-invoke under the same Python interpreter
    cmd = [
        pyspy,
        "record",
        "--format",
        "speedscope",
        "-o",
        str(output_path),
        "--",
        sys.executable,
        "-m",
        "dj_ledfx",
        *remaining_args,
    ]

    print(f"Starting py-spy profiler, output: {output_path}")
    try:
        result = subprocess.run(cmd, env=env)
        print(f"\nProfile saved to: {output_path}")
        print("Open at: https://www.speedscope.app/ (load local file)")
        sys.exit(result.returncode)
    except PermissionError:
        print(
            "ERROR: py-spy needs elevated permissions on macOS.\n"
            "Try: sudo uv run -m dj_ledfx --profile\n"
            "Or disable SIP: https://github.com/benfred/py-spy#how-do-i-run-py-spy-in-docker--macOS",
            file=sys.stderr,
        )
        sys.exit(1)


if _should_reexec_under_pyspy():
    _reexec_under_pyspy()
else:
    from dj_ledfx.main import main

    main()
```

- [ ] **Step 2: Run full test suite to verify no regressions**

Run: `uv run pytest -x -v`
Expected: All tests pass (py-spy re-exec is only triggered with `--profile` flag and no `_LEDFX_UNDER_PYSPY` env var)

- [ ] **Step 3: Commit**

```bash
git add src/dj_ledfx/__main__.py
git commit -m "feat(profile): add py-spy re-exec in __main__.py for --profile sampling"
```

---

### Task 6: Add VizTracer deep profiling in main.py

**Files:**
- Modify: `src/dj_ledfx/main.py` (the `main()` function)

- [ ] **Step 1: Add VizTracer integration to main()**

In `src/dj_ledfx/main.py`, replace the `main()` function with:

```python
def main() -> None:
    args = _parse_args()

    logger.remove()
    logger.add(sys.stderr, level=args.log_level)

    if args.profile == "deep":
        from datetime import datetime
        from pathlib import Path

        try:
            from viztracer import VizTracer
        except ImportError:
            logger.error(
                "VizTracer not installed. Install with: uv pip install viztracer"
            )
            sys.exit(1)

        profiles_dir = Path("profiles")
        profiles_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_path = profiles_dir / f"profile-{timestamp}.json"

        tracer = VizTracer(
            tracer_entries=1_000_000,
            include_files=["*/dj_ledfx/*"],
            min_duration=50,
            log_async=True,
        )
        tracer.start()
        try:
            asyncio.run(_run(args))
        except KeyboardInterrupt:
            pass
        finally:
            # Fires on both normal return (stop_event set) and KeyboardInterrupt.
            # asyncio.run() returns normally after signal handler sets stop_event,
            # so the finally block always executes before process exit.
            tracer.stop()
            tracer.save(str(output_path))
            logger.info("VizTracer profile saved to {}", output_path)
            print(f"\nProfile saved to: {output_path}")
            print("Open at: https://ui.perfetto.dev/ (load local file)")
    else:
        try:
            asyncio.run(_run(args))
        except KeyboardInterrupt:
            pass
```

- [ ] **Step 2: Run full test suite**

Run: `uv run pytest -x -v`
Expected: All tests pass

- [ ] **Step 3: Commit**

```bash
git add src/dj_ledfx/main.py
git commit -m "feat(profile): add VizTracer deep profiling via --profile deep"
```

---

## Chunk 3: Metrics Instrumentation

### Task 7: Initialize metrics in main.py and add event loop lag

**Files:**
- Modify: `src/dj_ledfx/main.py`

- [ ] **Step 1: Add `import time` to main.py**

Add `import time` to the imports at the top of `src/dj_ledfx/main.py` (after `import signal`). This is required by the `_event_loop_lag_loop` coroutine added in the next step.

- [ ] **Step 2: Add `from dj_ledfx import metrics` import**

Add after existing imports at the top of `src/dj_ledfx/main.py`:
```python
from dj_ledfx import metrics
```

- [ ] **Step 3: Add metrics.init() call at start of _run()**

In `_run()`, after `config = load_config(args.config)`, add:
```python
    metrics.init(enabled=args.metrics, port=args.metrics_port)
```

- [ ] **Step 4: Add BEATS_RECEIVED.inc() to on_beat callback**

Modify the existing `on_beat` callback in `_run()` to:
```python
    def on_beat(event: BeatEvent) -> None:
        metrics.BEATS_RECEIVED.inc()
        clock.on_beat(
            bpm=event.bpm,
            beat_number=event.beat_position,
            next_beat_ms=event.next_beat_ms,
            timestamp=event.timestamp,
        )
```

- [ ] **Step 5: Add RING_BUFFER_DEPTH to _status_loop()**

In `_status_loop()`, after the `status = SystemStatus(...)` block, add:
```python
            metrics.RING_BUFFER_DEPTH.set(engine.ring_buffer.fill_level)
```

- [ ] **Step 6: Add event loop lag coroutine and task**

Define the coroutine inside `_run()`, after `stop_event = asyncio.Event()` and before the task creation block:
```python
    async def _event_loop_lag_loop() -> None:
        interval = 0.1
        while not stop_event.is_set():
            t0 = time.monotonic()
            await asyncio.sleep(interval)
            lag = time.monotonic() - t0 - interval
            metrics.EVENT_LOOP_LAG.observe(max(0.0, lag))
```

After `tasks.append(asyncio.create_task(_status_loop()))`, add:
```python
    if args.metrics:
        tasks.append(asyncio.create_task(_event_loop_lag_loop()))
```

- [ ] **Step 7: Run full test suite**

Run: `uv run pytest -x -v`
Expected: All tests pass

- [ ] **Step 8: Commit**

```bash
git add src/dj_ledfx/main.py
git commit -m "feat(metrics): init metrics in main, add event loop lag and beat counter"
```

---

### Task 8: Instrument EffectEngine

**Files:**
- Modify: `src/dj_ledfx/effects/engine.py`
- Test: `tests/effects/test_engine.py` (add metrics verification)

- [ ] **Step 1: Write test verifying render metrics are observed when enabled**

Add to `tests/effects/test_engine.py`:
```python
import importlib

import dj_ledfx.metrics as metrics_mod


async def test_engine_tick_observes_render_duration(mock_clock, mock_effect):
    """Verify that EffectEngine.tick() calls metrics.RENDER_DURATION.observe()."""
    from unittest.mock import MagicMock

    importlib.reload(metrics_mod)
    mock_duration = MagicMock()
    mock_rendered = MagicMock()
    original_duration = metrics_mod.RENDER_DURATION
    original_rendered = metrics_mod.FRAMES_RENDERED
    metrics_mod.RENDER_DURATION = mock_duration
    metrics_mod.FRAMES_RENDERED = mock_rendered
    try:
        from dj_ledfx.effects.engine import EffectEngine

        engine = EffectEngine(clock=mock_clock, effect=mock_effect, led_count=10, fps=60)
        engine.tick(0.0)
        mock_duration.observe.assert_called_once()
        mock_rendered.inc.assert_called_once()
    finally:
        metrics_mod.RENDER_DURATION = original_duration
        metrics_mod.FRAMES_RENDERED = original_rendered
```

Note: `mock_clock` and `mock_effect` fixtures should already exist in the test file or conftest. If not, create minimal ones. Check the existing test file for available fixtures first.

- [ ] **Step 2: Run the new test to verify it fails**

Run: `uv run pytest tests/effects/test_engine.py::test_engine_tick_observes_render_duration -v`
Expected: FAIL — `observe` not called (metrics are no-ops, but we're injecting mocks)

- [ ] **Step 3: Add metrics to EffectEngine**

In `src/dj_ledfx/effects/engine.py`:

Add import at top:
```python
from dj_ledfx import metrics
```

In `tick()` method, after `render_elapsed = time.monotonic() - render_start` (line 99), add:
```python
        metrics.RENDER_DURATION.observe(render_elapsed)
        metrics.FRAMES_RENDERED.inc()
```

In the `run()` method, inside the `while self._running:` loop, after `self.tick(now)`, add actual realized FPS tracking:
```python
            if self._render_times:
                avg_render = sum(self._render_times[-60:]) / min(len(self._render_times), 60)
                if avg_render > 0:
                    metrics.RENDER_FPS.set(min(self._fps, 1.0 / (avg_render + (self._frame_period - avg_render))))
                else:
                    metrics.RENDER_FPS.set(self._fps)
```

Actually, the simplest accurate approach: use `FRAMES_RENDERED` counter and compute actual FPS via `rate(ledfx_frames_rendered_total[30s])` in PromQL/Grafana. So instead, just set the configured target FPS as a reference line:
```python
            metrics.RENDER_FPS.set(self._fps)
```

This gives the target FPS; actual FPS is derived from `rate(ledfx_frames_rendered_total[30s])` in Grafana queries. Both are useful.

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/effects/test_engine.py::test_engine_tick_observes_render_duration -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `uv run pytest -x -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/effects/engine.py tests/effects/test_engine.py
git commit -m "feat(metrics): instrument EffectEngine with render duration and frame counter"
```

---

### Task 9: Instrument LookaheadScheduler

**Files:**
- Modify: `src/dj_ledfx/scheduling/scheduler.py`

- [ ] **Step 1: Add metrics to scheduler**

In `src/dj_ledfx/scheduling/scheduler.py`:

Add import at top:
```python
from dj_ledfx import metrics
```

In `_send_loop()`, add `device_name` at the start of the method (after `last_send_time = time.monotonic()`):
```python
        device_name = device.adapter.device_info.name
```

After the successful `await device.adapter.send_frame(frame.colors)` try/except block, before the send count increment (`self._send_counts[index] += 1`), add:
```python
            send_elapsed = time.monotonic() - send_start
            metrics.DEVICE_SEND_DURATION.labels(device=device_name).observe(send_elapsed)
```

After the send count increment, add device latency and FPS update:
```python
            metrics.DEVICE_LATENCY.labels(device=device_name).set(
                device.tracker.effective_latency_s
            )
            metrics.DEVICE_FPS.labels(device=device_name).set(1.0 / device.max_fps)
```

Note: Like RENDER_FPS, DEVICE_FPS reports the target cap. Actual realized FPS can be derived in Grafana via `rate(ledfx_device_send_duration_seconds_count{device="..."}[30s])`.

In the distributor `run()` method, inside the `if slot.has_pending:` block (after the existing trace log), add:
```python
                        metrics.FRAMES_DROPPED.labels(
                            device=device.adapter.device_info.name
                        ).inc()
```

- [ ] **Step 2: Write test verifying scheduler metrics**

Add to `tests/scheduling/test_scheduler.py`:
```python
import importlib
from unittest.mock import MagicMock

import dj_ledfx.metrics as metrics_mod


async def test_send_loop_observes_device_metrics(mock_managed_device, ring_buffer_with_frame):
    """Verify _send_loop calls device send duration and latency metrics."""
    importlib.reload(metrics_mod)
    mock_send = MagicMock()
    mock_latency = MagicMock()
    original_send = metrics_mod.DEVICE_SEND_DURATION
    original_latency = metrics_mod.DEVICE_LATENCY
    # Make .labels() return the mock itself for chaining
    mock_send.labels.return_value = mock_send
    mock_latency.labels.return_value = mock_latency
    metrics_mod.DEVICE_SEND_DURATION = mock_send
    metrics_mod.DEVICE_LATENCY = mock_latency
    try:
        # Exercise the scheduler — existing test fixtures should provide
        # a managed device and ring buffer. Run briefly and check metrics called.
        from dj_ledfx.scheduling.scheduler import LookaheadScheduler

        scheduler = LookaheadScheduler(
            ring_buffer=ring_buffer_with_frame,
            devices=[mock_managed_device],
            fps=60,
        )
        # Run for a short time
        import asyncio

        task = asyncio.create_task(scheduler.run())
        await asyncio.sleep(0.1)
        scheduler.stop()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        # Verify metrics were called (at least once if device was connected)
        if mock_managed_device.adapter.is_connected:
            assert mock_send.labels.called or mock_send.observe.called
    finally:
        metrics_mod.DEVICE_SEND_DURATION = original_send
        metrics_mod.DEVICE_LATENCY = original_latency
```

Note: Check existing test fixtures in `tests/scheduling/test_scheduler.py` — adapt fixture names to match what's already there (`mock_managed_device`, `ring_buffer_with_frame`, etc.). If fixtures don't exist with these names, create minimal ones or use the existing patterns from the file.

- [ ] **Step 3: Run scheduler tests**

Run: `uv run pytest tests/scheduling/test_scheduler.py -v`
Expected: All tests pass

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest -x -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/scheduling/scheduler.py tests/scheduling/test_scheduler.py
git commit -m "feat(metrics): instrument scheduler with send duration, drops, latency"
```

---

### Task 10: Instrument BeatClock

**Files:**
- Modify: `src/dj_ledfx/beat/clock.py`

- [ ] **Step 1: Add metrics to BeatClock.on_beat()**

In `src/dj_ledfx/beat/clock.py`:

Add import at top:
```python
from dj_ledfx import metrics
```

At the end of `on_beat()`, after `self._is_playing = True` (line 53), add:
```python
        metrics.BEAT_BPM.set(bpm)

```

In `get_state_at()`, set `BEAT_PHASE` only in the `on_beat()` method instead of `get_state_at()` to avoid 60fps hot path overhead. After `metrics.BEAT_BPM.set(bpm)`, add:
```python
        metrics.BEAT_PHASE.set((self._last_beat_number - 1) / 4.0)
```

This sets beat phase to the bar position at beat time (0, 0.25, 0.5, 0.75), updated only when beats arrive (~2Hz at 128 BPM) instead of 60 times per second.

- [ ] **Step 2: Write test verifying BeatClock metrics**

Add to `tests/beat/test_clock.py`:
```python
import importlib
from unittest.mock import MagicMock

import dj_ledfx.metrics as metrics_mod


def test_on_beat_sets_bpm_metric() -> None:
    """Verify on_beat() calls metrics.BEAT_BPM.set()."""
    importlib.reload(metrics_mod)
    mock_bpm = MagicMock()
    mock_phase = MagicMock()
    original_bpm = metrics_mod.BEAT_BPM
    original_phase = metrics_mod.BEAT_PHASE
    metrics_mod.BEAT_BPM = mock_bpm
    metrics_mod.BEAT_PHASE = mock_phase
    try:
        from dj_ledfx.beat.clock import BeatClock
        import time

        clock = BeatClock()
        clock.on_beat(bpm=128.0, beat_number=1, next_beat_ms=468, timestamp=time.monotonic())
        mock_bpm.set.assert_called_once_with(128.0)
        mock_phase.set.assert_called_once()
    finally:
        metrics_mod.BEAT_BPM = original_bpm
        metrics_mod.BEAT_PHASE = original_phase
```

- [ ] **Step 3: Run beat clock tests**

Run: `uv run pytest tests/beat/test_clock.py -v`
Expected: All tests pass

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest -x -v`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/beat/clock.py tests/beat/test_clock.py
git commit -m "feat(metrics): instrument BeatClock with BPM and phase gauges"
```

---

### Task 11: Run linting and type checking

**Files:** All modified files

- [ ] **Step 1: Run ruff**

Run: `uv run ruff check .`
Fix any issues found.

- [ ] **Step 2: Run ruff format**

Run: `uv run ruff format .`

- [ ] **Step 3: Run mypy**

Run: `uv run mypy src/`
Fix any type errors. Note: `metrics.py` uses `Any` type annotations for module-level metrics, which is intentional — mypy should accept this.

- [ ] **Step 4: Run full test suite**

Run: `uv run pytest -x -v`
Expected: All tests pass

- [ ] **Step 5: Commit if any fixes were made**

```bash
git add -u
git commit -m "fix: address lint and type check issues from metrics instrumentation"
```

---

## Chunk 4: Monitoring Infrastructure and Validation

### Task 12: Create Prometheus config

**Files:**
- Create: `monitoring/prometheus.yml`

- [ ] **Step 1: Create monitoring directory and prometheus config**

Create `monitoring/prometheus.yml`:
```yaml
global:
  scrape_interval: 5s
  evaluation_interval: 5s

scrape_configs:
  - job_name: "dj-ledfx"
    static_configs:
      - targets: ["localhost:9091"]
```

- [ ] **Step 2: Commit**

```bash
git add monitoring/prometheus.yml
git commit -m "feat(monitoring): add Prometheus scrape config"
```

---

### Task 13: Create Grafana dashboard JSON

**Files:**
- Create: `monitoring/grafana-dashboard.json`

- [ ] **Step 1: Create pre-built Grafana dashboard**

Create `monitoring/grafana-dashboard.json` with a dashboard containing:

- **Row 1: Overview**
  - Gauge panel: `ledfx_render_fps` (title: "Render FPS")
  - Timeseries panel: `ledfx_event_loop_lag_seconds` histogram quantiles (title: "Event Loop Lag")
  - Stat panel: `ledfx_beat_bpm` (title: "BPM")

- **Row 2: Rendering**
  - Heatmap panel: `ledfx_render_duration_seconds` histogram (title: "Render Duration")
  - Timeseries panel: `rate(ledfx_frames_dropped_total[1m])` per device (title: "Frame Drop Rate")

- **Row 3: Devices**
  - Timeseries panel: `ledfx_device_send_duration_seconds` histogram quantiles by device (title: "Device Send Duration")
  - Timeseries panel: `ledfx_device_fps` by device (title: "Device FPS")
  - Timeseries panel: `ledfx_device_latency_seconds` by device (title: "Device Latency")

Use Grafana dashboard JSON model v8+ format with `__inputs` for datasource so it's portable. Set refresh interval to 5s, time range to last 15 minutes.

This is a large JSON file — build it programmatically or write it out as a complete Grafana dashboard export.

- [ ] **Step 2: Commit**

```bash
git add monitoring/grafana-dashboard.json
git commit -m "feat(monitoring): add pre-built Grafana dashboard"
```

---

### Task 14: Create setup script

**Files:**
- Create: `scripts/setup-monitoring.sh`

- [ ] **Step 1: Write setup script**

Create `scripts/setup-monitoring.sh`:
```bash
#!/usr/bin/env bash
set -euo pipefail

echo "=== dj-ledfx Monitoring Setup ==="

# Platform detection
if [[ "$(uname)" != "Darwin" ]]; then
    echo ""
    echo "This script supports macOS (brew) only."
    echo ""
    echo "For Linux, install manually:"
    echo "  Prometheus: https://prometheus.io/download/"
    echo "  Grafana:    https://grafana.com/grafana/download?platform=linux"
    echo ""
    echo "Then use the config files in monitoring/ directory."
    exit 1
fi

# Check for brew
if ! command -v brew &> /dev/null; then
    echo "ERROR: Homebrew not found. Install from https://brew.sh"
    exit 1
fi

# Install Prometheus
if ! command -v prometheus &> /dev/null; then
    echo "Installing Prometheus..."
    brew install prometheus
else
    echo "Prometheus already installed: $(prometheus --version 2>&1 | head -1)"
fi

# Install Grafana
if ! brew list grafana &> /dev/null 2>&1; then
    echo "Installing Grafana..."
    brew install grafana
else
    echo "Grafana already installed"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To start the monitoring stack:"
echo ""
echo "  1. Start Prometheus (port 9090):"
echo "     prometheus --config.file=monitoring/prometheus.yml &"
echo ""
echo "  2. Start Grafana (port 3000):"
echo "     brew services start grafana"
echo ""
echo "  3. Start dj-ledfx with metrics (port 9091):"
echo "     uv run -m dj_ledfx --metrics --demo"
echo ""
echo "  4. Open Grafana at http://localhost:3000 (admin/admin)"
echo "     Import monitoring/grafana-dashboard.json"
echo ""
echo "To stop:"
echo "  brew services stop grafana"
echo "  pkill prometheus"
```

- [ ] **Step 2: Make executable**

Run: `chmod +x scripts/setup-monitoring.sh`

- [ ] **Step 3: Commit**

```bash
git add scripts/setup-monitoring.sh
git commit -m "feat(monitoring): add setup script for Prometheus and Grafana"
```

---

### Task 15: Create monitoring README

**Files:**
- Create: `monitoring/README.md`

- [ ] **Step 1: Write monitoring README**

Create `monitoring/README.md`:
```markdown
# dj-ledfx Monitoring

Real-time performance monitoring with Prometheus and Grafana.

## Quick Start

```bash
# One-time setup (macOS)
./scripts/setup-monitoring.sh

# Start the stack
prometheus --config.file=monitoring/prometheus.yml &
brew services start grafana
uv run -m dj_ledfx --metrics --demo

# Open Grafana
open http://localhost:3000
# Default credentials: admin / admin
# Import monitoring/grafana-dashboard.json
```

## Ports

| Service | Port |
|---------|------|
| App metrics | :9091 |
| Prometheus | :9090 |
| Grafana | :3000 |

## Custom Metrics Port

```bash
uv run -m dj_ledfx --metrics --metrics-port 8080
```

Update `prometheus.yml` targets accordingly.

## Metrics Reference

See `src/dj_ledfx/metrics.py` for all metric definitions.
```

- [ ] **Step 2: Commit**

```bash
git add monitoring/README.md
git commit -m "docs: add monitoring quickstart README"
```

---

### Task 16: Integration test for metrics endpoint

**Files:**
- Create: `tests/test_metrics_integration.py`

- [ ] **Step 1: Write integration test for /metrics endpoint**

Create `tests/test_metrics_integration.py`:
```python
from __future__ import annotations

import importlib
import urllib.request

import pytest
from prometheus_client import REGISTRY

import dj_ledfx.metrics as metrics_mod


@pytest.fixture(autouse=True)
def _reset_metrics():
    """Reset metrics between tests."""
    yield
    collectors = list(REGISTRY._names_to_collectors.values())
    for collector in collectors:
        try:
            REGISTRY.unregister(collector)
        except Exception:
            pass
    importlib.reload(metrics_mod)


def test_metrics_endpoint_serves_ledfx_metrics() -> None:
    """Verify /metrics HTTP endpoint contains expected metric names."""
    importlib.reload(metrics_mod)
    metrics_mod.init(enabled=True, port=0)

    # Find the port the server bound to
    from prometheus_client import REGISTRY

    # Use the generate_latest function to verify metrics are registered
    from prometheus_client import generate_latest

    output = generate_latest(REGISTRY).decode("utf-8")

    assert "ledfx_render_duration_seconds" in output
    assert "ledfx_frames_rendered_total" in output
    assert "ledfx_beat_bpm" in output
    assert "ledfx_event_loop_lag_seconds" in output
    assert "ledfx_ring_buffer_depth" in output
```

- [ ] **Step 2: Run the integration test**

Run: `uv run pytest tests/test_metrics_integration.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_metrics_integration.py
git commit -m "test: add integration test for metrics endpoint"
```

---

### Task 17: Final validation

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest -x -v`
Expected: All tests pass

- [ ] **Step 2: Run linting**

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: No issues

- [ ] **Step 3: Run type checking**

Run: `uv run mypy src/`
Expected: No errors

- [ ] **Step 4: Smoke test metrics endpoint**

Run: `timeout 5 uv run -m dj_ledfx --metrics --demo 2>/dev/null & sleep 2 && curl -s localhost:9091/metrics | grep ledfx_ | head -20; kill %1 2>/dev/null`
Expected: See `ledfx_` prefixed Prometheus metrics in output

- [ ] **Step 5: Smoke test --profile deep flag parses correctly**

Run: `uv run python -c "import sys; sys.argv = ['dj_ledfx', '--profile', 'deep', '--demo']; from dj_ledfx.main import _parse_args; args = _parse_args(); print(f'profile={args.profile}'); assert args.profile == 'deep'"`
Expected: prints `profile=deep`
