"""Where the clock is in the music, at any time: a straight line of beats (spec §4.2)."""

from __future__ import annotations

import math
from dataclasses import dataclass

from dj_ledfx.tempo.model import BEATS_PER_BAR


@dataclass(frozen=True, slots=True)
class Timeline:
    """Beat `beat` falls at `at` (time.monotonic()), and each beat lasts `period` seconds."""

    at: float
    beat: float
    period: float

    def position(self, t: float) -> float:
        """Beats since beat 0, at time t."""
        return self.beat + (t - self.at) / self.period

    def time_of(self, beat: float) -> float:
        return self.at + (beat - self.beat) * self.period

    def moved(
        self, t: float, *, beat: float | None = None, period: float | None = None
    ) -> Timeline:
        """The line anchored at t: at its own position there unless `beat` says otherwise,
        so nothing jumps, and at its own period unless `period` says otherwise."""
        return Timeline(
            t,
            self.position(t) if beat is None else beat,
            self.period if period is None else period,
        )


def beat_and_bar(position: float) -> tuple[int, float, int, float]:
    """A position on the line as its beat and its bar, each counted from 0: (beat index,
    beat phase, bar index, bar phase), the phases 0 to 1."""
    beat_index = math.floor(position)
    bar_index = beat_index // BEATS_PER_BAR
    return (
        beat_index,
        position - beat_index,
        bar_index,
        (position - bar_index * BEATS_PER_BAR) / BEATS_PER_BAR,
    )


def nearest_beat(position: float, beat_in_bar: int) -> int:
    """The beat nearest `position` that falls `beat_in_bar` (1–4) into its bar, never
    before beat 0. A beat number outside 1–4 says nothing of the bar: the nearest beat."""
    if not 1 <= beat_in_bar <= BEATS_PER_BAR:
        return max(0, round(position))
    offset = beat_in_bar - 1
    beat = offset + BEATS_PER_BAR * round((position - offset) / BEATS_PER_BAR)
    return beat if beat >= 0 else offset
