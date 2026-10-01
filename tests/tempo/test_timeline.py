from __future__ import annotations

import pytest

from dj_ledfx.tempo.model import TempoSample
from dj_ledfx.tempo.timeline import Timeline, nearest_beat

LINE = Timeline(at=100.0, beat=8.0, period=0.5)  # 120 BPM, beat 8 at t=100


def _sample(line: Timeline, t: float) -> TempoSample:
    return line.sample(t, bpm=120.0, pitch_percent=0.0, source="internal", stale=False)


def test_the_position_counts_beats_from_the_anchor() -> None:
    assert LINE.position(100.0) == 8.0
    assert LINE.position(101.25) == 10.5
    assert LINE.time_of(12.0) == 102.0


def test_a_sample_says_the_beat_and_the_bar() -> None:
    sample = _sample(LINE, 101.25)  # beat 10.5: bar 2 (from 0), its third beat

    assert (sample.beat_index, sample.bar_index, sample.beat_in_bar) == (10, 2, 3)
    assert sample.beat_phase == pytest.approx(0.5)
    assert sample.bar_phase == pytest.approx(2.5 / 4)
    assert (sample.bpm, sample.source, sample.stale) == (120.0, "internal", False)


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
