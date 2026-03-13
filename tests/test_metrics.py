from __future__ import annotations

import importlib

import pytest
from prometheus_client import REGISTRY

import dj_ledfx.metrics as metrics_mod


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
