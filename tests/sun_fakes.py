"""A sun for tests, standing in for home/sun.py's Sun wherever the app takes one (a zone
runtime's env, the zone manager, the web app). Its places and times are made up."""

from __future__ import annotations

from datetime import UTC, datetime

from dj_ledfx.home.sun import SunPoint, SunReading

# A sun low in the west, as at dusk (made up: no place's).
AT_DUSK = SunPoint(datetime(2026, 3, 20, 18, 0, tzinfo=UTC), 2.0, 270.0)


class FixedSun:
    """Gives the point and the reading it was made with, as Sun gives the sun now, until a
    test sets another: `point` (None: no location, so no sun) and `sun_reading`."""

    def __init__(self, point: SunPoint | None, reading: SunReading | None = None) -> None:
        self.point = point
        self.sun_reading = reading

    def __call__(self) -> SunPoint | None:
        return self.point

    def reading(self) -> SunReading | None:
        return self.sun_reading
