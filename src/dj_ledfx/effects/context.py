"""What an effect knows about the moment it draws (spec §4.2)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from dj_ledfx.tempo.timeline import beat_and_bar
from dj_ledfx.types import BeatContext

if TYPE_CHECKING:
    from dj_ledfx.tempo.clock import TempoClock


class SignalView:
    """Named input signals sampled at the frame's target time (spec §7.3). Until M6-M7
    there is one: DJ_BEAT."""

    __slots__ = ("_values",)

    def __init__(self, values: Mapping[str, float] | None = None) -> None:
        self._values: Mapping[str, float] = MappingProxyType(dict(values or {}))

    def get(self, name: str, default: float = 0.0) -> float:
        return self._values.get(name, default)


NO_SIGNALS = SignalView()
DJ_BEAT = "beat.dj"  # 1 while a DJ's deck drives the tempo clock, so a look can tell
_DJ_SIGNALS = SignalView({DJ_BEAT: 1.0})


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


def render_context(clock: TempoClock, t: float, dt: float) -> RenderContext:
    """Read the tempo clock at the frame's target time `t` (spec §7.2): only what a frame
    draws with, so no whole TempoSample."""
    beat_index, beat_phase, bar_index, bar_phase = beat_and_bar(clock.position_at(t))
    return RenderContext(
        t=t,
        dt=dt,
        beat_phase=beat_phase,
        bar_phase=bar_phase,
        bpm=clock.bpm,
        beat_index=beat_index,
        bar_index=bar_index,
        signals=_DJ_SIGNALS if clock.source == "prodjlink" and not clock.stale else NO_SIGNALS,
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
