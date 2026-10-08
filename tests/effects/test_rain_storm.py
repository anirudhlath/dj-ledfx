from __future__ import annotations

import math

import numpy as np
import pytest
from conftest import render_ctx
from crowds import SPLITS, dealt, worst_crowd
from map_home import ROW, bulbs, leds_at, lights_at, upright
from numpy.typing import NDArray
from stray_lamps import STRAYS, moves, run_frames, run_heights, stays_in_band, unpassed

from dj_ledfx.effects import rain_storm as rain_module
from dj_ledfx.effects.context import RenderContext
from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.effects.particle_tools import Ground, draws, lamps_of
from dj_ledfx.effects.particles import MAX_PARTICLES, drawn
from dj_ledfx.effects.rain_storm import (
    EDGE,
    FLASH_S,
    JITTER_M,
    OVER_M,
    UNDER_M,
    RainStorm,
    flash,
    flashes_at_once,
)

# Three upright lamps along a 6 m room.
LAMPS = lights_at(upright(0.5, 1.0), upright(3.0, 1.0), upright(5.5, 1.0))
# Four round a 5 x 3 m room, under a 3 m ceiling.
SQUARE = lights_at(upright(0.5, 0.5), upright(5.5, 0.5), upright(5.5, 3.5), upright(0.5, 3.5))


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
        assert (where[:, 2] >= -1e-5).all()  # the lamps stand at 0.1 m: not under the floor
    # A drop runs from 1.4 + 0.25 m to the floor in a second: 0.0825 m in 0.05 s. Match each
    # drop by its place.
    for drop in after:
        same = np.linalg.norm(before[:, :2] - drop[:2], axis=1) < 1e-4
        if same.any():  # not one that started since
            np.testing.assert_allclose(
                before[same, 2][0] - drop[2], (1.4 + OVER_M) * 0.05, atol=1e-4
            )


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


def test_each_lamp_has_about_drops_per_lamp_drops_running_down_it() -> None:
    storm = _storm(strikes_per_min=0.0, drops_per_lamp=4.0)
    counts = []
    for t in np.arange(500.0, 530.0, 0.1):
        drawn(storm, render_ctx(t=float(t)), LAMPS)
        counts.append(storm.particles.count)
    assert 3.0 * 4.0 * 0.9 < np.mean(counts) < 3.0 * 4.0 * 1.1


def test_a_drop_takes_fall_s_to_run_down_a_lamp() -> None:
    storm = _storm(strikes_per_min=0.0, fall_s=2.5)
    drawn(storm, render_ctx(t=500.0), LAMPS)
    before = storm.particles.pos.copy()
    drawn(storm, render_ctx(t=500.05), LAMPS)
    ran = []
    for drop in storm.particles.pos:
        same = np.linalg.norm(before[:, :2] - drop[:2], axis=1) < 1e-4
        if same.any():  # not one that started since
            ran.append(before[same, 2][0] - drop[2])
    assert len(ran) >= 3
    np.testing.assert_allclose(ran, (1.4 + OVER_M) * 0.05 / 2.5, atol=1e-4)


def test_drops_and_strikes_are_as_big_as_the_settings_say() -> None:
    storm = _storm(size=0.25, strike_reach=6.0, strikes_per_min=30.0)
    sizes = set()
    for t in np.arange(500.0, 520.0, 0.1):
        drawn(storm, render_ctx(t=float(t)), LAMPS)
        sizes.update(np.round(storm.particles.radius, 4).tolist())
    assert sizes == {0.25, 6.0}


def test_each_lamp_has_drops_of_its_own() -> None:
    lamps = lamps_of(LAMPS)  # three of the same lamp
    storm = _storm(strikes_per_min=0.0)
    for t in np.arange(500.0, 520.0, 0.5):
        drawn(storm, render_ctx(t=float(t)), LAMPS)
        pos = storm.particles.pos
        lamp = np.linalg.norm(pos[:, None, :2] - lamps.centre[None, :, :2], axis=2).argmin(axis=1)
        assert not np.array_equal(np.sort(pos[lamp == 0, 2]), np.sort(pos[lamp == 1, 2]))


