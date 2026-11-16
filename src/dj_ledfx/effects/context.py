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
    from dj_ledfx.home.sun import SunPoint
    from dj_ledfx.tempo.clock import TempoClock


class SignalView:
    """Named input signals sampled at the frame's target time (spec §7.3). Until M7 there
    are four: DJ_BEAT, EVENING, and SUN_ELEVATION and SUN_AZIMUTH while there is a sun."""

    __slots__ = ("_values",)

    def __init__(self, values: Mapping[str, float] | None = None) -> None:
        self._values: Mapping[str, float] = MappingProxyType(dict(values or {}))

    def get(self, name: str, default: float = 0.0) -> float:
        return self._values.get(name, default)


NO_SIGNALS = SignalView()
DJ_BEAT = "beat.dj"  # 1 while a DJ's deck drives the tempo clock, so a look can tell
EVENING = "time.evening"  # how far into the evening it is at the home, 0..1 (home/sun.py)
# The sun at the home (home/sun.py's Sun), in degrees: its height over the horizon, and its
# bearing clockwise from true north (a look turns it to the plan with plan_bearing, in
# field_tools). Neither is signalled without a sun (no location), so a look reading one gets
# its own default.
SUN_ELEVATION = "sun.elevation"
SUN_AZIMUTH = "sun.azimuth"
_DJ_SIGNALS = SignalView({DJ_BEAT: 1.0})


def _signals(dj: bool, evening: float, sun: SunPoint | None) -> SignalView:
    if evening <= 0.0 and sun is None:
        return _DJ_SIGNALS if dj else NO_SIGNALS
    return _home_signals(dj, evening, sun)


@lru_cache(maxsize=4)
def _home_signals(dj: bool, evening: float, sun: SunPoint | None) -> SignalView:
    """The evening and the sun move at most once a second (home/sun.py's Evening and Sun),
    so the frames between share a view."""
    values: dict[str, float] = {DJ_BEAT: 1.0} if dj else {}
    if evening > 0.0:
        values[EVENING] = evening
    if sun is not None:
        values[SUN_ELEVATION] = sun.elevation_deg
        values[SUN_AZIMUTH] = sun.azimuth_deg
    return SignalView(values)


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
    # Seconds since the zone started this look (ZoneRuntime.started_t): what a look that
    # plays a walk of its own reads, where `t` is the clock's. A resume picks it up where it
    # was, and a Restart keeps it; 0 for a moment that belongs to no running look.
    elapsed_s: float = 0.0

    @property
    def beats(self) -> float:
        """Where the music is: beats since the tempo clock started counting, and the part
        of this one gone."""
        return self.beat_index + self.beat_phase


def render_context(
    clock: TempoClock,
    t: float,
    dt: float,
    evening: float = 0.0,
    *,
    sun: SunPoint | None = None,
    elapsed_s: float = 0.0,
) -> RenderContext:
    """Read the tempo clock at the frame's target time `t` (spec §7.2): only what a frame
    draws with, so no whole TempoSample. `evening` is how far into the evening it is, which
    the signals carry as EVENING, `sun` where the sun is (None: no sun), which they carry as
    SUN_ELEVATION and SUN_AZIMUTH, and `elapsed_s` how long the zone has run its look."""
    beat_index, beat_phase, bar_index, bar_phase = beat_and_bar(clock.position_at(t))
    return RenderContext(
        t=t,
        dt=dt,
        beat_phase=beat_phase,
        bar_phase=bar_phase,
        bpm=clock.bpm,
        beat_index=beat_index,
        bar_index=bar_index,
        signals=_signals(clock.source == "prodjlink" and not clock.stale, evening, sun),
        elapsed_s=elapsed_s,
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
