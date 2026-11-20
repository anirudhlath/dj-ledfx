"""Spec §5.3's evening and §7.3's sun, from the sun's times at made-up places (never the
home's)."""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta, timezone

import pytest
from astral import Observer, sun
from loguru import logger

from dj_ledfx.home import sun as sun_module
from dj_ledfx.home.model import Location
from dj_ledfx.home.sun import (
    CACHE_S,
    LEAD,
    PATH_SPAN,
    PATH_STEP,
    Evening,
    Sun,
    SunPoint,
    SunReading,
    daylight,
    evening_amount,
    plan_bearing,
    sun_path,
    sun_position,
)

GREENWICH = (51.48, 0.0)
EQUATOR = (0.0, 0.0)
MID = (45.0, 0.0)
POLE = (89.9, 0.0)
DAY = datetime(2026, 10, 3, tzinfo=UTC)
SOLSTICE = datetime(2026, 6, 21, tzinfo=UTC)


def _sun(lat: float, lon: float, day: datetime, *events: str) -> list[datetime]:
    """The sun's events of that UTC date, in the order asked (astral's dawn, sunrise,
    sunset or dusk)."""
    observer = Observer(latitude=lat, longitude=lon)
    return [getattr(sun, event)(observer, day.date(), tzinfo=UTC) for event in events]


def _samples(lat: float, lon: float, start: datetime, hours: int = 48) -> list[float]:
    """The evening every two minutes from `start`."""
    return [
        evening_amount(lat, lon, start + timedelta(minutes=minute))
        for minute in range(0, hours * 60, 2)
    ]


def test_the_evening_through_one_night() -> None:
    lat, lon = GREENWICH
    sunset, dusk = _sun(lat, lon, DAY, "sunset", "dusk")
    dawn, sunrise = _sun(lat, lon, DAY + timedelta(days=1), "dawn", "sunrise")

    def at(when: datetime) -> float:
        return evening_amount(lat, lon, when)

    assert at(sunset - LEAD - timedelta(minutes=1)) == 0.0
    assert at(sunset - LEAD) == 0.0
    assert at(sunset - LEAD + (dusk - sunset + LEAD) / 2) == pytest.approx(0.5)
    assert at(dusk) == 1.0
    assert at(dusk + (dawn - dusk) / 2) == 1.0  # the middle of the night
    assert at(dawn) == 1.0
    assert at(dawn + (sunrise - dawn) / 2) == pytest.approx(0.5)
    assert at(sunrise) == 0.0
    assert at(sunrise + timedelta(hours=6)) == 0.0


# Review Focus 5: anywhere, any time, the evening is a number from 0 to 1 that moves
# continuously, across UTC midnight and the date line, through polar days and nights.
@pytest.mark.parametrize(
    ("lat", "lon", "start"),
    [
        (40.0, -120.0, datetime(2026, 6, 20, tzinfo=UTC)),  # sunset after UTC midnight
        (40.0, -120.0, datetime(2026, 12, 20, tzinfo=UTC)),
        (-34.0, 151.0, datetime(2026, 6, 20, tzinfo=UTC)),  # sunset before UTC noon
        (0.0, 179.9, datetime(2026, 3, 20, tzinfo=UTC)),  # either side of the date line
        (0.0, -179.9, datetime(2026, 3, 20, tzinfo=UTC)),
        (62.0, 10.0, datetime(2026, 6, 20, tzinfo=UTC)),  # no civil dusk at midsummer
        (68.0, 20.0, datetime(2026, 5, 20, tzinfo=UTC)),  # the last sunsets before polar day
        (89.0, 0.0, datetime(2026, 9, 22, tzinfo=UTC)),  # the sun along the horizon
        (-90.0, 0.0, datetime(2026, 3, 20, tzinfo=UTC)),
        (85.0, 20.0, datetime(2026, 4, 1, tzinfo=UTC)),  # the first day of polar day
        (80.0, -179.9, datetime(2026, 10, 22, tzinfo=UTC)),  # the first of polar night
        (89.75, 20.0, datetime(2026, 9, 25, tzinfo=UTC)),  # a pole's one evening
    ],
)
def test_the_evening_is_in_range_and_continuous_anywhere(
    lat: float, lon: float, start: datetime
) -> None:
    amounts = _samples(lat, lon, start)

    assert all(0.0 <= amount <= 1.0 for amount in amounts)
    steps = [abs(after - before) for before, after in zip(amounts, amounts[1:], strict=False)]
    assert max(steps) < 0.2  # two minutes never jump more than the fastest dawn moves


