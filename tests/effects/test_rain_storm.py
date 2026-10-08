from __future__ import annotations

import numpy as np
from conftest import render_ctx
from map_home import ROW, leds_at, lights_at, upright

from dj_ledfx.effects.particle_tools import lamps_of
from dj_ledfx.effects.particles import drawn
from dj_ledfx.effects.rain_storm import FLASH_S, JITTER_M, OVER_M, UNDER_M, RainStorm, flash

# Three upright lamps along a 6 m room.
LAMPS = lights_at(upright(0.5, 1.0), upright(3.0, 1.0), upright(5.5, 1.0))


def _storm(**settings: object) -> RainStorm:
    storm = RainStorm(**settings)
    storm.reseed(1)
    return storm


def test_rain_runs_down_each_lamp() -> None:
    lamps = lamps_of(LAMPS)
    storm = _storm(strikes_per_min=0.0, fall_s=1.0)
    drawn(storm, render_ctx(t=500.0), LAMPS)
    before = storm.particles.pos.copy()
    drawn(storm, render_ctx(t=500.05), LAMPS)
    after = storm.particles.pos

    for where in (before, after):
        gaps = np.linalg.norm(where[:, None, :2] - lamps.centre[None, :, :2], axis=2)
        assert (gaps.min(axis=1) <= JITTER_M + 1e-5).all()
        assert (where[:, 2] <= 1.4 + OVER_M + 1e-5).all()
        assert (where[:, 2] >= 0.1 - UNDER_M - 1e-5).all()
    # A drop runs 1.3 + 0.4 m in a second: 0.085 m in 0.05 s. Match each drop by its place.
    for drop in after:
        same = np.linalg.norm(before[:, :2] - drop[:2], axis=1) < 1e-4
        if same.any():  # not one that started since
            np.testing.assert_allclose(before[same, 2][0] - drop[2], 0.085, atol=1e-4)


def test_rain_runs_down_past_leds_all_along_a_long_light() -> None:
    leds = leds_at(ROW)  # one light, 4 m long
    storm = _storm(strikes_per_min=0.0, drops_per_lamp=8.0)
    xs = []
    for t in np.arange(500.0, 502.0, 0.1):
        drawn(storm, render_ctx(t=float(t)), leds)
        pos = storm.particles.pos
        gaps = np.linalg.norm(pos[:, None, :2] - leds.pos[None, :, :2], axis=2).min(axis=1)
        assert (gaps <= JITTER_M + 1e-5).all()
        xs.extend(pos[:, 0].tolist())
    assert np.ptp(xs) > 3.0  # past LEDs all along it, not past its middle


def test_lightning_lights_each_lamp_by_its_distance_from_the_strike() -> None:
    storm = _storm(palette=["#000000"], strikes_per_min=30.0, strike_reach=3.0)
    for t in np.arange(500.0, 510.0, 0.01):
        frame = drawn(storm, render_ctx(t=float(t)), LAMPS)
        strikes = storm.particles.radius > 2.0
        if strikes.any() and frame.max() > 0.2:
            break
    else:
        raise AssertionError("no strike in 10 s at 30 a minute")
    spot = storm.particles.pos[strikes][0]
    lamps = lamps_of(LAMPS)
    nearest_first = np.argsort(np.linalg.norm(lamps.centre[:, :2] - spot[:2], axis=1))
    glow = [frame[14 * lamp : 14 * lamp + 14, 0].mean() for lamp in nearest_first]
    assert glow[0] >= glow[1] >= glow[2]
    assert glow[0] > glow[2]


def test_no_lightning_at_no_strikes_a_minute() -> None:
    storm = _storm(strikes_per_min=0.0)
    for t in np.arange(500.0, 560.0, 0.25):
        drawn(storm, render_ctx(t=float(t)), LAMPS)
        assert (storm.particles.radius < 1.0).all()


def test_a_strike_flashes_dims_and_flickers_once_more() -> None:
    ages = np.array([0.0, 0.15, 0.25, FLASH_S])
    first, dim, flicker, over = flash(ages)
    assert first == 1.0
    assert dim < 0.25 < 0.5 < flicker
    assert over < 0.01
