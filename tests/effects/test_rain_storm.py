from __future__ import annotations

import numpy as np
from conftest import render_ctx
from map_home import ROW, bulbs, leds_at, lights_at, upright

from dj_ledfx.effects.particle_tools import Ground, lamps_of
from dj_ledfx.effects.particles import MAX_PARTICLES, drawn
from dj_ledfx.effects.rain_storm import (
    EDGE,
    FLASH_S,
    JITTER_M,
    OVER_M,
    UNDER_M,
    RainStorm,
    flash,
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
    np.testing.assert_allclose(ran, (1.3 + OVER_M + UNDER_M) * 0.05 / 2.5, atol=1e-4)


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
        share = (1.4 + OVER_M - z) / (1.3 + OVER_M + UNDER_M)  # how far down its run
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


def test_the_cap_keeps_the_newest_drops_and_the_lightning() -> None:
    crowd = bulbs(100)  # 800 drops asked for
    ground, storm = Ground.of(crowd), _storm(drops_per_lamp=8.0, strikes_per_min=30.0)
    struck = 0
    for t in np.arange(500.0, 520.0, 0.1):
        ctx = render_ctx(t=float(t))
        asked = storm.positions(ctx, ground)
        drawn(storm, ctx, crowd)
        assert asked.count > MAX_PARTICLES == storm.particles.count
        drops = asked.pick(asked.radius < 1.0)
        assert (np.diff(drops.pos[:, 2]) >= -1e-6).all()  # the oldest, lowest, come first
        struck += bool((asked.radius > 2.0).any())
        assert (storm.particles.radius > 2.0).any() == (asked.radius > 2.0).any()
    assert struck > 10