# M1: at the edges of polar night too. The first sunrise after it fades the night out from
# civil dawn, the last ones before it start no evening before they rise, and a day the sun
# only peeks over the horizon has its sunset even when astral finds only its sunrise.
@pytest.mark.parametrize(
    "start", [datetime(2026, 1, 13, tzinfo=UTC), datetime(2026, 11, 21, tzinfo=UTC)]
)
def test_the_evening_moves_minute_by_minute_at_the_edges_of_polar_night(
    start: datetime,
) -> None:
    week = [start + timedelta(minutes=minute) for minute in range(7 * 24 * 60)]
    amounts = [evening_amount(70.0, 20.0, at) for at in week]

    steps = [abs(after - before) for before, after in zip(amounts, amounts[1:], strict=False)]
    assert max(steps) < 0.05
    assert min(amounts) == 0.0 and max(amounts) == 1.0


@pytest.mark.parametrize(("lat", "lon"), [(40.0, -120.0), (-34.0, 151.0), (0.0, 179.9)])
def test_every_day_has_one_evening(lat: float, lon: float) -> None:
    amounts = _samples(lat, lon, datetime(2026, 6, 20, 12, tzinfo=UTC), hours=24)

    assert min(amounts) == 0.0 and max(amounts) == 1.0
    starts = [i for i in range(1, len(amounts)) if amounts[i - 1] == 0.0 < amounts[i]]
    assert len(starts) == 1


def test_polar_day_has_no_evening_and_polar_night_is_all_evening() -> None:
    assert set(_samples(70.0, 20.0, datetime(2026, 6, 20, tzinfo=UTC), hours=24)) == {0.0}
    assert set(_samples(70.0, 20.0, datetime(2026, 12, 20, tzinfo=UTC), hours=24)) == {1.0}


def test_with_no_civil_dusk_the_evening_is_full_at_the_middle_of_the_night() -> None:
    lat, lon = 62.0, 10.0  # midsummer: the sun stays within 6° of the horizon all night
    day = datetime(2026, 6, 20, tzinfo=UTC)
    [sunset] = _sun(lat, lon, day, "sunset")
    [sunrise] = _sun(lat, lon, day + timedelta(days=1), "sunrise")
    middle = sunset + (sunrise - sunset) / 2

    assert evening_amount(lat, lon, middle) == 1.0
    assert 0.0 < evening_amount(lat, lon, sunset) < 1.0
    assert evening_amount(lat, lon, sunrise) == 0.0


