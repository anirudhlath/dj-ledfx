from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
import pytest
from conftest import CallCounts, tempo_ctx
from map_home import HOMES, ROW, lights_at, upright
from stray_lamps import STRAYS, moves, on_the_beat, run_frames, stays_in_band

from dj_ledfx.effects import bouncing_ball as ball_module
from dj_ledfx.effects.bouncing_ball import BouncingBall
from dj_ledfx.effects.color import palette_float
from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.effects.particle_tools import Ground
from dj_ledfx.effects.particles import MAX_PARTICLES, drawn

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


ZONES: dict[str, Callable[[], LedSet]] = {**HOMES, "four lamps": lambda: ROOM}


def _where(ball: BouncingBall, room: LedSet, beats: float, bpm: float = 120.0) -> np.ndarray:
    """Where the ball is at this moment."""
    drawn(ball, tempo_ctx(beats, bpm=bpm), room)
    return ball.particles.pos[0].astype(np.float64)


@pytest.mark.parametrize("bpm", [30.0, 120.0, 300.0])
def test_the_ball_flies_a_ballistic_bounce_straight_across_in_time_at_any_tempo(
    bpm: float,
) -> None:
    ball = _ball(height_m=1.5)
    for beat in range(2000, 2008):
        here = _where(ball, ROOM, float(beat), bpm)
        there = _where(ball, ROOM, beat + 1.0, bpm)
        quarter = _where(ball, ROOM, beat + 0.25, bpm)
        np.testing.assert_allclose(quarter[:2], (here + 0.25 * (there - here))[:2], atol=1e-5)
        line = here[2] + 0.25 * (there[2] - here[2])
        assert quarter[2] == pytest.approx(line + 4.0 * 1.5 * 0.25 * 0.75, abs=1e-5)


@pytest.mark.parametrize("bpm", [30.0, 300.0])
def test_the_ball_follows_the_beat_count_not_the_tempo(bpm: float) -> None:
    steady, other = _ball(), _ball()
    for beats in (2000.0, 2000.5, 2001.3, 2006.9):
        drawn(steady, tempo_ctx(beats), ROOM)
        drawn(other, tempo_ctx(beats, bpm=bpm), ROOM)
        for got, want in (
            (other.particles.pos, steady.particles.pos),
            (other.particles.colour, steady.particles.colour),
            (other.particles.radius, steady.particles.radius),
        ):
            np.testing.assert_array_equal(got, want)


def test_the_bounce_rises_under_the_higher_ceiling_of_its_two_lamps_whichever_way_it_goes() -> (
    None
):
    """One lamp is in the band (a 3 m ceiling over its foot at 2.9 m). The other has an LED at
    3.4 m, which lifts its own ceiling to that (Ground.ceiling_for), and its foot at 1 m. A
    bounce between them has the room under 3.4 m over its higher foot, 0.5 m, to and fro."""
    room = lights_at([(0.5, 0.5, 2.9)], [(3.5, 0.5, 1.0), (3.5, 0.5, 3.4)])
    ball = _ball(height_m=1.5)
    for beat in range(2000, 2012):
        middle = _where(ball, room, beat + 0.5)
        assert middle[2] == pytest.approx((2.9 + 1.0) / 2.0 + 0.5, abs=1e-5)


def test_the_ball_rises_to_the_ceiling_and_no_higher_not_flat_along_it() -> None:
    """Bouncing 3 m from feet at 0.1 m under a 1.5 m ceiling, it bounces the 1.4 m of room
    instead: a parabola whose top is the ceiling, and not a stretch along it."""
    low = lights_at(upright(0.5, 0.5), upright(3.5, 0.5), ceiling=1.5)
    ball = _ball(height_m=3.0)
    for beat in range(2000, 2008):
        assert _where(ball, low, beat + 0.5)[2] == pytest.approx(1.5, abs=1e-5)
    z = np.concatenate(run_frames(_ball(height_m=3.0), low, moment=on_the_beat))
    assert z.max() <= 1.5 + 1e-5
    # The top of each bounce alone; flattened, over two in three.
    assert np.mean(z > 1.5 - 1e-3) < 0.2


