from dj_ledfx.latency.strategies import LATENCY_WINDOW, StaticLatency, WindowedMedianLatency
from dj_ledfx.latency.tracker import STREAMING_WINDOW_S, LatencyTracker


def test_tracker_effective_latency() -> None:
    strategy = StaticLatency(latency_ms=10.0)
    tracker = LatencyTracker(strategy=strategy, manual_offset_ms=5.0)
    assert tracker.effective_latency_ms == 15.0


def test_tracker_effective_latency_seconds() -> None:
    strategy = StaticLatency(latency_ms=10.0)
    tracker = LatencyTracker(strategy=strategy, manual_offset_ms=5.0)
    assert abs(tracker.effective_latency_s - 0.015) < 0.0001


def test_the_display_delay_adds_to_the_latency() -> None:
    tracker = LatencyTracker(StaticLatency(10.0), manual_offset_ms=5.0, display_ms=24.0)
    assert tracker.effective_latency_ms == 39.0


def test_a_round_trip_counts_half_and_only_while_the_light_streams() -> None:
    now = [100.0]
    strategy = WindowedMedianLatency(LATENCY_WINDOW, initial_value_ms=10.0)
    tracker = LatencyTracker(strategy, clock=lambda: now[0])
    tracker.update_rtt(60.0)  # nothing sent yet: an idle round trip
    assert tracker.effective_latency_ms == 10.0
    tracker.note_send()
    now[0] += 0.1
    tracker.update_rtt(60.0)
    assert tracker.effective_latency_ms == 30.0
    now[0] += STREAMING_WINDOW_S + 0.1
    tracker.update_rtt(200.0)  # idle again, its Wi-Fi dozing: ignored
    assert tracker.effective_latency_ms == 30.0


def test_reset_forgets_that_the_light_streamed() -> None:
    now = [100.0]
    strategy = WindowedMedianLatency(LATENCY_WINDOW, initial_value_ms=10.0)
    tracker = LatencyTracker(strategy, clock=lambda: now[0])
    tracker.note_send()
    tracker.reset()
    tracker.update_rtt(60.0)
    assert tracker.effective_latency_ms == 10.0


def test_a_latency_is_measured_once_a_streaming_round_trip_lands() -> None:
    now = [100.0]
    strategy = WindowedMedianLatency(LATENCY_WINDOW, initial_value_ms=10.0)
    tracker = LatencyTracker(strategy, clock=lambda: now[0])
    tracker.update_rtt(60.0)  # idle: ignored
    assert not tracker.measured
    tracker.note_send()
    tracker.update_rtt(60.0)
    assert tracker.measured
    tracker.reset()  # the light came back: its seed again
    assert not tracker.measured


def test_a_static_latency_is_never_measured() -> None:
    tracker = LatencyTracker(StaticLatency(10.0))
    tracker.note_send()
    tracker.update_rtt(60.0)
    assert (tracker.effective_latency_ms, tracker.measured) == (10.0, False)  # the config's


def test_a_light_streams_for_the_window_after_a_send() -> None:
    now = [100.0]
    tracker = LatencyTracker(StaticLatency(10.0), clock=lambda: now[0])
    assert not tracker.streaming  # nothing sent yet
    tracker.note_send()
    now[0] += STREAMING_WINDOW_S
    assert tracker.streaming
    now[0] += 0.1
    assert not tracker.streaming
    tracker.note_send()
    tracker.reset()
    assert not tracker.streaming