def test_the_suns_times_are_worked_out_once_a_day_for_a_place(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    asked: list[object] = []
    sunset = sun_module._EVENTS["sunset"]

    def counted(*args: object, **kwargs: object) -> datetime:
        asked.append(args[1])
        return sunset(*args, **kwargs)

    monkeypatch.setitem(sun_module._EVENTS, "sunset", counted)
    lat, lon = (12.5, -40.25)  # somewhere no other test asks about
    morning = datetime(2026, 3, 9, 6, tzinfo=UTC)

    for minutes in range(0, 12 * 60, 30):  # the evening, every half hour of one UTC date
        evening_amount(lat, lon, morning + timedelta(minutes=minutes))
    evening_amount(lat + 1.0, lon, morning)  # another place: its own times

    assert len(asked) == 10  # five dates around each place's, each asked once


def test_evening_reads_the_homes_location_once_a_second() -> None:
    lat, lon = GREENWICH
    [dusk] = _sun(lat, lon, DAY, "dusk")
    night = dusk + timedelta(hours=1)
    place: list[Location | None] = [Location("Test", lat, lon)]
    stamp = [100.0]
    evening = Evening(lambda: place[0], now=lambda: night, clock=lambda: stamp[0])

    assert evening() == 1.0
    place[0] = None
    assert evening() == 1.0  # worked out less than a second ago
    stamp[0] += CACHE_S
    assert evening() == 0.0  # no location: looks play as they are
    place[0] = Location("Test", 0.0, 179.0)  # where it's morning at that moment
    stamp[0] += CACHE_S
    assert evening() == 0.0
    place[0] = Location("Test", lat, lon)
    stamp[0] += CACHE_S
    assert evening() == 1.0


def test_sun_position_is_astrals_apparent_elevation_and_true_azimuth() -> None:
    at = SOLSTICE.replace(hour=12)
    observer = Observer(latitude=MID[0], longitude=MID[1])

    point = sun_position(*MID, at)

    assert point.at == at
    assert point.elevation_deg == pytest.approx(
        sun.elevation(observer, at, with_refraction=True), abs=1e-9
    )
    assert point.azimuth_deg == pytest.approx(sun.azimuth(observer, at), abs=1e-9)
    assert 0.0 <= point.azimuth_deg < 360.0
    assert hash(point) == hash(SunPoint(at, point.elevation_deg, point.azimuth_deg))


def test_daylight_is_the_latest_sunrise_and_the_sunset_after_it() -> None:
    sunrise, sunset = _sun(*MID, SOLSTICE, "sunrise", "sunset")
    yesterday = SOLSTICE - timedelta(days=1)
    rose, set_ = _sun(*MID, yesterday, "sunrise", "sunset")

    noon = SOLSTICE.replace(hour=12)
    assert sunrise < noon < sunset
    assert daylight(*MID, noon) == (sunrise, sunset)

    night = SOLSTICE.replace(hour=23)
    assert sunset < night
    assert daylight(*MID, night) == (sunrise, sunset)

    small_hours = SOLSTICE.replace(hour=1)
    assert set_ < small_hours < sunrise
    assert daylight(*MID, small_hours) == (rose, set_)


def test_the_sun_at_a_pole_has_a_place_but_no_sunrise_or_sunset() -> None:
    midsummer = sun_position(*POLE, SOLSTICE.replace(hour=12))
    midwinter = sun_position(*POLE, datetime(2026, 12, 21, 12, tzinfo=UTC))

    assert math.isfinite(midsummer.elevation_deg) and midsummer.elevation_deg > 0.0
    assert math.isfinite(midwinter.elevation_deg) and midwinter.elevation_deg < 0.0
    for point in (midsummer, midwinter):
        assert math.isfinite(point.azimuth_deg) and 0.0 <= point.azimuth_deg < 360.0
        assert daylight(*POLE, point.at) == (None, None)


def test_the_path_is_the_ten_minute_marks_of_the_two_hours_before_now_oldest_first() -> None:
    assert (PATH_SPAN, PATH_STEP) == (timedelta(hours=2), timedelta(minutes=10))
    first = SOLSTICE.replace(hour=10, minute=40)
    marks = [first + PATH_STEP * step for step in range(12)]

    path = sun_path(*MID, SOLSTICE.replace(hour=12, minute=34, second=56))

    assert [point.at for point in path] == marks
    assert list(path) == [sun_position(*MID, mark) for mark in marks]
    on_a_mark = sun_path(*MID, SOLSTICE.replace(hour=12, minute=30))
    assert [on_a_mark[0].at, on_a_mark[-1].at] == [marks[0], marks[-1]]
    assert len(on_a_mark) == 12
    within_one_mark = SOLSTICE.replace(hour=12, minute=34, second=20)
    assert sun_path(*MID, within_one_mark) == sun_path(
        *MID, within_one_mark + timedelta(seconds=30)
    )


def test_the_path_follows_the_instant_not_the_zone_it_is_given_in() -> None:
    nepal = timezone(timedelta(hours=5, minutes=45))  # its :00 is not a UTC mark
    at = SOLSTICE.replace(hour=12, minute=34, second=56)
    local = at.astimezone(nepal)

    assert local.minute != at.minute
    assert sun_path(*MID, local) == sun_path(*MID, at)


@pytest.mark.parametrize(
    ("azimuth", "offset", "turned"),
    [(270.0, 90.0, 0.0), (10.0, 355.0, 5.0), (90.0, 0.0, 90.0), (10.0, -20.0, 350.0)],
)
def test_plan_bearing_turns_the_azimuth_by_the_north_offset(
    azimuth: float, offset: float, turned: float
) -> None:
    assert plan_bearing(azimuth, offset) == pytest.approx(turned)


def test_plan_bearing_stays_below_a_full_turn() -> None:
    assert plan_bearing(0.0, -1e-20) < 360.0  # -1e-20 % 360.0 is 360.0 in floats


def test_sun_works_its_reading_out_at_most_once_a_second_and_follows_the_location(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    place: list[Location | None] = [Location("Test", *MID)]
    reads: list[None] = []
    paths: list[None] = []
    stamp = [100.0]
    moment = [SOLSTICE.replace(hour=12)]
    real_path = sun_module.sun_path

    def location() -> Location | None:
        reads.append(None)
        return place[0]

    def counted_path(lat: float, lon: float, at: datetime) -> tuple[SunPoint, ...]:
        paths.append(None)
        return real_path(lat, lon, at)

    monkeypatch.setattr(sun_module, "sun_path", counted_path)
    home_sun = Sun(location, now=lambda: moment[0], clock=lambda: stamp[0])

    point = home_sun()
    assert point == sun_position(*MID, moment[0])
    moment[0] += timedelta(seconds=0.4)
    stamp[0] += CACHE_S / 2
    assert home_sun() == point  # worked out less than a second ago
    assert len(reads) == 1 and not paths  # and no path was built for it

    stamp[0] += CACHE_S
    place[0] = Location("Test", *EQUATOR)
    elsewhere = home_sun()
    assert elsewhere == sun_position(*EQUATOR, moment[0])
    assert len(reads) == 2 and not paths

    reading = home_sun.reading()
    assert reading == SunReading(
        elsewhere, *daylight(*EQUATOR, moment[0]), sun_path(*EQUATOR, moment[0])
    )
    assert home_sun.reading() is reading and len(paths) == 1  # built once for the second
    assert home_sun() == reading.now and len(reads) == 2


def test_a_reading_is_built_again_for_each_moment_it_is_worked_out() -> None:
    stamp = [100.0]
    moment = [SOLSTICE.replace(hour=12)]
    home_sun = Sun(lambda: Location("Test", *MID), now=lambda: moment[0], clock=lambda: stamp[0])

    before = home_sun.reading()
    assert before is not None and before.now.at == moment[0]
    stamp[0] += CACHE_S
    moment[0] += timedelta(minutes=10)  # the next mark: its path has moved on
    after = home_sun.reading()

    assert after is not None and after is not before
    assert after.now == sun_position(*MID, moment[0])
    assert after.path == sun_path(*MID, moment[0]) and after.path != before.path
    assert (after.sunrise, after.sunset) == daylight(*MID, moment[0])


def test_no_location_no_sun_logged_once() -> None:
    place: list[Location | None] = [None]
    stamp = [100.0]
    home_sun = Sun(lambda: place[0], clock=lambda: stamp[0])
    warnings: list[str] = []
    sink = logger.add(lambda message: warnings.append(str(message)), level="WARNING")
    try:
        for _ in range(3):
            assert home_sun() is None
            assert home_sun.reading() is None
            stamp[0] += 1.0
        assert len(warnings) == 1
        assert "The home has no location: looks that need the sun wait" in warnings[0]

        place[0] = Location("Test", *MID)
        stamp[0] += 1.0
        assert home_sun() is not None  # a location came back
        place[0] = None
        stamp[0] += 1.0
        assert home_sun() is None
    finally:
        logger.remove(sink)

    assert len(warnings) == 2  # told again, once, when it went missing again