def test_a_drop_fades_in_at_the_top_and_out_at_the_bottom() -> None:
    storm = _storm(palette=["#ffffff"], strikes_per_min=0.0)
    brightest = 0.0
    for t in np.arange(500.0, 505.0, 0.05):
        drawn(storm, render_ctx(t=float(t)), LAMPS)
        z, glow = storm.particles.pos[:, 2], storm.particles.colour[:, 0]
        share = (1.4 + OVER_M - z) / (1.4 + OVER_M)  # how far down its run, to the floor
        assert (glow <= np.minimum(share, 1.0 - share) / EDGE + 1e-4).all()
        brightest = max(brightest, float(glow.max()))
    assert brightest > 0.99


def test_drops_take_their_colours_from_along_the_palette() -> None:
    storm = _storm(palette=["#ff0000", "#0000ff"], strikes_per_min=0.0)
    blue = []
    for t in np.arange(500.0, 510.0, 0.5):
        drawn(storm, render_ctx(t=float(t)), LAMPS)
        colour = storm.particles.colour
        lit = colour.sum(axis=1) > 0.5
        blue.extend((colour[lit, 2] / colour[lit].sum(axis=1)).tolist())
    assert np.ptp(blue) > 0.8  # from red to blue


def test_strikes_land_at_random_over_the_zone_at_half_the_ceilings_height() -> None:
    storm = _storm(strikes_per_min=30.0, lightning="#ffffff")
    seen: dict[tuple[float, ...], float] = {}  # each strike's place, and when it was first seen
    brightest = 0.0
    for t in np.arange(500.0, 800.0, 0.1):
        drawn(storm, render_ctx(t=float(t)), SQUARE)
        strikes = storm.particles.radius > 2.0
        for spot in storm.particles.pos[strikes]:
            seen.setdefault(tuple(np.round(spot, 3)), float(t))
        if strikes.any():
            brightest = max(brightest, float(storm.particles.colour[strikes, 0].max()))
    where = np.array(list(seen))
    assert brightest > 0.8  # a strike starts at the lightning colour in full
    assert 148 <= len(where) <= 152  # one in each 2 s, 150 in 300 s
    assert (where[:, 2] == 1.5).all()  # half of the 3 m ceiling
    assert where[:, 0].min() >= 0.5 - 1e-3 and where[:, 0].max() <= 5.5 + 1e-3  # over the room
    assert where[:, 1].min() >= 0.5 - 1e-3 and where[:, 1].max() <= 3.5 + 1e-3
    assert np.ptp(where[:, 0]) > 4.0 and np.ptp(where[:, 1]) > 2.4  # all over it
    assert np.std(np.diff(sorted(seen.values()))) > 0.4  # at moments of their own, not on a beat


def _heights(leds: LedSet, seconds: float = 30.0) -> NDArray[np.float64]:
    """The heights of every drop of a storm without lightning over `seconds`, seen every 0.05 s
    (a drop runs under 2 m a second, so the lowest seen is within 0.1 m of where it ends)."""
    return run_heights(_storm(strikes_per_min=0.0), leds, seconds)


def test_a_lamp_standing_high_enough_still_runs_its_drops_under_its_lowest_led() -> None:
    z = _heights(lights_at(upright(1.0, 1.0, 0.6, 1.4)))
    bottom = 0.6 - UNDER_M  # 0.45 m up, over the floor
    assert z.min() >= bottom - 1e-5
    assert z.min() < bottom + 0.06  # a drop runs 1.2 m in a second: 0.06 m between looks


def test_a_lamp_standing_at_a_tenth_of_a_metre_never_takes_a_drop_under_the_floor() -> None:
    z = _heights(lights_at(upright(1.0, 1.0, 0.1, 1.4)))
    assert z.min() >= -1e-5  # 0.15 under the lamp's lowest LED would be 0.05 under the floor
    assert z.min() < 0.06  # it runs right down to the floor


