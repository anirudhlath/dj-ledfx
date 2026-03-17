from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any


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

_initialized = False

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
    global _initialized
    if not enabled or _initialized:
        return
    _initialized = True

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
