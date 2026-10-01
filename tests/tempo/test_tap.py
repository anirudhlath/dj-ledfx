from __future__ import annotations

import pytest

from dj_ledfx.tempo.tap import Tap, TapTempo


def _taps(taps: TapTempo, times: list[float]) -> list[Tap | None]:
    return [taps.tap(at) for at in times]


def test_the_third_tap_sets_the_tempo() -> None:
    first, second, third = _taps(TapTempo(), [10.0, 10.5, 11.0])

    assert first == Tap(0, 10.0, None)
    assert second == Tap(1, 10.5, None)
    assert third is not None and third.bpm == pytest.approx(120.0)
    assert (third.index, third.at) == (2, 11.0)


def test_the_tempo_is_the_mean_of_the_last_eight_intervals() -> None:
    slow = [10.0 + 0.6 * k for k in range(4)]  # 100 BPM
    fast = [slow[-1] + 0.5 * k for k in range(1, 10)]  # then 120 BPM, nine taps

    *_, last = _taps(TapTempo(), slow + fast)

    assert last is not None and last.bpm == pytest.approx(120.0)


def test_a_double_tap_counts_once() -> None:
    taps = TapTempo()
    taps.tap(10.0)

    assert taps.tap(10.05) is None  # closer than the fastest beat (300 BPM)
    assert taps.tap(10.5) == Tap(1, 10.5, None)


def test_a_pause_starts_a_new_run() -> None:
    taps = TapTempo()
    _taps(taps, [10.0, 10.5, 11.0])

    again = taps.tap(13.5)  # more than the slowest beat (2 s) later

    assert again == Tap(0, 13.5, None)


# Review Focus 4: taps that don't arrive like taps.
def test_client_times_set_the_tempo_whatever_the_network_did() -> None:
    taps = TapTempo()
    delays = [0.02, 0.15, 0.04, 0.11, 0.01, 0.09]  # each tap's trip over the network
    sent = [1_790_000_000.0 + 0.5 * k for k in range(6)]  # the client's epoch seconds

    results = [taps.tap(500.0 + 0.5 * k + delay, sent[k]) for k, delay in enumerate(delays)]

    assert all(result is not None for result in results)
    assert [result.bpm for result in results[:2] if result] == [None, None]
    assert all(result.bpm == pytest.approx(120.0) for result in results[2:] if result)
    # Each tap lands where the least-delayed tap so far puts the client's clock.
    last = results[-1]
    assert last is not None and last.at == pytest.approx(500.0 + 2.5 + 0.01)
    assert taps.tap(503.1, sent[-1] - 1.0) is None  # stamped before the last tap
    assert taps.tap(503.2, sent[-1] + 0.05) is None  # a double tap, by the client's clock


def test_a_run_never_mixes_client_and_arrival_times() -> None:
    taps = TapTempo()
    taps.tap(10.0, 1_790_000_000.0)
    taps.tap(10.5, 1_790_000_000.5)

    assert taps.tap(11.0) == Tap(0, 11.0, None)  # no client time: a new run
    assert taps.tap(11.5, float("nan")) == Tap(1, 11.5, None)  # NaN is no client time