def test_a_drop_never_starts_over_the_ceiling() -> None:
    z = _heights(lights_at(upright(1.0, 1.0, 0.1, 2.9), ceiling=3.0))  # 0.25 m over is 3.15 m
    assert z.max() <= 3.0 + 1e-5
    assert z.max() > 3.0 - 0.06


@pytest.mark.parametrize("where", STRAYS)
def test_drops_run_down_every_led_of_a_lamp_outside_the_floor_and_ceiling(where: str) -> None:
    leds = STRAYS[where]
    frames = run_frames(_storm(strikes_per_min=0.0), leds)
    z = np.concatenate(frames)
    assert moves(frames)  # running from frame to frame, not just spread over heights
    assert unpassed(z, leds) == []  # down the lamp's whole length
    assert stays_in_band(z, leds)  # the overhang still stops at the ends


def test_a_lamp_with_no_map_takes_its_drops_down_to_the_lowest_led_of_the_zone() -> None:
    z = _heights(leds_at([[1.0, 1.0, 0.8 + 0.1 * i] for i in range(7)], ceiling=None))
    assert z.min() >= 0.8 - 1e-5  # the zone's floor is its lowest LED
    assert z.max() <= 1.4 + 0.25 + 1e-5


def _count(storm: RainStorm, ctx: RenderContext, ground: Ground) -> tuple[int, int]:
    """The drops and the strikes a storm makes at a moment; step() must cut none of them."""
    made = storm.positions(ctx, ground)
    storm.step(ctx)
    assert storm.particles.count == made.count  # none cut, mid-life or otherwise
    return int((made.radius < 1.0).sum()), int((made.radius >= 1.0).sum())


