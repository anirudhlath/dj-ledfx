"""What an effect knows about the moment it draws (spec §4.2)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from types import MappingProxyType
from typing import TYPE_CHECKING

from dj_ledfx.tempo.timeline import beat_and_bar
from dj_ledfx.types import BeatContext

if TYPE_CHECKING:
    from dj_ledfx.tempo.clock import TempoClock


class SignalView:
    """Named input signals sampled at the frame's target time (spec §7.3). Until M6-M7
    there are two: DJ_BEAT and EVENING."""

    __slots__ = ("_values",)

    def __init__(self, values: Mapping[str, float] | None = None) -> None:
        self._values: Mapping[str, float] = MappingProxyType(dict(values or {}))

    def get(self, name: str, default: float = 0.0) -> float:
        return self._values.get(name, default)


NO_SIGNALS = SignalView()
DJ_BEAT = "beat.dj"  # 1 while a DJ's deck drives the tempo clock, so a look can tell
EVENING = "time.evening"  # how far into the evening it is at the home, 0..1 (home/sun.py)
_DJ_SIGNALS = SignalView({DJ_BEAT: 1.0})


def _signals(dj: bool, evening: float) -> SignalView:
    if evening <= 0.0:
        return _DJ_SIGNALS if dj else NO_SIGNALS
    return _evening_signals(dj, evening)


@lru_cache(maxsize=4)
def _evening_signals(dj: bool, evening: float) -> SignalView:
    """The evening's amount moves at most once a second (home/sun.py's Evening), so the
    frames between share a view."""
    return SignalView({EVENING: evening, DJ_BEAT: 1.0} if dj else {EVENING: evening})


@dataclass(frozen=True, slots=True)
class RenderContext:
    t: float  # time (s, time.monotonic() clock) the frame will be shown
    dt: float
    beat_phase: float  # 0..1
    bar_phase: float  # 0..1
    bpm: float
    beat_index: int  # beats since the tempo clock started counting
    bar_index: int
    signals: SignalView

    @property
    def beats(self) -> float:
        """Where the music is: beats since the tempo clock started counting, and the part
        of this one gone."""
        return self.beat_index + self.beat_phase


def render_context(clock: TempoClock, t: float, dt: float, evening: float = 0.0) -> RenderContext:
    """Read the tempo clock at the frame's target time `t` (spec §7.2): only what a frame
    draws with, so no whole TempoSample. `evening` is how far into the evening it is, which
    the signals carry as EVENING."""
    beat_index, beat_phase, bar_index, bar_phase = beat_and_bar(clock.position_at(t))
    return RenderContext(
        t=t,
        dt=dt,
        beat_phase=beat_phase,
        bar_phase=bar_phase,
        bpm=clock.bpm,
        beat_index=beat_index,
        bar_index=bar_index,
        signals=_signals(clock.source == "prodjlink" and not clock.stale, evening),
    )


def to_beat_context(ctx: RenderContext) -> BeatContext:
    """The narrow context today's 1D effects render with."""
    return BeatContext(
        beat_phase=ctx.beat_phase,
        bar_phase=ctx.bar_phase,
        bpm=ctx.bpm,
        dt=ctx.dt,
        dj=ctx.signals.get(DJ_BEAT) > 0.0,
        beat_index=ctx.beat_index,
    )
