"""Spec §5.3's evening, from the sun's times at made-up places (never the home's)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from astral import Observer, sun

from dj_ledfx.home.model import Location
from dj_ledfx.home.sun import CACHE_S, LEAD, Evening, evening_amount

GREENWICH = (51.48, 0.0)
DAY = datetime(2026, 10, 3, tzinfo=UTC)


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
    ],
)
def test_the_evening_is_in_range_and_continuous_anywhere(
    lat: float, lon: float, start: datetime
) -> None:
    amounts = _samples(lat, lon, start)

    assert all(0.0 <= amount <= 1.0 for amount in amounts)
    steps = [abs(after - before) for before, after in zip(amounts, amounts[1:], strict=False)]
    assert max(steps) < 0.2  # two minutes never jump more than the fastest dawn moves


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
