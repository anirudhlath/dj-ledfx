from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker


def test_tracker_effective_latency() -> None:
    strategy = StaticLatency(latency_ms=10.0)
    tracker = LatencyTracker(strategy=strategy, manual_offset_ms=5.0)
    assert tracker.effective_latency_ms == 15.0


def test_tracker_effective_latency_seconds() -> None:
    strategy = StaticLatency(latency_ms=10.0)
    tracker = LatencyTracker(strategy=strategy, manual_offset_ms=5.0)
    assert abs(tracker.effective_latency_s - 0.015) < 0.0001


def test_tracker_update_delegates() -> None:
    strategy = StaticLatency(latency_ms=10.0)
    tracker = LatencyTracker(strategy=strategy)
    tracker.update(20.0)
    assert tracker.effective_latency_ms == 10.0
