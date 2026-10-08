from __future__ import annotations

import numpy as np
from conftest import render_ctx
from map_home import ROW, leds_at, lights_at

from dj_ledfx.effects.particles import MAX_PARTICLES, drawn
from dj_ledfx.effects.snowfall import COLUMN_M, EDGE, Snowfall

# Four bulbs round a 6 x 4 m room, under a 3 m ceiling.
CORNERS = lights_at([(0.0, 0.0, 0.5)], [(6.0, 0.0, 1.0)], [(6.0, 4.0, 1.5)], [(0.0, 4.0, 2.0)])


def _snow(**settings: object) -> Snowfall:
    snow = Snowfall(**settings)
    snow.reseed(1)
    return snow


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
    snow = _snow(per_lamp=3.0)
    drawn(snow, render_ctx(t=500.0), CORNERS)
    assert snow.particles.count == 12
    drawn(snow, render_ctx(t=500.0), leds_at([[1.0, 1.0, 1.0]]))
    assert snow.particles.count == 3
    many = lights_at(*[[(float(x), 0.0, 1.0)] for x in range(40)])
    snow = _snow(per_lamp=20.0)
    drawn(snow, render_ctx(t=500.0), many)  # 800 flakes asked for
    assert snow.particles.count == MAX_PARTICLES


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
