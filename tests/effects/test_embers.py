from __future__ import annotations

import itertools

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


def test_an_ember_lives_its_rise_time_give_or_take_a_quarter() -> None:
    one = leds_at([[1.0, 1.0, 1.0]])  # a bulb, with about one ember at a time
    step = 0.25
    for rise in (3.0, 8.0):
        embers = _embers(per_lamp=0.5, rise_s=rise)
        counts = []
        for t in np.arange(500.0, 500.0 + 120 * rise, step):
            drawn(embers, render_ctx(t=float(t)), one)
            counts.append(embers.particles.count)
        # Each stretch with an ember is one's life, unless two overlapped. The first and the
        # last may be cut short by where the run starts and ends.
        runs = [list(run) for alive, run in itertools.groupby(counts, key=bool) if alive]
        lives = [len(run) * step for run in runs[1:-1] if max(run) == 1]
        assert len(lives) > 15
        assert min(lives) >= 0.75 * rise - step
        assert np.percentile(lives, 10) < 0.9 * rise
        assert np.percentile(lives, 90) > 1.1 * rise


def test_embers_are_born_at_moments_of_their_own() -> None:
    one = leds_at([[1.0, 1.0, 1.0]])
    embers = _embers(per_lamp=0.5, rise_s=4.0)  # one in each 8 s, at a moment of its own
    counts = []
    for t in np.arange(500.0, 1300.0, 0.25):
        drawn(embers, render_ctx(t=float(t)), one)
        counts.append(embers.particles.count)
    born = np.flatnonzero(np.diff(counts) > 0) * 0.25
    assert len(born) > 80
    assert np.std(np.diff(born)) > 0.2 * 8.0  # not on a beat: gaps of 0 to 16 s, 3.3 s apart


def test_embers_are_as_big_as_the_setting_says() -> None:
    embers = _embers(size=0.35)
    drawn(embers, render_ctx(t=500.0), LAMPS)
    np.testing.assert_allclose(embers.particles.radius, 0.35)


def test_each_lamp_has_embers_of_its_own() -> None:
    lamps = lamps_of(LAMPS)  # the first two are the same lamp, 4 m apart
    embers = _embers()
    for t in _moments(20.0):
        drawn(embers, render_ctx(t=t), LAMPS)
        pos = embers.particles.pos
        lamp = np.linalg.norm(pos[:, None, :2] - lamps.centre[None, :, :2], axis=2).argmin(axis=1)
        assert not np.array_equal(np.sort(pos[lamp == 0, 2]), np.sort(pos[lamp == 1, 2]))


def test_an_ember_brightens_as_it_catches() -> None:
    lamps = lamps_of(LAMPS)
    embers = _embers(palette=["#ffffff"])
    fresh = []
    for t in np.arange(500.0, 530.0, 0.01):
        drawn(embers, render_ctx(t=float(t)), LAMPS)
        pos, colour = embers.particles.pos, embers.particles.colour
        lamp = np.linalg.norm(pos[:, None, :2] - lamps.centre[None, :, :2], axis=2).argmin(axis=1)
        foot, top = lamps.low[lamp], lamps.high[lamp] + CLIMB_OVER_M
        share = ((pos[:, 2] - foot) / (top - foot)) ** (1 / 0.8)  # how far up its climb
        fresh.extend(colour[share < 0.004, 0].tolist())  # under 0.02 s old (a life is 5 s at most)
    assert len(fresh) > 50
    assert max(fresh) < 0.2  # it takes 0.15 s to catch: 0.13 at most


def test_an_ember_does_not_sink_when_its_lamp_is_over_the_ceiling() -> None:
    over = lights_at(upright(1.0, 1.0, 3.2, 3.5), ceiling=3.0)  # a map that puts a lamp up there
    embers = _embers()
    for t in _moments(5.0):
        drawn(embers, render_ctx(t=t), over)
        assert (embers.particles.pos[:, 2] >= 3.2 - 1e-5).all()
