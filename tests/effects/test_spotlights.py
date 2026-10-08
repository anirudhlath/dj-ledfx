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


def _lamp_under(pos: np.ndarray) -> int:
    """The lamp a spotlight at `pos` is nearest to, seen from above."""
    return int(np.argmin(np.linalg.norm(FIVE.pos[::14, :2] - pos[:2], axis=1)))


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


def test_a_spotlight_glides_to_the_next_lamp_without_a_jump() -> None:
    spots = _spots(count=1, hold_s=4.0, move_s=3.0)
    last, steps = None, []
    for t in np.arange(700.0, 800.0, 0.05):
        drawn(spots, render_ctx(t=float(t)), FIVE)
        pos = spots.particles.pos[0].copy()
        if last is not None:
            steps.append(float(np.linalg.norm(pos - last)))
        last = pos
    # Corner to corner is 5 m in 3 s; the glide eases, so at most 1.5 times the mean speed: 0.13 m.
    assert 0.05 < max(steps) < 0.2


def test_there_are_two_spotlights_by_default() -> None:
    spots = _spots()
    drawn(spots, render_ctx(t=700.0), FIVE)
    assert spots.particles.count == 2


def test_the_settings_reach_the_spotlights() -> None:
    spots = _spots(count=3, palette=["#ff0000", "#00ff00"], size=1.5)
    drawn(spots, render_ctx(t=700.0), FIVE)
    np.testing.assert_allclose(spots.particles.radius, 1.5)
    np.testing.assert_allclose(spots.particles.colour, [[1, 0, 0], [0, 1, 0], [1, 0, 0]])


def test_each_spotlight_is_on_a_tour_of_its_own() -> None:
    spots = _spots(count=2, hold_s=4.0, move_s=3.0)
    resting = shared = 0
    for t in np.arange(700.0, 1400.0, 0.25):
        drawn(spots, render_ctx(t=float(t)), FIVE)
        pos = spots.particles.pos
        if (_off_the_leds(pos) < 1e-4).all():  # both rest on a lamp
            resting += 1
            shared += _lamp_under(pos[0]) == _lamp_under(pos[1])
    assert resting > 300
    assert shared < 0.35 * resting  # about one time in five, as chance has it, not half


def test_a_spotlight_sets_off_gently() -> None:
    spots = _spots(count=1, hold_s=4.0, move_s=3.0)  # a step is 7 s: rest till 704, glide to 707

    def at(t: float) -> np.ndarray:
        drawn(spots, render_ctx(t=t), FIVE)
        return spots.particles.pos[0].copy()

    start = float(np.linalg.norm(at(704.1) - at(704.0)))
    middle = float(np.linalg.norm(at(705.55) - at(705.45)))
    assert middle > 0.1  # a tenth of a second of the 2.5 to 5 m glide, at its quickest
    assert start < 0.3 * middle


def test_another_seed_tours_the_lamps_in_another_order() -> None:
    tours = set()
    for seed in (1, 2, 3):
        spots = Spotlights(count=1, hold_s=4.0, move_s=3.0)
        spots.reseed(seed)
        lamps = []
        for step in range(5):  # a step is 7 s: the spotlight rests for the first 4
            drawn(spots, render_ctx(t=700.0 + 7.0 * step + 2.0), FIVE)
            lamps.append(_lamp_under(spots.particles.pos[0]))
        tours.add(tuple(lamps))
    assert len(tours) == 3
