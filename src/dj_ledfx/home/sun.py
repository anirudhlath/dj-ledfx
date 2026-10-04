"""The evening at the home (engine spec §5.3): it warms in from an hour before sunset to
the end of civil twilight, stays through the night, and is off again at sunrise (the
owner's decision), fading out from civil dawn. The sun's times come from the home's
location, worked out with astral; within POLE_DEG of a pole it follows the sun's height."""

from __future__ import annotations

import math
import time
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from types import MappingProxyType
from typing import TYPE_CHECKING

from astral import Observer, sun
from loguru import logger

from dj_ledfx.effects.field_tools import smoothstep
from dj_ledfx.timing import utcnow

if TYPE_CHECKING:
    from dj_ledfx.home.model import Location

LEAD = timedelta(hours=1)  # the evening starts an hour before sunset
HORIZON_DEG = -0.833  # the sun's centre at sunrise and sunset (astral's, unrefracted)
CACHE_S = 1.0  # Evening works the amount out at most this often
_EVENTS: dict[str, Callable[..., datetime]] = {
    "dawn": sun.dawn,  # civil, the sun 6° below the horizon
    "sunrise": sun.sunrise,
    "sunset": sun.sunset,
    "dusk": sun.dusk,
}
_SAME_EVENT = timedelta(hours=2)  # astral's answers for two dates closer than this are one
CIVIL_DEG = -6.0  # the sun's centre at civil dusk and dawn
# Nearer a pole than this the sun circles the sky at about one height all day, skimming
# the horizon for days around an equinox, and astral's times stop making sense.
POLE_DEG = 89.7


@lru_cache(maxsize=8)
def _times(lat: float, lon: float, around: date) -> Mapping[str, tuple[datetime, ...]]:
    """Each kind of event from two days before to two days after, each once, in order.
    astral answers per UTC date, so one date can hold two sunsets and the next none. Kept
    per place and UTC date: they change once a day."""
    observer = Observer(latitude=lat, longitude=lon)
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
    first = datetime.combine(around - timedelta(days=2), datetime.min.time(), UTC)
    _pair_sunrises_and_sunsets(observer, found, first, first + timedelta(days=5))
    return MappingProxyType({name: tuple(sorted(times)) for name, times in found.items()})


def _pair_sunrises_and_sunsets(
    observer: Observer, found: dict[str, list[datetime]], first: datetime, last: datetime
) -> None:
    """Add the sunrises and sunsets astral missed between `first` and `last`. It works each
    one out at the sun's declination at that moment, so on a day the sun only peeks over
    the horizon at noon, or dips under it at midnight (the edges of polar night and polar
    day), it can find one of the pair and not the other. The sun rises and sets in turn,
    from where it is at `first` to where it is at `last`, so a missing one shows as two of
    a kind in a row; it's the mirror image of whichever of the two only just crossed the
    horizon, about the noon or midnight it's nearest."""
    events = sorted(
        [(at, True) for at in found["sunrise"]] + [(at, False) for at in found["sunset"]]
    )
    up, before = _up(observer, first), None
    for at, rising in events:
        if rising == up:  # risen twice (or set twice): the other one is missing before `at`
            found["sunset" if rising else "sunrise"].append(_missing(observer, before, at))
        up, before = rising, at
    if before is not None and up != _up(observer, last):  # missing after the last one
        turn = _culmination(observer, before, later=True)
        found["sunset" if up else "sunrise"].append(turn + (turn - before))


def _up(observer: Observer, at: datetime) -> bool:
    """Whether the sun is over the horizon, as astral's sunrise and sunset count it."""
    return sun.elevation(observer, at, with_refraction=False) > HORIZON_DEG


def _culmination(observer: Observer, at: datetime, *, later: bool) -> datetime:
    """The solar noon or midnight just after `at` (or just before it)."""
    days = [at.date() + timedelta(days=offset) for offset in (-1, 0, 1)]
    turns = [
        event(observer, day, tzinfo=UTC) for day in days for event in (sun.noon, sun.midnight)
    ]
    return min(t for t in turns if t > at) if later else max(t for t in turns if t < at)


def _missing(observer: Observer, before: datetime | None, at: datetime) -> datetime:
    """The event missing between two of a kind (`before` is None at the start): the mirror
    image of the one nearer its noon or midnight, landing between them."""
    turn = _culmination(observer, at, later=False)
    mirrors = [(at - turn, turn - (at - turn))]
    if before is not None:
        turn = _culmination(observer, before, later=True)
        mirrors.append((turn - before, turn + (turn - before)))
    between = [m for m in mirrors if (before is None or before < m[1]) and m[1] < at]
    return min(between or mirrors)[1]


def _evening_start(sunset: datetime, sunrises: Sequence[datetime]) -> datetime:
    """An hour before the sunset, but not before the sunrise it follows: at the edges of
    polar night a day can be shorter than LEAD."""
    rose = [rise for rise in sunrises if rise < sunset]
    return max(sunset - LEAD, rose[-1]) if rose else sunset - LEAD


def evening_amount(lat: float, lon: float, at: datetime) -> float:
    """How far into the evening it is at `at` (aware), 0 (day) to 1 (night). It follows
    the night that began with the last sunset whose evening has started: up from an hour
    before that sunset (or its sunrise, on a shorter day) to civil dusk, 1 until civil
    dawn, down to 0 at sunrise. Where the sun gets no lower than civil twilight, the
    middle of the night stands in for dusk and dawn. Before the first evening of the days
    astral looks at, _before_any_evening() answers, and near a pole _at_a_pole(). Never
    raises, and moves continuously."""
    if abs(lat) > POLE_DEG:
        return _at_a_pole(lat, lon, at)
    times = _times(lat, lon, at.astimezone(UTC).date())
    begun = [
        sunset for sunset in times["sunset"] if _evening_start(sunset, times["sunrise"]) <= at
    ]
    if not begun:
        return _before_any_evening(lat, lon, at, times)
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
    start = _evening_start(sunset, times["sunrise"])
    if at < full:
        return smoothstep(0.0, 1.0, (at - start) / (full - start))
    if sunrise is None or at < fade:
        return 1.0
    return 1.0 - smoothstep(0.0, 1.0, (at - fade) / (sunrise - fade))


def _before_any_evening(
    lat: float, lon: float, at: datetime, times: Mapping[str, Sequence[datetime]]
) -> float:
    """No evening has begun in the days astral looked at. Since a sunrise, or before a
    sunset (the end of a polar day), it's day. Before a sunrise, it's the night that ends
    polar night, which fades out from civil dawn to that sunrise. With neither for days,
    it's polar day or night by the sun's height."""
    rises = times["sunrise"]
    if any(rise <= at for rise in rises):
        return 0.0
    rise = next((r for r in rises if r > at), None)
    if any(at < sunset and (rise is None or sunset < rise) for sunset in times["sunset"]):
        return 0.0
    if rise is not None:
        dawn = next((d for d in reversed(times["dawn"]) if d < rise), rise - LEAD)
        return 1.0 if at < dawn else 1.0 - smoothstep(0.0, 1.0, (at - dawn) / (rise - dawn))
    return 0.0 if _up(Observer(latitude=lat, longitude=lon), at) else 1.0


def _at_a_pole(lat: float, lon: float, at: datetime) -> float:
    """At a pole there's one evening a year, and it follows the sun's height: up as the sun
    sinks from the horizon to civil dusk's 6° below it, down as it climbs back."""
    height = sun.elevation(Observer(latitude=lat, longitude=lon), at, with_refraction=False)
    return smoothstep(HORIZON_DEG, CIVIL_DEG, height)  # down from the horizon to civil dusk


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
