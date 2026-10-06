from typing import Any

from doze_fakes import SEED_MS, START, Lamp, bunched, on_beat, spread
from loguru import logger

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
    tracker.reset()  # the light came back: unmeasured until it streams again
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


def test_a_dozing_light_s_latency_is_its_whole_round_trip_from_the_10th_reply() -> None:
    lamp = Lamp()
    latencies = [lamp.reply(bunched(k), 240.0) for k in range(10)]
    # Half until the check calls it dozing; then all of each round trip it holds, at once.
    assert latencies == [120.0] * 9 + [240.0]
    assert lamp.tracker.dozing and lamp.tracker.measured


def test_an_awake_light_s_latency_is_half_its_round_trip() -> None:
    lamp = Lamp()
    assert [lamp.reply(spread(k), 30.0) for k in range(20)] == [15.0] * 20
    assert not lamp.tracker.dozing


def test_a_change_of_mode_restarts_the_latency_at_the_new_share() -> None:
    """A light remembered dozing whose replies say it's awake: all of each round trip until
    the check holds 10, then half of every one it holds."""
    lamp = Lamp()
    lamp.tracker.recall(30.0, dozing=True)
    assert [lamp.reply(spread(k), 30.0) for k in range(10)] == [30.0] * 9 + [15.0]
    assert not lamp.tracker.dozing


def test_a_light_s_latency_follows_a_step_in_its_round_trips_within_5_s() -> None:
    lamp = Lamp()
    for k in range(20):
        lamp.reply(START + 0.5 * k, 20.0)  # a reply every 0.5 s, as Govee's probes come
    after = [lamp.reply(START + 0.5 * k, 80.0) for k in range(20, 30)]
    assert after[:4] == [10.0] * 4 and after[4:] == [40.0] * 6  # 2 s after the step
    assert not lamp.tracker.dozing


def test_round_trips_that_land_while_the_light_is_idle_never_reach_the_doze_check() -> None:
    lamp = Lamp()
    for k in range(20):
        lamp.now = bunched(k)
        lamp.tracker.update_rtt(240.0)  # no frame went out: an idle light's round trip
    assert (lamp.tracker.link_latency_ms, lamp.tracker.dozing) == (SEED_MS, False)
    assert not lamp.tracker.measured


def test_a_reset_keeps_the_latency_and_the_mode_and_drops_the_round_trips_held() -> None:
    lamp = Lamp()
    for k in range(10):
        lamp.reply(bunched(k), 240.0)
    lamp.tracker.reset()  # the light dropped out and came back

    assert (lamp.tracker.link_latency_ms, lamp.tracker.dozing) == (240.0, True)
    assert not lamp.tracker.measured and not lamp.tracker.streaming
    # The check starts again: dozing through 9 awake replies, awake at the 10th.
    assert [lamp.reply(spread(k), 30.0) for k in range(10, 20)] == [30.0] * 9 + [15.0]


def test_recall_sets_the_latency_and_the_mode() -> None:
    lamp = Lamp(display_ms=24.0)
    lamp.tracker.recall(250.0, dozing=True)
    assert lamp.tracker.link_latency_ms == 250.0
    assert lamp.tracker.effective_latency_ms == 274.0  # its display delay on top, as ever
    assert lamp.tracker.dozing and not lamp.tracker.measured


def test_a_static_latency_ignores_round_trips_whatever_the_mode() -> None:
    records: list[Any] = []
    sink = logger.add(lambda message: records.append(message.record), level="INFO")
    try:
        lamp = Lamp(StaticLatency(10.0))
        lamp.tracker.recall(250.0, dozing=False)
        for k in range(10):
            lamp.reply(bunched(k), 240.0)
    finally:
        logger.remove(sink)
    assert lamp.tracker.dozing  # the check still runs
    assert (lamp.tracker.link_latency_ms, lamp.tracker.measured) == (10.0, False)
    assert [(record["level"].name, record["message"]) for record in records] == [
        (
            "INFO",
            "test-lamp dozes (z 9.8, median round trip 240 ms over 10): its latency stays the"
            " configured one",
        ),
    ]


def test_each_change_of_mode_is_logged_with_z_and_the_median() -> None:
    records: list[Any] = []
    sink = logger.add(lambda message: records.append(message.record), level="INFO")
    try:
        lamp = Lamp()
        for k in range(10):
            lamp.reply(on_beat(k), 240.0)
        for k in range(10, 20):
            lamp.reply(on_beat(k), 20.0)
        turned = lamp.reply(on_beat(20), 20.0)  # it turns awake, over the 21 it holds
        for k in range(21, 30):
            lamp.reply(on_beat(k), 20.0)
    finally:
        logger.remove(sink)
    assert [(record["level"].name, record["message"]) for record in records] == [
        (
            "INFO",
            "test-lamp dozes (z 10.0, median round trip 240 ms over 10): its latency is its"
            " whole round trip",
        ),
        (
            "INFO",
            "test-lamp is awake (z 21.0, median round trip 20 ms over 21): its latency is half"
            " its round trip",
        ),
    ]
    # At the turn the 21 held are replayed oldest first, halved, so the window ends on the
    # newest 9, the 20 ms ones (replayed newest first, it would end on the 240s: 120 ms).
    assert turned == 10.0
