from __future__ import annotations

import pytest

from dj_ledfx.tempo.timeline import Timeline, beat_and_bar, nearest_beat

LINE = Timeline(at=100.0, beat=8.0, period=0.5)  # 120 BPM, beat 8 at t=100


def test_the_position_counts_beats_from_the_anchor() -> None:
    assert LINE.position(100.0) == 8.0
    assert LINE.position(101.25) == 10.5
    assert LINE.time_of(12.0) == 102.0


def test_a_position_is_a_beat_and_a_bar() -> None:
    beat_index, beat_phase, bar_index, bar_phase = beat_and_bar(LINE.position(101.25))

    assert (beat_index, bar_index) == (10, 2)  # beat 10.5: bar 2 (from 0), its third beat
    assert beat_phase == pytest.approx(0.5)
    assert bar_phase == pytest.approx(2.5 / 4)


def test_moving_the_anchor_never_jumps() -> None:
    slower = LINE.moved(101.0, period=1.0)

    assert slower.position(101.0) == LINE.position(101.0)
    assert slower.position(102.0) == LINE.position(101.0) + 1.0
    assert LINE.moved(101.0, beat=3.0).position(101.0) == 3.0


def test_the_nearest_beat_keeps_its_place_in_the_bar() -> None:
    assert nearest_beat(13.7, 1) == 12
    assert nearest_beat(13.7, 2) == 13
    assert nearest_beat(13.7, 3) == 14
    assert nearest_beat(14.6, 4) == 15
    assert nearest_beat(0.4, 4) == 3  # never before beat 0
    assert nearest_beat(5.2, 0) == 5  # no place in the bar: the nearest beat
    assert nearest_beat(5.6, 9) == 6