@pytest.mark.parametrize("fall", [0.3, 1.0, 4.0])
@pytest.mark.parametrize("lamps", [100, 167, 300, 700])
def test_rain_on_a_crowded_home_keeps_its_drops_and_lightning_to_the_cap(
    lamps: int, fall: float
) -> None:
    crowd = bulbs(lamps)
    ground = Ground.of(crowd)
    storm = _storm(drops_per_lamp=8.0, strikes_per_min=30.0, fall_s=fall)
    storm.place(crowd)
    drops = []
    for t in np.arange(500.0, 800.0, 0.37):
        found = _count(storm, render_ctx(t=float(t)), ground)
        assert sum(found) <= MAX_PARTICLES
        drops.append(found[0])
    room = MAX_PARTICLES - 2  # two strikes can flash at once at 30 a minute
    served = min(lamps, room)
    assert np.mean(drops) > 0.5 * served * (room // served)  # not thinned to nothing


def test_two_strikes_can_flash_at_once_at_30_a_minute_but_not_three() -> None:
    storm = _storm(strikes_per_min=30.0)
    ground = Ground.of(LAMPS)
    at_once = {
        int((storm.positions(render_ctx(t=float(t)), ground).radius > 2.0).sum())
        for t in np.arange(500.0, 800.0, 0.05)
    }
    assert at_once == {0, 1, 2}


@pytest.mark.parametrize("lamps", [3, 100, 250, 700])
def test_the_drops_of_a_crowded_home_stay_as_they_are_whatever_the_lightning_setting(
    lamps: int,
) -> None:
    """strikes_per_min is bindable, so it moves at will, through 0 and the whole of its range;
    the room the drops are given must not move with it, or the whole rain would jump."""
    crowd = bulbs(lamps)
    ground = Ground.of(crowd)
    setting = RainStorm.parameters()["strikes_per_min"]
    rates = np.linspace(float(setting.min or 0.0), float(setting.max or 0.0), 7)
    storms = [_storm(drops_per_lamp=8.0, strikes_per_min=float(rate)) for rate in rates]
    for t in np.arange(500.0, 530.0, 0.37):
        ctx = render_ctx(t=float(t))
        made = [storm.positions(ctx, ground) for storm in storms]
        drops = [each.pick(each.radius < 1.0) for each in made]  # leaving the strikes out
        for other in drops[1:]:
            np.testing.assert_array_equal(other.pos, drops[0].pos)
            np.testing.assert_array_equal(other.colour, drops[0].colour)


def test_the_lamps_of_a_crowded_home_are_not_in_step_so_its_rain_does_not_breathe() -> None:
    crowd = bulbs(700)  # one drop at a time at the most, born in a quarter of each stretch
    ground, storm = Ground.of(crowd), _storm(drops_per_lamp=8.0, strikes_per_min=0.0)
    counts = [
        storm.positions(render_ctx(t=float(t)), ground).count for t in np.arange(500.0, 560.0, 0.1)
    ]
    assert np.std(counts) < 0.07 * np.mean(counts)  # 3%, where lamps in step breathe by 13%


@pytest.mark.parametrize("per_min", [4.0, 30.0, 100.0, 101.0, 200.0])
def test_however_the_draws_fall_no_more_strikes_flash_at_once_than_the_room_kept_for_them(
    monkeypatch: pytest.MonkeyPatch, per_min: float
) -> None:
    ground, most = Ground.of(LAMPS), 0
    storm = _storm(strikes_per_min=per_min, drops_per_lamp=0.5)
    for split in range(SPLITS):
        monkeypatch.setattr(rain_module, "draws", dealt(split))
        for t in np.arange(500.0, 502.0 + 120.0 / per_min, 0.01):  # two stretches and more
            made = storm.positions(render_ctx(t=float(t)), ground)
            most = max(most, int((made.radius > 2.0).sum()))
    assert most == flashes_at_once(per_min)  # the room is enough, and no more than needed


def test_drops_and_strikes_are_listed_oldest_first_by_when_they_began() -> None:
    storm = _storm(strikes_per_min=15.0, drops_per_lamp=8.0, fall_s=1.0)
    ground, every, mixed = Ground.of(LAMPS), 60.0 / 15.0, 0
    top = 1.4 + OVER_M  # the lamps stand from 0.1 m: a drop runs from here to the floor
    for t in np.arange(500.0, 600.0, 0.01):
        made = storm.positions(render_ctx(t=float(t)), ground)
        strike = made.radius > 2.0
        if not strike.any():
            continue
        n = np.arange(math.floor(t / every) - 1, math.floor(t / every) + 1)
        u = draws(1, n, 3, stream=1)[:, 0]  # strike n comes at (n + u) * every
        age = t - (n + u) * every
        began = np.empty(made.count)
        began[~strike] = t - (top - made.pos[~strike, 2]) / top * 1.0  # a drop's run takes fall_s
        began[strike] = t - age[(age >= 0.0) & (age < FLASH_S)]
        assert (np.diff(began) >= -1e-4).all()
        mixed += int(began[strike].min() < began[~strike].max())  # younger drops than a strike
    assert mixed > 100  # a strike in among the drops, not always last


def test_there_is_no_room_kept_for_lightning_that_never_comes() -> None:
    assert flashes_at_once(0.0) == 0


@pytest.mark.parametrize("per_min", [0.0, 4.0, 30.0, 200.0])  # the last is past the setting
@pytest.mark.parametrize("lamps", [100, 250, 500, 700])
def test_however_the_draws_fall_rain_never_passes_the_cap_on_a_crowded_home(
    monkeypatch: pytest.MonkeyPatch, lamps: int, per_min: float
) -> None:
    storm = _storm(drops_per_lamp=8.0, strikes_per_min=per_min, fall_s=1.0)
    served, most = worst_crowd(monkeypatch, rain_module, storm, bulbs(lamps), 20.0)
    fastest = max(per_min, float(RainStorm.parameters()["strikes_per_min"].max or 0.0))
    room = MAX_PARTICLES - flashes_at_once(fastest)  # kept for the lightning at its fastest
    assert served == min(lamps, room)
    each = room // served  # the rest of the cap, shared out in whole drops
    assert most == each  # the worst hand fills a lamp's share, and never past it
    assert served * most + flashes_at_once(per_min) <= MAX_PARTICLES
