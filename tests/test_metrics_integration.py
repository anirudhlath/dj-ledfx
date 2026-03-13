from __future__ import annotations

import importlib

import pytest
from prometheus_client import REGISTRY, generate_latest

import dj_ledfx.metrics as metrics_mod


@pytest.fixture(autouse=True)
def _reset_metrics() -> None:
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

    output = generate_latest(REGISTRY).decode("utf-8")

    assert "ledfx_render_duration_seconds" in output
    assert "ledfx_frames_rendered_total" in output
    assert "ledfx_beat_bpm" in output
    assert "ledfx_event_loop_lag_seconds" in output
    assert "ledfx_ring_buffer_depth" in output