def test_a_bounce_with_no_room_under_the_ceiling_stays_on_the_line_between_its_feet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The backstop for a ceiling under the feet, which Ground.ceiling_for never gives: there
    is no room to rise, and the ball doesn't dip under the line between its feet either."""

    def under_every_foot(self: Ground, stop: Any) -> Any:
        return np.full(np.shape(stop), 0.05)

    monkeypatch.setattr(Ground, "ceiling_for", under_every_foot)
    ball = _ball(height_m=1.5)
    for beat in range(2000, 2012):
        here = _where(ball, ROOM, float(beat))
        quarter = _where(ball, ROOM, beat + 0.25)
        there = _where(ball, ROOM, beat + 1.0)
        np.testing.assert_allclose(quarter, here + 0.25 * (there - here), atol=1e-5)


@pytest.mark.parametrize("where", STRAYS)
def test_the_ball_bounces_from_the_foot_of_a_lamp_outside_the_floor_and_ceiling(
    where: str,
) -> None:
    leds = STRAYS[where]
    frames = run_frames(_ball(height_m=1.5), leds, moment=on_the_beat)
    z = np.concatenate(frames)
    foot = float(leds.pos[:, 2].min())
    ceiling = max(Ground.of(leds).ceiling, float(leds.pos[:, 2].max()))
    assert moves(frames)  # bouncing from frame to frame, not just spread over heights
    assert z.min() == pytest.approx(foot, abs=1e-5)  # it lands on the lamp's foot, no lower
    assert z.max() == pytest.approx(min(foot + 1.5, ceiling), abs=1e-5)  # up, under its ceiling
    assert stays_in_band(z, leds)


def test_the_ball_lands_under_a_different_led_of_a_long_lamp_each_time() -> None:
    row_and_bulb = lights_at(ROW, [(2.0, 3.0, 1.0)])  # a 4 m row of 9 LEDs, and a bulb
    ball = _ball()
    landed = set()
    for beat in range(2000, 2060):
        drawn(ball, tempo_ctx(float(beat)), row_and_bulb)
        x, y, _ = ball.particles.pos[0]
        if y == 0.0:  # on the row
            landed.add(round(float(x), 3))
    assert len(landed) >= 6  # of its 9 LEDs, over 30 landings


def test_with_two_lamps_the_ball_goes_to_and_fro_and_with_one_it_stays_over_it() -> None:
    two = lights_at(upright(0.5, 0.5), upright(3.5, 0.5))
    ball = _ball()
    feet = [_where(ball, two, float(beat)) for beat in range(2000, 2008)]
    assert [round(float(f[0]), 1) for f in feet[:4]] in (
        [0.5, 3.5, 0.5, 3.5],
        [3.5, 0.5, 3.5, 0.5],
    )
    assert [round(float(f[0]), 1) for f in feet[4:]] == [round(float(f[0]), 1) for f in feet[:4]]
    one = lights_at(upright(2.0, 2.0))
    for beats in (2000.0, 2000.5, 2001.3, 2006.9):
        np.testing.assert_allclose(_where(ball, one, beats)[:2], [2.0, 2.0], atol=1e-6)


@pytest.mark.parametrize("home", ZONES)
def test_the_ball_is_one_particle_whatever_the_lamps(home: str) -> None:
    made = _ball().positions(tempo_ctx(2003.3), Ground.of(ZONES[home]()))
    assert made.count == 1 <= MAX_PARTICLES


def test_the_ball_is_as_big_as_the_setting_says() -> None:
    ball = _ball(size=0.9)
    drawn(ball, tempo_ctx(2003.3), ROOM)
    np.testing.assert_allclose(ball.particles.radius, 0.9)


def test_both_ends_of_a_bounce_are_worked_out_at_once(call_counts: CallCounts) -> None:
    call_counts.spy(ball_module, "tour")
    call_counts.spy(ball_module, "draws")
    call_counts.spy(Ground, "foot")

    drawn(_ball(), tempo_ctx(2003.3), ROOM)

    assert call_counts.calls == {"tour": 1, "draws": 1, "foot": 1}
