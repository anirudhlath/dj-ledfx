from __future__ import annotations

import numpy as np
import pytest
from conftest import render_ctx
from map_home import ROW, bulbs, leds_at, lights_at
from stray_lamps import STRAYS, run_heights, stays_in_band, unpassed

from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.effects.particles import MAX_PARTICLES, drawn
from dj_ledfx.effects.snowfall import COLUMN_M, EDGE, Snowfall

# Four bulbs round a 6 x 4 m room, under a 3 m ceiling.
CORNERS = lights_at([(0.0, 0.0, 0.5)], [(6.0, 0.0, 1.0)], [(6.0, 4.0, 1.5)], [(0.0, 4.0, 2.0)])


def _snow(**settings: object) -> Snowfall:
    snow = Snowfall(**settings)
    snow.reseed(1)
    return snow


def _lamp_of_each(snow: Snowfall, leds: LedSet, t: float = 500.0) -> np.ndarray:
    """The lamp each flake falls past at moment t: the nearest, seen from above. (For snow
    that does not drift, over lamps of one LED each that are well apart.)"""
    drawn(snow, render_ctx(t=t), leds)
    gaps = np.linalg.norm(snow.particles.pos[:, None, :2] - leds.pos[None, :, :2], axis=2)
    assert (gaps.min(axis=1) <= COLUMN_M + 1e-5).all()  # each is in some lamp's column
    return gaps.argmin(axis=1)


def _flakes_past(snow: Snowfall, leds: LedSet) -> list[int]:
    """How many flakes fall past each lamp, at one moment."""
    return np.bincount(_lamp_of_each(snow, leds), minlength=leds.count).tolist()


def test_snow_falls_from_the_ceiling_to_the_floor() -> None:
    snow = _snow(fall_s=12.0)
    drawn(snow, render_ctx(t=500.0), CORNERS)
    before = snow.particles.pos[:, 2].copy()
    drawn(snow, render_ctx(t=500.5), CORNERS)
    after = snow.particles.pos[:, 2]

    fell = before - after  # half a second, at 3 m in 10 to 14 s: 0.1 to 0.15 m
    started_again = fell < 0.0  # back at the ceiling
    assert (fell[~started_again] > 0.09).all() and (fell[~started_again] < 0.16).all()
    assert started_again.sum() <= 2
    assert (after >= 0.0).all() and (after <= 3.0).all()


def test_each_lamp_has_per_lamp_flakes_falling_past_it_up_to_the_cap() -> None:
    snow = _snow(per_lamp=3.0, drift=0.0)
    assert _flakes_past(snow, CORNERS) == [3, 3, 3, 3]
    assert snow.particles.count == 12
    assert _flakes_past(snow, leds_at([[1.0, 1.0, 1.0]])) == [3]
    assert snow.particles.count == 3
    assert _flakes_past(_snow(per_lamp=1.0, drift=0.0), bulbs(19)) == [1] * 19  # none go without
    snow = _snow(per_lamp=20.0, drift=0.0)  # 800 flakes asked for
    over = _flakes_past(snow, bulbs(40))
    assert snow.particles.count == MAX_PARTICLES == sum(over)
    assert max(over) - min(over) <= 1  # the cap takes from the lamps alike


def test_a_flake_keeps_its_lamp_from_fall_to_fall_and_as_per_lamp_changes() -> None:
    snow = _snow(per_lamp=3.0, fall_s=3.0, drift=0.0)  # 12 flakes, each fall 2.55 to 3.45 s
    first = _lamp_of_each(snow, CORNERS)
    for t in (520.0, 537.0, 560.0):  # by now each has landed and started again, many times
        np.testing.assert_array_equal(_lamp_of_each(snow, CORNERS, t=t), first)
    more = _lamp_of_each(_snow(per_lamp=5.0, fall_s=3.0, drift=0.0), CORNERS)  # 20 flakes
    np.testing.assert_array_equal(more[: len(first)], first)  # the first twelve stay put


def test_each_flake_falls_past_an_led_and_along_a_long_light() -> None:
    leds = leds_at(ROW)  # one light, 4 m long
    snow = _snow(per_lamp=12.0, drift=0.0)
    drawn(snow, render_ctx(t=500.0), leds)
    pos = snow.particles.pos
    gaps = np.linalg.norm(pos[:, None, :2] - leds.pos[None, :, :2], axis=2).min(axis=1)
    assert (gaps <= COLUMN_M + 1e-5).all()
    assert np.ptp(pos[:, 0]) > 2.5  # past LEDs all along it, not past its middle


def test_a_flake_fades_in_at_the_ceiling_and_out_at_the_floor() -> None:
    snow = _snow(palette=["#ffffff"])
    for t in np.arange(500.0, 520.0, 0.25):
        drawn(snow, render_ctx(t=float(t)), CORNERS)
        share = (3.0 - snow.particles.pos[:, 2]) / 3.0  # how far down each flake is
        glow = snow.particles.colour[:, 0]
        assert (glow <= np.minimum(share, 1.0 - share) / EDGE + 1e-4).all()


def test_flakes_sway_as_they_fall() -> None:
    still, swaying = _snow(drift=0.0), _snow(drift=0.5)
    sideways = []
    for snow in (still, swaying):
        drawn(snow, render_ctx(t=500.0), CORNERS)
        first = snow.particles.pos[:, :2].copy()
        drawn(snow, render_ctx(t=501.0), CORNERS)
        sideways.append(np.linalg.norm(snow.particles.pos[:, :2] - first, axis=1))
    steady = sideways[0] < 1e-6
    assert steady.mean() > 0.9  # without drift a flake falls straight down
    assert np.median(sideways[1]) > 0.1


def test_a_flake_that_lands_starts_again_over_another_place() -> None:
    # Each fall takes 2.5 to 3.5 s, so the first flake falls 28 times or more in 100 s.
    snow = _snow(per_lamp=1.0, fall_s=3.0, drift=0.0)
    columns = set()
    for t in np.arange(500.0, 600.0, 0.25):
        drawn(snow, render_ctx(t=float(t)), CORNERS)
        columns.add(tuple(np.round(snow.particles.pos[0, :2], 3)))
    assert len(columns) >= 10


def test_flakes_are_as_big_as_the_setting_says() -> None:
    snow = _snow(size=0.35)
    drawn(snow, render_ctx(t=500.0), CORNERS)
    np.testing.assert_allclose(snow.particles.radius, 0.35)


@pytest.mark.parametrize("where", STRAYS)
def test_snow_falls_past_every_led_of_a_lamp_outside_the_floor_and_ceiling(where: str) -> None:
    leds = STRAYS[where]
    z = run_heights(_snow(), leds)
    assert np.ptp(z) > 0.1  # falling, not stuck in place
    assert unpassed(z, leds) == []  # past the lamp's whole length
    assert stays_in_band(z, leds)  # from the ceiling or the lamp's top to the floor or its foot
