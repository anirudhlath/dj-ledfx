"""What an effect knows about the moment it draws (spec §4.2)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from dj_ledfx.types import BeatContext

if TYPE_CHECKING:
    from dj_ledfx.beat.clock import BeatClock


class SignalView:
    """Named input signals sampled at the frame's target time. Empty until M6-M7."""

    __slots__ = ("_values",)

    def __init__(self, values: Mapping[str, float] | None = None) -> None:
        self._values: Mapping[str, float] = MappingProxyType(dict(values or {}))

    def get(self, name: str, default: float = 0.0) -> float:
        return self._values.get(name, default)


NO_SIGNALS = SignalView()


@dataclass(frozen=True, slots=True)
class RenderContext:
    t: float  # time (s, time.monotonic() clock) the frame will be shown
    dt: float
    beat_phase: float  # 0..1
    bar_phase: float  # 0..1
    bpm: float
    beat_index: int  # 0 until M3 adds the tempo clock's beat counter
    bar_index: int  # 0 until M3
    signals: SignalView


def render_context(clock: BeatClock, t: float, dt: float) -> RenderContext:
    """Sample the beat clock at the frame's target time `t`."""
    state = clock.get_state_at(t)
    return RenderContext(
        t=t,
        dt=dt,
        beat_phase=state.beat_phase,
        bar_phase=state.bar_phase,
        bpm=state.bpm,
        beat_index=0,
        bar_index=0,
        signals=NO_SIGNALS,
    )


def to_beat_context(ctx: RenderContext) -> BeatContext:
    """The narrow context today's 1D effects render with."""
    return BeatContext(beat_phase=ctx.beat_phase, bar_phase=ctx.bar_phase, bpm=ctx.bpm, dt=ctx.dt)
