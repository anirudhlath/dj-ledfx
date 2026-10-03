"""The evening at the home (engine spec §5.3): it warms in from an hour before sunset to
the end of civil twilight, stays through the night, and is off again at sunrise (the
owner's decision), fading out from civil dawn. The sun's times come from the home's
location, worked out with astral."""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

from astral import Observer, sun
from loguru import logger

from dj_ledfx.effects.easing import ease_in_out
from dj_ledfx.timing import utcnow

if TYPE_CHECKING:
    from dj_ledfx.home.model import Location

LEAD = timedelta(hours=1)  # the evening starts an hour before sunset
HORIZON_DEG = -0.833  # the sun's centre at sunrise and sunset, refraction included
CACHE_S = 1.0  # Evening works the amount out at most this often
_EVENTS: dict[str, Callable[..., datetime]] = {
    "dawn": sun.dawn,  # civil, the sun 6° below the horizon
    "sunrise": sun.sunrise,
    "sunset": sun.sunset,
    "dusk": sun.dusk,
}
_SAME_EVENT = timedelta(hours=2)  # astral's answers for two dates closer than this are one


def _ramp(fraction: float) -> float:
    return ease_in_out(min(max(fraction, 0.0), 1.0))


def _times(observer: Observer, around: date) -> dict[str, list[datetime]]:
    """Each kind of event from two days before to two days after, each once, in order.
    astral answers per UTC date, so one date can hold two sunsets and the next none."""
    found: dict[str, list[datetime]] = {name: [] for name in _EVENTS}
    for offset in range(-2, 3):
        day = around + timedelta(days=offset)
        for name, event in _EVENTS.items():
            try:
                at = event(observer, day, tzinfo=UTC)
            except ValueError:  # the sun doesn't get there that day (polar day or night)
                continue
            if all(abs(at - seen) > _SAME_EVENT for seen in found[name]):
                found[name].append(at)
    return {name: sorted(times) for name, times in found.items()}


def evening_amount(lat: float, lon: float, at: datetime) -> float:
    """How far into the evening it is at `at` (aware), 0 (day) to 1 (night). It follows
    the night that began with the last sunset whose hour before has started: up from an
    hour before that sunset to civil dusk, 1 until civil dawn, down to 0 at sunrise. Where
    the sun gets no lower than civil twilight, the middle of the night stands in for dusk
    and dawn; where it doesn't set or rise for days, it's day or night by the sun's
    height. Never raises, and moves continuously."""
    observer = Observer(latitude=lat, longitude=lon)
    times = _times(observer, at.astimezone(UTC).date())
    begun = [sunset for sunset in times["sunset"] if sunset - LEAD <= at]
    if not begun:  # no sunset for days: polar day (0) or polar night (1)
        return 0.0 if sun.elevation(observer, at) > HORIZON_DEG else 1.0
    sunset = begun[-1]
    sunrise = next((rise for rise in times["sunrise"] if rise > sunset), None)
    if sunrise is not None and sunrise <= at:
        return 0.0
    middle = None if sunrise is None else sunset + (sunrise - sunset) / 2
    night_end = sunrise or datetime.max.replace(tzinfo=UTC)
    dusk = next((d for d in times["dusk"] if sunset < d < night_end), None)
    full = dusk or middle or sunset + LEAD
    dawn = next((d for d in reversed(times["dawn"]) if full < d < night_end), None)
    fade = max(dawn or middle or full, full)
    start = sunset - LEAD
    if at < full:
        return _ramp((at - start) / (full - start))
    if sunrise is None or at < fade:
        return 1.0
    return 1.0 - _ramp((at - fade) / (sunrise - fade))


class Evening:
    """How far into the evening it is now at the home, 0..1, for the zones' runtimes.
    It reads the home's location each time it works the amount out, at most once a
    second, so a location the owner changes applies within a second. With no location
    it's always 0: looks that follow the evening play as they are."""

    def __init__(
        self,
        location: Callable[[], Location | None],
        *,
        now: Callable[[], datetime] = utcnow,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._location = location
        self._now = now
        self._clock = clock
        self._worked_out = -math.inf
        self._amount = 0.0
        self._told = False

    def __call__(self) -> float:
        stamp = self._clock()
        if stamp - self._worked_out < CACHE_S:
            return self._amount
        self._worked_out = stamp
        place = self._location()
        if place is None:
            if not self._told:
                logger.warning("The home has no location: looks play as they are at evening")
                self._told = True
            self._amount = 0.0
        else:
            self._told = False
            self._amount = evening_amount(place.lat, place.lon, self._now())
        return self._amount
