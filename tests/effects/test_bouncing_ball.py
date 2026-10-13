from __future__ import annotations

import numpy as np
import pytest
from conftest import tempo_ctx
from map_home import lights_at, upright

from dj_ledfx.effects.bouncing_ball import BouncingBall
from dj_ledfx.effects.color import palette_float
from dj_ledfx.effects.particles import drawn

# Three upright lamps and a bulb at the corners of a 4 x 4 m room, and where each one's
# foot is.
ROOM = lights_at(upright(0.5, 0.5), upright(3.5, 0.5), upright(3.5, 3.5), [(0.5, 3.5, 1.2)])
FEET = np.array([[0.5, 0.5, 0.1], [3.5, 0.5, 0.1], [3.5, 3.5, 0.1], [0.5, 3.5, 1.2]])


def _ball(**settings: object) -> BouncingBall:
    ball = BouncingBall(**settings)
    ball.reseed(1)
    return ball


def _landings(ball: BouncingBall, beats: range, bpm: float = 120.0) -> list[int]:
    """The foot the ball is on at each whole beat; it must be on one."""
    feet = []
    for beat in beats:
        drawn(ball, tempo_ctx(float(beat), bpm=bpm), ROOM)
        gaps = np.linalg.norm(FEET - ball.particles.pos[0], axis=1)
        assert gaps.min() < 1e-4
        feet.append(int(gaps.argmin()))
    return feet


@pytest.mark.parametrize("bpm", [30.0, 120.0, 300.0])
def test_the_ball_lands_on_a_lamps_foot_on_every_beat_at_any_tempo(bpm: float) -> None:
    feet = _landings(_ball(), range(2000, 2012), bpm)
    assert all(a != b for a, b in zip(feet, feet[1:], strict=False))  # never twice running
    for start in range(0, 12, 4):  # every lamp once a round
        assert sorted(feet[start : start + 4]) == [0, 1, 2, 3]


def test_the_ball_bounces_height_m_up_between_beats() -> None:
    ball = _ball(height_m=1.5)
    feet = _landings(ball, range(2000, 2009))
    for beat, (here, there) in enumerate(zip(feet, feet[1:], strict=False), start=2000):
        drawn(ball, tempo_ctx(beat + 0.5), ROOM)
        half_way = (FEET[here, 2] + FEET[there, 2]) / 2.0
        np.testing.assert_allclose(ball.particles.pos[0, 2], half_way + 1.5, atol=1e-5)


def test_the_ball_bounces_no_higher_than_the_ceiling() -> None:
    low = lights_at(upright(0.5, 0.5), upright(3.5, 0.5), [(0.5, 3.5, 1.2)], ceiling=1.5)
    ball = _ball(height_m=3.0)
    for beats in np.arange(2000.0, 2012.0, 0.05):
        drawn(ball, tempo_ctx(float(beats)), low)
        assert ball.particles.pos[0, 2] <= 1.5 + 1e-5


def test_the_ball_takes_the_next_colour_at_each_bounce() -> None:
    palette = ["#ff0000", "#00ff00", "#0000ff"]
    ball = _ball(palette=palette)
    for beat in range(2000, 2006):
        drawn(ball, tempo_ctx(beat + 0.25), ROOM)
        np.testing.assert_allclose(ball.particles.colour[0], palette_float(palette)[beat % 3])
