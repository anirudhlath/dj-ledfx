from __future__ import annotations

import numpy as np
from conftest import render_ctx
from map_home import ROW, leds_at, lights_at, upright

from dj_ledfx.effects.embers import CLIMB_OVER_M, WOBBLE_M, Embers
from dj_ledfx.effects.particle_tools import lamps_of
from dj_ledfx.effects.particles import drawn

# Two upright lamps from 0.1 to 1.4 m and a short one on a table from 0.8 to 1.2 m.
LAMPS = lights_at(upright(1.0, 1.0), upright(5.0, 1.0), upright(3.0, 4.0, 0.8, 1.2))


def _embers(**settings: object) -> Embers:
    embers = Embers(**settings)
    embers.reseed(1)
    return embers


def _moments(seconds: float = 10.0) -> list[float]:
    return [500.0 + t for t in np.arange(0.0, seconds, 0.1)]


def test_embers_rise_from_each_lamps_foot_to_just_over_its_top() -> None:
    lamps = lamps_of(LAMPS)
    embers = _embers(per_lamp=3.0)
    seen = []
    for t in _moments():
        drawn(embers, render_ctx(t=t), LAMPS)
        seen.append(embers.particles.pos)
    where = np.concatenate(seen)
    gaps = np.linalg.norm(where[:, None, :2] - lamps.centre[None, :, :2], axis=2)
    lamp = gaps.argmin(axis=1)
    assert (gaps.min(axis=1) <= WOBBLE_M + 1e-5).all()  # each on its lamp
    assert (where[:, 2] >= lamps.low[lamp] - 1e-5).all()  # from its foot
    assert (where[:, 2] <= lamps.high[lamp] + CLIMB_OVER_M + 1e-5).all()
    assert set(lamp.tolist()) == {0, 1, 2}
    for which in range(3):  # some just leaving each lamp's foot
        assert where[lamp == which, 2].min() < lamps.low[which] + 0.05


def test_an_ember_dims_and_reddens_as_it_climbs() -> None:
    lamps = lamps_of(LAMPS)
    embers = _embers(palette=["#ffffff", "#ff0000"])  # white as it catches, red dying
    for t in _moments(3.0):
        drawn(embers, render_ctx(t=t), LAMPS)
        pos, colour = embers.particles.pos, embers.particles.colour
        lamp = np.linalg.norm(pos[:, None, :2] - lamps.centre[None, :, :2], axis=2).argmin(axis=1)
        foot, top = lamps.low[lamp], lamps.high[lamp] + CLIMB_OVER_M
        share = ((pos[:, 2] - foot) / (top - foot)) ** (1 / 0.8)  # how far up its climb
        lit = colour[:, 0] > 1e-3
        np.testing.assert_allclose(colour[lit, 1] / colour[lit, 0], 1.0 - share[lit], atol=1e-3)
        assert (colour[:, 0] <= 1.0 - share + 1e-4).all()


def test_embers_smoulder_all_along_a_long_light() -> None:
    leds = leds_at(ROW)  # one light, 4 m long, 1 m up
    embers = _embers(per_lamp=10.0)
    xs = []
    for t in _moments(5.0):
        drawn(embers, render_ctx(t=t), leds)
        xs.extend(embers.particles.pos[:, 0].tolist())
    assert np.ptp(xs) > 3.0  # from LEDs all along it, not from its middle


def test_embers_stop_at_the_ceiling() -> None:
    low_ceiling = lights_at(upright(1.0, 1.0), ceiling=1.5)
    embers = _embers()
    for t in _moments(5.0):
        drawn(embers, render_ctx(t=t), low_ceiling)
        assert (embers.particles.pos[:, 2] <= 1.5 + 1e-5).all()


def test_each_lamp_has_about_per_lamp_embers_climbing_it() -> None:
    embers = _embers(per_lamp=4.0)
    counts = []
    for t in _moments(30.0):
        drawn(embers, render_ctx(t=t), LAMPS)
        counts.append(embers.particles.count)
    assert 3.0 * 4.0 * 0.8 < np.mean(counts) < 3.0 * 4.0 * 1.2
