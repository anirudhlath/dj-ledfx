from __future__ import annotations

import itertools

import numpy as np
import pytest
from conftest import render_ctx
from crowds import worst_crowd
from map_home import ROW, bulbs, leds_at, lights_at, upright
from stray_lamps import STRAYS, moves, run_frames, stays_in_band, unpassed

from dj_ledfx.effects import embers as embers_module
from dj_ledfx.effects.embers import CLIMB_OVER_M, WOBBLE_M, Embers
from dj_ledfx.effects.particle_tools import Ground, lamps_of
from dj_ledfx.effects.particles import MAX_PARTICLES, drawn

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


@pytest.mark.parametrize("where", STRAYS)
def test_embers_climb_every_led_of_a_lamp_outside_the_floor_and_ceiling(where: str) -> None:
    leds = STRAYS[where]
    frames = run_frames(_embers(), leds)
    z = np.concatenate(frames)
    assert moves(frames)  # climbing from frame to frame, not just spread over heights
    assert unpassed(z, leds) == []  # up the lamp's whole length
    assert stays_in_band(z, leds)  # and the overhang still stops at the floor and the ceiling


def test_an_ember_climbing_a_lamp_near_the_ceiling_ends_at_the_ceiling() -> None:
    near = lights_at(upright(1.0, 1.0), ceiling=1.5)  # 0.3 m over the lamp's top is 1.7 m
    embers = _embers()
    highest = 0.0
    for t in _moments(30.0):
        drawn(embers, render_ctx(t=t), near)
        highest = max(highest, float(embers.particles.pos[:, 2].max()))
    assert 1.5 - 0.03 < highest <= 1.5 + 1e-5  # they climb right up to it, and no further


def test_embers_on_a_home_with_room_for_them_keep_the_rate_they_were_given() -> None:
    home = bulbs(19)  # up to 19 * (10 * 1.25 + 1) = 256 at once, well under the cap
    embers = _embers(per_lamp=10.0)
    embers.place(home)
    counts = []
    for t in np.arange(500.0, 560.0, 0.5):
        embers.step(render_ctx(t=float(t)))
        counts.append(embers.particles.count)
    assert 19 * 10.0 * 0.9 < np.mean(counts) < 19 * 10.0 * 1.1


def test_embers_on_a_crowded_home_at_the_default_rate_are_not_thinned() -> None:
    home = bulbs(100)  # 5 each at the most, and 3 * 1.25 + 1 is under that
    embers = _embers()
    embers.place(home)
    counts = []
    for t in np.arange(500.0, 560.0, 0.5):
        embers.step(render_ctx(t=float(t)))
        counts.append(embers.particles.count)
    assert 100 * 3.0 * 0.9 < np.mean(counts) < 100 * 3.0 * 1.1


@pytest.mark.parametrize("rise", [1.0, 4.0, 15.0])
@pytest.mark.parametrize("lamps", [100, 167, 300, 700])
def test_embers_keep_to_the_cap_on_a_crowded_home_and_none_is_cut(lamps: int, rise: float) -> None:
    crowd = bulbs(lamps)
    ground, embers = Ground.of(crowd), _embers(per_lamp=10.0, rise_s=rise)
    embers.place(crowd)
    counts = []
    for t in np.arange(500.0, 500.0 + 8 * rise, rise / 13):
        ctx = render_ctx(t=float(t))
        embers.step(ctx)
        made = embers.positions(ctx, ground)
        assert made.count <= MAX_PARTICLES
        assert embers.particles.count == made.count  # step() cut none, mid-life or otherwise
        counts.append(made.count)
    served = min(lamps, MAX_PARTICLES)
    assert np.mean(counts) > 0.5 * served * (MAX_PARTICLES // served)  # not thinned to nothing


@pytest.mark.parametrize("lamps", [100, 700])
def test_a_crowded_home_shares_its_embers_evenly_between_the_lamps_it_serves(lamps: int) -> None:
    crowd = bulbs(lamps)
    embers = _embers(per_lamp=10.0, rise_s=4.0)
    embers.place(crowd)
    ground = Ground.of(crowd)
    seen = np.zeros(lamps)
    moments = np.arange(500.0, 620.0, 0.5)
    for t in moments:
        made = embers.positions(render_ctx(t=float(t)), ground)
        seen += np.bincount(np.rint(made.pos[:, 0]).astype(np.int64), minlength=lamps)
    served = seen > 0
    assert served.sum() == min(lamps, MAX_PARTICLES)  # a few lamps when there are too many
    mean = seen[served] / len(moments)
    assert (mean > 0.75 * mean.mean()).all() and (mean < 1.25 * mean.mean()).all()


def test_the_lamps_of_a_crowded_home_are_not_in_step_so_its_embers_do_not_breathe() -> None:
    crowd = bulbs(700)  # one ember at a time at the most, born in a quarter of each stretch
    ground, embers = Ground.of(crowd), _embers(per_lamp=10.0, rise_s=4.0)
    counts = [
        embers.positions(render_ctx(t=float(t)), ground).count
        for t in np.arange(500.0, 560.0, 0.1)
    ]
    assert np.std(counts) < 0.08 * np.mean(counts)  # 4%, where lamps in step breathe by 18%


@pytest.mark.parametrize("lamps", [100, 167, 300, 700])
def test_however_the_draws_fall_embers_never_pass_the_cap_on_a_crowded_home(
    monkeypatch: pytest.MonkeyPatch, lamps: int
) -> None:
    embers = _embers(per_lamp=10.0, rise_s=4.0)
    served, most = worst_crowd(monkeypatch, embers_module, embers, bulbs(lamps), 40.0, lives=True)
    assert served == min(lamps, MAX_PARTICLES)
    each = MAX_PARTICLES // served  # the cap, shared out in whole embers
    assert most == each  # the worst hand fills a lamp's share, and never past it
    assert served * most <= MAX_PARTICLES
