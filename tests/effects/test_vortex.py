from __future__ import annotations

import math

import numpy as np
from conftest import tempo_ctx
from map_home import ROW, leds_at, lights_at, upright

from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.effects.particles import drawn
from dj_ledfx.effects.vortex import JITTER_M, Vortex, kicked


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
