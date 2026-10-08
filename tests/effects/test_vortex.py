from __future__ import annotations

import math

import numpy as np
import pytest
from conftest import tempo_ctx
from map_home import ROW, bulbs, leds_at, lights_at, upright
from stray_lamps import STRAYS, on_the_beat, run_heights, stays_in_band, unpassed

from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.effects.particle_tools import Ground
from dj_ledfx.effects.particles import MAX_PARTICLES, drawn
from dj_ledfx.effects.vortex import JITTER_M, LEAST_RADIUS_M, Vortex, kicked


def _room() -> LedSet:
    """Four upright lamps round a 4 x 4 m room under a 3 m ceiling: its middle is (2, 2)."""
    return lights_at(upright(0.5, 0.5), upright(3.5, 0.5), upright(3.5, 3.5), upright(0.5, 3.5))


def _vortex(**settings: object) -> Vortex:
    vortex = Vortex(**settings)
    vortex.reseed(1)
    return vortex


def _turn(pos: np.ndarray) -> np.ndarray:
    return np.arctan2(pos[:, 1] - 2.0, pos[:, 0] - 2.0)


def test_the_kick_puts_most_of_each_beats_turn_at_the_beat() -> None:
    assert kicked(7.0, 0.7) == 7.0 and kicked(8.0, 0.7) == 8.0  # whole beats stay whole
    assert kicked(7.5, 0.0) == 7.5  # no kick: even through the beat
    assert kicked(7.25, 0.7) - 7.0 > 0.45  # kicked: nearly half of it in the first quarter
    steps = [kicked(7.0 + i / 10, 0.7) for i in range(11)]
    assert all(b > a for a, b in zip(steps, steps[1:], strict=False))  # never back


def test_particles_spiral_up_round_the_middle_and_the_nearer_ones_turn_faster() -> None:
    room = _room()
    vortex = _vortex(kick=0.0, turns_per_bar=0.5)
    drawn(vortex, tempo_ctx(2000.0), room)
    first = vortex.particles.pos.copy()
    drawn(vortex, tempo_ctx(2000.4), room)
    then = vortex.particles.pos

    turned = np.mod(_turn(then) - _turn(first), 2.0 * math.pi)
    assert (turned > 0.0).all() and (turned < 0.5).all()  # all one way, a little
    out = np.linalg.norm(first[:, :2] - 2.0, axis=1)
    np.testing.assert_allclose(out, np.linalg.norm(then[:, :2] - 2.0, axis=1), atol=1e-5)
    assert np.corrcoef(out, turned)[0, 1] < -0.9  # the nearer, the faster
    rose = then[:, 2] - first[:, 2]
    assert ((rose > 0.0) | (rose < -2.5)).all()  # up, or back at the floor


def test_particles_glow_most_half_way_up() -> None:
    room = _room()
    vortex = _vortex(palette=["#ffffff"])
    drawn(vortex, tempo_ctx(2000.0), room)
    height = vortex.particles.pos[:, 2] / 3.0
    np.testing.assert_allclose(vortex.particles.colour[:, 0], np.sin(math.pi * height), atol=1e-5)


def test_the_rings_pass_through_leds_all_along_a_long_light() -> None:
    leds = leds_at(ROW)  # one light, 4 m long: the middle is its middle, (2, 0)
    vortex = _vortex()
    drawn(vortex, tempo_ctx(2000.0), leds)
    out = np.linalg.norm(vortex.particles.pos[:, :2] - np.array([2.0, 0.0]), axis=1)
    rings = np.abs(leds.pos[:, 0] - 2.0)  # each LED's distance from the middle
    assert (np.abs(out[:, None] - rings[None, :]).min(axis=1) <= JITTER_M + 1e-5).all()
    assert np.ptp(out) > 1.5  # rings through its ends as well as its middle


def test_the_rings_are_jittered_to_both_sides_of_the_lamps_ring() -> None:
    vortex = _vortex(count=300)
    drawn(vortex, tempo_ctx(2000.0), _room())
    out = np.linalg.norm(vortex.particles.pos[:, :2] - 2.0, axis=1)
    ring = math.hypot(1.5, 1.5)  # every lamp is this far from the middle
    assert out.min() >= ring - 0.2 - 1e-5 and out.max() <= ring + 0.2 + 1e-5
    assert out.min() < ring - 0.15 and out.max() > ring + 0.15  # in and out, both ways


def test_the_turn_follows_the_beat_count_the_nearer_ring_a_third_faster() -> None:
    room = _room()
    vortex = _vortex(kick=0.0, turns_per_bar=1.5)
    drawn(vortex, tempo_ctx(2000.0), room)
    first = vortex.particles.pos.copy()
    drawn(vortex, tempo_ctx(2001.0), room)  # a quarter of a bar on
    turned = np.mod(_turn(vortex.particles.pos) - _turn(first), 2.0 * math.pi)
    out = np.linalg.norm(first[:, :2] - 2.0, axis=1)
    speed = 1.5 * (1.4 - 0.6 * out / out.max())  # turns a bar, the widest ring's the slowest
    np.testing.assert_allclose(turned, 2.0 * math.pi * speed / 4.0, atol=1e-4)


