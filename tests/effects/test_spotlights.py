from __future__ import annotations

import numpy as np
from conftest import render_ctx
from map_home import lights_at, upright

from dj_ledfx.effects.particles import drawn
from dj_ledfx.effects.spotlights import Spotlights

# Five upright lamps round a room.
FIVE = lights_at(
    upright(0.5, 0.5), upright(4.5, 0.5), upright(4.5, 3.5), upright(0.5, 3.5), upright(2.5, 2.0)
)


def _spots(**settings: object) -> Spotlights:
    spots = Spotlights(**settings)
    spots.reseed(1)
    return spots


def _off_the_leds(pos: np.ndarray) -> np.ndarray:
    """How far each spotlight is from the nearest LED."""
    return np.linalg.norm(pos[:, None, :] - FIVE.pos[None, :, :], axis=2).min(axis=1)


def test_a_spotlight_rests_on_an_led_then_glides_to_the_next_lamp() -> None:
    spots = _spots(count=1, hold_s=4.0, move_s=3.0)
    resting, gliding, lamps = [], [], []
    for t in np.arange(700.0, 728.0, 0.25):  # four steps of 7 s
        drawn(spots, render_ctx(t=float(t)), FIVE)
        pos = spots.particles.pos
        if (t / 7.0) % 1.0 < 4.0 / 7.0:
            resting.append(_off_the_leds(pos)[0])
            lamps.append(int(np.argmin(np.linalg.norm(pos[0, :2] - FIVE.pos[::14, :2], axis=1))))
        else:
            gliding.append(_off_the_leds(pos)[0])
    assert max(resting) < 1e-4  # on an LED while it rests
    assert max(gliding) > 0.5  # between lamps as it glides
    visits = [lamp for lamp, before in zip(lamps, [-1, *lamps], strict=False) if lamp != before]
    assert len(visits) == 4  # a lamp a step, never one twice running


def test_with_one_lamp_a_spotlight_moves_up_and_down_it() -> None:
    one = lights_at(upright(2.0, 2.0))
    spots = _spots(count=3)
    heights = []
    for t in np.arange(700.0, 760.0, 0.5):
        drawn(spots, render_ctx(t=float(t)), one)
        np.testing.assert_allclose(spots.particles.pos[:, :2], [[2.0, 2.0]] * 3, atol=1e-5)
        heights.append(spots.particles.pos[:, 2])
    assert 0.1 - 1e-5 <= np.min(heights) and np.max(heights) <= 1.4 + 1e-5
    assert np.ptp(heights) > 0.5  # from one of its LEDs to another


def test_spotlights_set_off_at_even_shares_of_a_step_apart() -> None:
    spots = _spots(count=2, hold_s=4.0, move_s=3.0)
    for t in np.arange(700.0, 728.0, 0.25):
        drawn(spots, render_ctx(t=float(t)), FIVE)
        assert _off_the_leds(spots.particles.pos).min() < 1e-4  # one of the two rests