def test_a_vortex_round_a_single_bulb_is_at_least_as_wide_as_the_least_radius() -> None:
    bulb = leds_at([[2.0, 2.0, 1.0]])
    vortex = _vortex(kick=0.0, turns_per_bar=1.0)
    drawn(vortex, tempo_ctx(2000.0), bulb)
    first = vortex.particles.pos.copy()
    drawn(vortex, tempo_ctx(2001.0), bulb)
    turned = np.mod(_turn(vortex.particles.pos) - _turn(first), 2.0 * math.pi)
    out = np.linalg.norm(first[:, :2] - 2.0, axis=1)
    assert out.max() <= JITTER_M + 1e-5  # on the bulb's own ring, give or take the jitter
    wide = out > 0.05  # a particle on the middle itself has no direction to turn
    assert wide.sum() > 10
    np.testing.assert_allclose(
        turned[wide], 2.0 * math.pi * (1.4 - 0.6 * out[wide] / LEAST_RADIUS_M) / 4.0, atol=1e-3
    )


def test_the_beat_kick_moves_the_turn_and_the_rise_along_by_the_kicked_count() -> None:
    room = _room()
    kicked_up, even = _vortex(kick=0.7), _vortex(kick=0.0)
    drawn(kicked_up, tempo_ctx(2000.25), room)
    drawn(even, tempo_ctx(kicked(2000.25, 0.7)), room)
    np.testing.assert_allclose(kicked_up.particles.pos, even.particles.pos, atol=1e-4)
    assert kicked(2000.25, 0.7) > 2000.4  # and that is well on from the quarter beat


def test_the_rise_takes_rise_bars_bars_from_the_floor_to_the_ceiling() -> None:
    room = _room()
    vortex = _vortex(kick=0.0, rise_bars=4.0)
    drawn(vortex, tempo_ctx(2000.0), room)
    first = vortex.particles.pos[:, 2].astype(np.float64)
    drawn(vortex, tempo_ctx(2004.0), room)  # a bar on: a quarter of the way up the 3 m
    np.testing.assert_allclose(np.mod(vortex.particles.pos[:, 2] - first, 3.0), 0.75, atol=1e-4)
    drawn(vortex, tempo_ctx(2016.0), room)  # four bars on: round again, to where it began
    np.testing.assert_allclose(vortex.particles.pos[:, 2], first, atol=1e-4)


def test_particles_run_from_the_lows_colour_to_the_highs() -> None:
    room = _room()
    vortex = _vortex(palette=["#000000", "#ffffff"])
    drawn(vortex, tempo_ctx(2000.0), room)
    height = vortex.particles.pos[:, 2] / 3.0
    expected = height * np.sin(math.pi * height)  # black at the floor, white at the ceiling
    np.testing.assert_allclose(vortex.particles.colour[:, 0], expected, atol=1e-5)


def test_the_settings_reach_the_particles() -> None:
    room = _room()
    vortex = _vortex(count=120, size=0.45)
    drawn(vortex, tempo_ctx(2000.0), room)
    assert vortex.particles.count == 120
    np.testing.assert_allclose(vortex.particles.radius, 0.45)


def test_the_particles_take_the_lamps_in_turn() -> None:
    row = lights_at(upright(0.0, 0.0), upright(2.0, 0.0), upright(4.0, 0.0))  # rings 2, 0, 2
    vortex = _vortex(count=60)
    drawn(vortex, tempo_ctx(2000.0), row)
    out = np.linalg.norm(vortex.particles.pos[:, :2] - np.array([2.0, 0.0]), axis=1)
    lamp = np.arange(60) % 3
    assert (out[lamp == 1] <= JITTER_M + 1e-5).all()  # the middle lamp's rings are the narrow ones
    assert (np.abs(out[lamp != 1] - 2.0) <= JITTER_M + 1e-5).all()


@pytest.mark.parametrize("where", STRAYS)
def test_the_rise_passes_every_led_of_a_lamp_outside_the_floor_and_ceiling(where: str) -> None:
    leds = STRAYS[where]
    z = run_heights(_vortex(), leds, moment=on_the_beat)
    assert np.ptp(z) > 0.1  # moving, not stuck in place
    assert unpassed(z, leds) == []  # up past the lamp's whole length
    assert stays_in_band(z, leds)  # and no further than the floor, the ceiling and the lamp


def test_with_lamps_in_the_band_the_rise_runs_from_the_floor_to_the_ceiling() -> None:
    z = run_heights(_vortex(), _room(), moment=on_the_beat)
    assert z.min() < 0.05 and z.max() > 2.95
    assert z.min() >= 0.0 and z.max() <= 3.0


def test_the_band_takes_in_the_lamps_that_stand_outside_it_wherever_they_are() -> None:
    low = lights_at(upright(0.5, 0.5, -1.0, -0.5), upright(3.5, 0.5, 0.1, 1.4))
    high = lights_at(upright(0.5, 0.5, 3.2, 3.5), upright(3.5, 0.5, 0.1, 1.4))
    for leds, floor, ceiling in ((low, -1.0, 3.0), (high, 0.0, 3.5)):
        z = run_heights(_vortex(), leds, moment=on_the_beat)
        assert z.min() == pytest.approx(floor, abs=0.05) and z.max() == pytest.approx(
            ceiling, abs=0.05
        )
        assert unpassed(z, leds) == []


def test_a_vortex_over_many_lamps_has_its_count_and_no_more() -> None:
    vortex = _vortex(count=300)
    made = vortex.positions(tempo_ctx(2000.0), Ground.of(bulbs(100)))
    assert made.count == 300 <= MAX_PARTICLES
