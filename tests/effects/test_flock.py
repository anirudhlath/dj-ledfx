from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import replace
from typing import Any

import numpy as np
import pytest
from conftest import CallCounts, tempo_ctx
from map_home import HOMES, lights_at, upright
from stray_lamps import STRAYS, moves, on_the_beat, run_frames, stays_in_band, unpassed

from dj_ledfx.effects import flock as flock_module
from dj_ledfx.effects.easing import ease_in_out
from dj_ledfx.effects.flock import FLAT, MOVE_BARS, Flock, scattered
from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.effects.particle_tools import Ground
from dj_ledfx.effects.particles import MAX_PARTICLES, drawn
from dj_ledfx.tempo.model import BEATS_PER_BAR

# Four upright lamps at the corners of a 4 x 4 m room.
ROOM = lights_at(upright(0.5, 0.5), upright(3.5, 0.5), upright(3.5, 3.5), upright(0.5, 3.5))


def _flock(**settings: object) -> Flock:
    flock = Flock(**settings)
    flock.reseed(1)
    return flock


def _spread(flock: Flock, beats: float, bpm: float = 120.0) -> float:
    """How far the birds are from their middle, on average, seen from above, at this moment.
    Seen from above: the flock's height is fitted to the room over and under it, which a
    middle near the floor squeezes, but how far it spreads sideways is `scattered` alone."""
    drawn(flock, tempo_ctx(beats, bpm=bpm), ROOM)
    pos = flock.particles.pos[:, :2]
    return float(np.linalg.norm(pos - pos.mean(axis=0), axis=1).mean())


def test_the_flock_gathers_round_an_led_of_each_lamp_in_turn() -> None:
    flock = _flock(spread_m=0.2)
    lamps = []
    for bar in range(500, 512, 2):  # it comes to a lamp on every other downbeat
        drawn(flock, tempo_ctx(4.0 * bar), ROOM)
        gaps = np.linalg.norm(flock.particles.pos[:, None, :] - ROOM.pos[None, :, :], axis=2)
        led = int(gaps.max(axis=0).argmin())  # the LED every bird is nearest together
        assert gaps[:, led].max() <= 0.2 + 1e-5
        lamps.append(led // 14)
    assert all(a != b for a, b in zip(lamps, lamps[1:], strict=False))
    assert set(lamps) == {0, 1, 2, 3}


def test_the_flock_scatters_on_every_other_downbeat_and_gathers_again() -> None:
    flock = _flock(scatter=3.0)
    gathered = _spread(flock, 2000.0)  # beat 2000: it has just come to a lamp
    np.testing.assert_allclose(_spread(flock, 2000.75), 3.0 * gathered, rtol=1e-4)
    assert _spread(flock, 2003.0) < 1.5 * gathered  # gathering again by the bar's end
    assert _spread(flock, 2004.75) < 1.2 * gathered  # the bar between: no scatter


def test_the_flock_moves_on_the_beat_at_any_tempo() -> None:
    slow, fast = _flock(), _flock()
    for beats in (2000.0, 2001.3, 2006.9):
        drawn(slow, tempo_ctx(beats, bpm=30.0), ROOM)
        drawn(fast, tempo_ctx(beats, bpm=300.0), ROOM)
        np.testing.assert_array_equal(slow.particles.pos, fast.particles.pos)


ZONES: dict[str, Callable[[], LedSet]] = {**HOMES, "four lamps": lambda: ROOM}
MOVE_BEATS = BEATS_PER_BAR * MOVE_BARS  # the beats a flock takes from one lamp to the next
LIFT = 20.0  # metres: a zone's roomy twin is this much higher, under a ceiling at 2 * LIFT


def _bulb(height: float, ceiling: float = 3.0) -> LedSet:
    """One bulb, so the flock's middle is always at the bulb."""
    return lights_at([(1.0, 1.0, height)], ceiling=ceiling)


def _places(
    flock: Flock, leds: LedSet, beats: float, bpm: float = 120.0
) -> tuple[np.ndarray, np.ndarray]:
    """The birds' places at this moment, and where the flock's middle is (a bulb)."""
    drawn(flock, tempo_ctx(beats, bpm=bpm), leds)
    return flock.particles.pos.astype(np.float64), leds.pos[0].astype(np.float64)


def _roomy(leds: LedSet) -> LedSet:
    """The zone's twin with all the room a flock could want over and under its lamps (the
    largest goes 12 m either way): the same LEDs LIFT metres higher, under a ceiling at
    2 * LIFT."""
    lift = np.array([0.0, 0.0, LIFT])
    low, high = leds.bounds
    return replace(
        leds.moved(leds.pos.astype(np.float64) + lift),
        bounds=(low + lift.astype(np.float32), high + lift.astype(np.float32)),
        space=replace(leds.space, ceiling=2.0 * LIFT),
    )


def _free(flock: Flock, leds: LedSet, beats: float) -> np.ndarray:
    """Where the birds would be with all the room they could want: the flock round the same
    lamps in the zone's roomy twin, brought back down to them."""
    made = flock.positions(tempo_ctx(beats), Ground.of(_roomy(leds)))
    return made.pos.astype(np.float64) - np.array([0.0, 0.0, LIFT])


def _farthest(spread: float, scatter: float, beats: float) -> float:
    """How far up or down the farthest bird of a flock can go from its middle: its spread,
    scattered, FLAT of it."""
    return FLAT * spread * scattered(beats % MOVE_BEATS, scatter)


def _with_the_room(
    free: np.ndarray, room_under: float, room_over: float, farthest: float
) -> np.ndarray:
    """The birds' heights from the middle of a flock whose farthest bird goes `farthest` up
    or down, given their `free` heights and this much room over and under the middle: each
    side's heights scaled to the room on it when that is less than the farthest."""
    fit_up, fit_down = min(1.0, room_over / farthest), min(1.0, room_under / farthest)
    return free * np.where(free > 0.0, fit_up, fit_down)


def test_scattered_is_1_on_the_downbeat_its_scatter_at_the_peak_and_back_to_1_after() -> None:
    assert scattered(0.0, 3.0) == 1.0
    assert scattered(0.75, 3.0) == pytest.approx(3.0)
    assert scattered(0.75, 8.0) == pytest.approx(8.0)
    rising = [scattered(since, 3.0) for since in np.linspace(0.0, 0.75, 20)]
    falling = [scattered(since, 3.0) for since in np.linspace(0.75, 8.0, 60)]
    assert all(a < b for a, b in zip(rising, rising[1:], strict=False))
    assert all(a > b for a, b in zip(falling, falling[1:], strict=False))
    assert scattered(8.0, 8.0) < 1.01  # the flock has gathered again by the next move
    assert all(scattered(since, 1.0) == 1.0 for since in np.linspace(0.0, 8.0, 30))


@pytest.mark.parametrize("bpm", [30.0, 120.0, 300.0])
def test_the_scatter_peaks_three_quarters_of_a_beat_after_the_downbeat_at_any_tempo(
    bpm: float,
) -> None:
    flock = _flock(scatter=3.0)
    gathered = _spread(flock, 2000.0, bpm)
    np.testing.assert_allclose(_spread(flock, 2000.75, bpm), 3.0 * gathered, rtol=1e-4)
    assert _spread(flock, 2003.0, bpm) < 1.5 * gathered
    assert _spread(flock, 2004.75, bpm) < 1.2 * gathered  # the bar between: no scatter


@pytest.mark.parametrize("bpm", [30.0, 300.0])
def test_the_flock_follows_the_beat_count_not_the_tempo_in_all_it_does(bpm: float) -> None:
    steady, other = _flock(count=60), _flock(count=60)
    for beats in (2000.0, 2000.75, 2001.3, 2003.9, 2006.9):
        drawn(steady, tempo_ctx(beats), ROOM)
        drawn(other, tempo_ctx(beats, bpm=bpm), ROOM)
        for got, want in (
            (other.particles.pos, steady.particles.pos),
            (other.particles.colour, steady.particles.colour),
            (other.particles.radius, steady.particles.radius),
        ):
            np.testing.assert_array_equal(got, want)


def test_the_birds_fill_a_ball_flatter_than_it_is_wide_evenly_when_the_room_lets_them() -> None:
    """Gathered on a lamp, with the room they want, the birds are spread through a ball of
    spread_m metres round the middle, FLAT as high as it is wide: none outside it, an eighth
    in its inner half, as many above the middle as below it, and some out near its surface."""
    spread = 0.8
    flock = _flock(count=200, spread_m=spread)
    room = _bulb(1.5)  # 1.5 m each way: the farthest a bird goes, 0.4 m, fits
    for beats in (2000.0, 2008.0, 2016.0):  # a lamp at each: the flock has just come to it
        pos, middle = _places(flock, room, beats)
        apart = pos - middle
        wide = np.linalg.norm(apart[:, :2], axis=1)
        out = np.sqrt(wide**2 + (apart[:, 2] / FLAT) ** 2) / spread  # the ball's own measure
        assert out.max() <= 1.0 + 1e-5 and out.max() > 0.95
        assert 0.08 < np.mean(out < 0.5) < 0.2  # 0.125 in a ball of even birds
        assert 0.4 < np.mean(apart[:, 2] > 0.0) < 0.6
        assert 0.9 * spread < wide.max() <= spread + 1e-5
        assert 0.9 * FLAT * spread < np.abs(apart[:, 2]).max() <= FLAT * spread + 1e-5


def test_the_whole_flock_turns_once_every_two_bars_about_its_middle() -> None:
    flock = _flock(count=12, scatter=1.0)  # no scatter: the turn alone
    before, _ = _places(flock, ROOM, 2001.2)
    after, _ = _places(flock, ROOM, 2002.2)  # a beat on: an eighth of a turn
    again, _ = _places(flock, ROOM, 2009.2)  # eight beats on: the whole turn, and the move on
    apart_before = (before - before[0])[1:, :2]
    apart_after = (after - after[0])[1:, :2]
    turn = np.arctan2(apart_after[:, 1], apart_after[:, 0]) - np.arctan2(
        apart_before[:, 1], apart_before[:, 0]
    )
    np.testing.assert_allclose(np.mod(turn, 2.0 * math.pi), math.pi / 4.0, atol=1e-4)
    np.testing.assert_allclose(
        np.linalg.norm(apart_after, axis=1), np.linalg.norm(apart_before, axis=1), atol=1e-5
    )
    np.testing.assert_allclose((again - again[0])[:, :2], (before - before[0])[:, :2], atol=1e-4)


def test_the_flock_moves_from_lamp_to_lamp_easing_in_and_out_over_two_bars() -> None:
    far = lights_at([(0.0, 0.0, 1.0)], [(10.0, 0.0, 1.0)])
    flock = _flock(count=200, spread_m=0.2, scatter=1.0)
    positions = []
    for beats in (2000.0, 2002.0, 2004.0, 2006.0, 2008.0):  # a quarter of the move at a time
        drawn(flock, tempo_ctx(beats), far)
        positions.append(flock.particles.pos[:, 0].mean())
    # Eased in and out: the smoothstep takes 5/32 of the way in the first quarter and half
    # of it by the middle; the flock is at a lamp at each end.
    here, there = positions[0], positions[-1]
    assert abs(abs(there - here) - 10.0) < 0.1
    shares = [abs(x - here) / 10.0 for x in positions]
    np.testing.assert_allclose(shares, [0.0, 5.0 / 32.0, 0.5, 27.0 / 32.0, 1.0], atol=0.02)


@pytest.mark.parametrize("room_over", [0.1, 0.4, 2.0])
def test_the_flocks_height_is_scaled_to_the_room_over_it_when_there_is_less_than_it_needs(
    room_over: float,
) -> None:
    """A flock whose birds go up to `farthest` fits that to the room over its middle, the
    birds above it in proportion, and leaves the side with room, and its width, as it is."""
    flock = _flock(count=80, spread_m=0.8, scatter=3.0)
    room = _bulb(5.0, ceiling=5.0 + room_over)  # 5 m of room under it
    for beats in (2000.0, 2000.75, 2002.5, 2006.0):
        pos, middle = _places(flock, room, beats)
        free = _free(flock, room, beats) - middle
        expected = _with_the_room(free[:, 2], 5.0, room_over, _farthest(0.8, 3.0, beats))
        np.testing.assert_allclose(pos[:, :2] - middle[:2], free[:, :2], atol=1e-5)
        np.testing.assert_allclose(pos[:, 2] - middle[2], expected, atol=1e-5)


@pytest.mark.parametrize("room_under", [0.1, 0.4, 2.0])
def test_the_flocks_height_is_scaled_to_the_room_under_it_when_there_is_less_than_it_needs(
    room_under: float,
) -> None:
    flock = _flock(count=80, spread_m=0.8, scatter=3.0)
    room = _bulb(room_under, ceiling=10.0)  # 10 m of room over it
    for beats in (2000.0, 2000.75, 2002.5, 2006.0):
        pos, middle = _places(flock, room, beats)
        free = _free(flock, room, beats) - middle
        expected = _with_the_room(free[:, 2], room_under, 10.0, _farthest(0.8, 3.0, beats))
        np.testing.assert_allclose(pos[:, :2] - middle[:2], free[:, :2], atol=1e-5)
        np.testing.assert_allclose(pos[:, 2] - middle[2], expected, atol=1e-5)


def _heights_at_the_largest(height: float) -> np.ndarray:
    """The heights of every bird of the largest flock over 16 beats, round a bulb."""
    flock = _flock(count=200, spread_m=3.0, scatter=8.0)
    room = _bulb(height)
    return np.concatenate(
        [_places(flock, room, float(beats))[0][:, 2] for beats in np.arange(2000.0, 2016.0, 0.25)]
    )


@pytest.mark.parametrize("height", [0.05, 0.5, 1.5, 2.5, 2.95])
def test_a_flock_at_its_largest_stays_inside_the_room_even_with_its_middle_at_an_edge(
    height: float,
) -> None:
    z = _heights_at_the_largest(height)
    assert z.min() > 0.0 and z.max() < 3.0  # inside the room, not on the floor or the ceiling


@pytest.mark.parametrize("height", [0.5, 1.5, 2.5])
def test_a_flock_at_its_largest_spreads_through_the_room_instead_of_piling_up_on_the_edges(
    height: float,
) -> None:
    z = _heights_at_the_largest(height)
    assert z.min() < 0.2 and z.max() > 2.8  # birds almost to the floor and to the ceiling …
    assert np.mean(z < 0.01) < 0.01 and np.mean(z > 2.99) < 0.01  # … but no sheet on either


def test_the_flock_does_not_jump_at_the_downbeat_between_lamps_with_different_bands() -> None:
    """Two lamps in the band and one under the floor: the flock's room under its middle
    differs from one pair of lamps to the next, and it is the band of the lamp it is at
    that counts at the downbeat, whichever lamp it came from and goes to."""
    zone = lights_at(
        upright(0.5, 0.5), upright(3.5, 0.5), upright(2.0, 3.5, -1.0, -0.5), ceiling=3.0
    )
    flock = _flock(count=200, scatter=1.0)
    steps = []
    for move in range(2000 // 8, 2000 // 8 + 40):  # across 40 downbeats
        beat = 8.0 * move
        before, _ = _places(flock, zone, beat - 1e-6)
        after, _ = _places(flock, zone, beat + 1e-6)
        steps.append(np.linalg.norm(after - before, axis=1).max())
    assert max(steps) < 1e-3


@pytest.mark.parametrize("where", STRAYS)
def test_the_flock_gathers_along_the_whole_length_of_a_lamp_outside_the_floor_and_ceiling(
    where: str,
) -> None:
    leds = STRAYS[where]
    frames = run_frames(_flock(), leds, moment=on_the_beat)
    z = np.concatenate(frames)
    assert moves(frames)  # swirling from frame to frame, not just spread over heights
    assert unpassed(z, leds) == []  # gathering round the lamp's whole length
    assert stays_in_band(z, leds)  # and no bird past the floor, the ceiling or the lamp


def test_between_a_lamp_in_the_band_and_one_over_the_ceiling_the_flock_stays_between_them() -> (
    None
):
    zone = lights_at(upright(0.5, 0.5), upright(3.5, 0.5, 3.2, 3.5), ceiling=3.0)
    flock = _flock(count=200, spread_m=3.0, scatter=8.0)
    frames = run_frames(flock, zone, seconds=40.0, moment=on_the_beat)
    z = np.concatenate(frames)
    assert z.min() >= 0.0 - 1e-5 and z.max() <= 3.5 + 1e-5  # the zone's floor to the lamp's top
    assert z.max() > 3.0  # the flock does go up round the high lamp


@pytest.mark.parametrize(
    ("z_a", "z_b", "room_under", "room_over"),
    [
        (1.0, -0.6, 0.5, 2.8),  # a lamp in the band, one under the floor
        (2.0, 3.6, 2.8, 0.5),  # a lamp in the band, one over the ceiling
    ],
)
def test_half_way_between_two_lamps_the_flock_has_the_room_of_the_band_half_way_between_theirs(
    z_a: float, z_b: float, room_under: float, room_over: float
) -> None:
    """The band of the lamp it leaves is blended into that of the lamp it comes to by the
    share of the move done, as the flock's middle is: half-way, the band is half-way between
    the two lamps' bands (a 3 m ceiling, and the floor, widened to each lamp's own LEDs)."""
    zone = lights_at([(1.0, 1.0, z_a)], [(3.0, 1.0, z_b)], ceiling=3.0)
    flock = _flock(count=200, spread_m=3.0, scatter=1.0)
    beats = 2000.0 + MOVE_BEATS / 2.0
    pos, _ = _places(flock, zone, beats)
    middle = zone.pos.astype(np.float64).mean(axis=0)  # two single LEDs: half-way between them
    free = _free(flock, zone, beats) - middle
    expected = _with_the_room(free[:, 2], room_under, room_over, _farthest(3.0, 1.0, beats))
    np.testing.assert_allclose(pos[:, :2] - middle[:2], free[:, :2], atol=1e-5)
    np.testing.assert_allclose(pos[:, 2] - middle[2], expected, atol=1e-5)


@pytest.mark.parametrize(
    ("trip", "leaves_the_one_in_the_band"),
    [(250, True), (251, False)],
    ids=["leaving the lamp in the band", "coming to it"],
)
def test_the_band_goes_from_the_lamp_the_flock_leaves_to_the_one_it_comes_to_either_way(
    trip: int, leaves_the_one_in_the_band: bool
) -> None:
    """A lamp in the band and one under the floor, a flock a quarter of the way along a move
    between them, one way or the other: its room is that of a band a quarter of the way from
    the band of the lamp it leaves to that of the lamp it comes to. Half-way can't tell the
    way (above); a quarter of the way can."""
    zone = lights_at([(1.0, 1.0, 1.0)], [(3.0, 1.0, -0.6)], ceiling=3.0)
    flock = _flock(count=200, spread_m=3.0, scatter=1.0)
    start, _ = _places(flock, zone, MOVE_BEATS * trip)  # gathered on the lamp it leaves
    assert (start[:, 0].mean() < 2.0) == leaves_the_one_in_the_band
    share = ease_in_out(0.25)  # a quarter of the move done, eased
    if leaves_the_one_in_the_band:  # the middle from z = 1, the floor from 0, to -0.6 and -0.6
        middle_z, room_under = 1.0 - 1.6 * share, 1.0 - share
    else:  # from -0.6 and -0.6 to 1 and 0
        middle_z, room_under = -0.6 + 1.6 * share, share
    beats = MOVE_BEATS * trip + MOVE_BEATS / 4.0
    pos, _ = _places(flock, zone, beats)
    free = _free(flock, zone, beats)
    expected = _with_the_room(
        free[:, 2] - middle_z, room_under, 3.0 - middle_z, _farthest(3.0, 1.0, beats)
    )
    np.testing.assert_allclose(pos[:, :2], free[:, :2], atol=1e-5)
    np.testing.assert_allclose(pos[:, 2] - middle_z, expected, atol=1e-5)


@pytest.mark.parametrize("side", ["over", "under"])
def test_a_band_with_no_room_on_a_side_of_the_middle_leaves_the_birds_that_way_at_its_height(
    monkeypatch: pytest.MonkeyPatch, side: str
) -> None:
    """The backstop for a band that is not around the lamp, which Ground never gives: the
    birds that go to the side without room stay level with the middle, not thrown to the
    other, and the birds going the other way are as free as ever."""

    def level_with_nothing(self: Ground, stop: Any) -> Any:
        return np.full(np.shape(stop), 0.1 if side == "over" else 2.9)

    monkeypatch.setattr(
        Ground, "ceiling_for" if side == "over" else "floor_for", level_with_nothing
    )
    flock = _flock(count=80, spread_m=0.8, scatter=3.0)
    room = _bulb(1.5)  # a ceiling at 0.1 m, or a floor at 2.9 m: no room on that side
    for beats in (2000.0, 2000.75, 2002.5, 2006.0):
        pos, middle = _places(flock, room, beats)
        free = _free(flock, room, beats) - middle
        shut = free[:, 2] > 0.0 if side == "over" else free[:, 2] < 0.0
        np.testing.assert_allclose(
            pos[:, 2] - middle[2], np.where(shut, 0.0, free[:, 2]), atol=1e-5
        )


def test_a_birds_colour_does_not_go_with_where_it_is_in_the_flock() -> None:
    flock = _flock(count=200, spread_m=1.0, palette=["#000000", "#ffffff"])
    pos, middle = _places(flock, _bulb(1.5), 2000.0)
    shade = flock.particles.colour[:, 0].astype(np.float64)
    apart = pos - middle
    for along in (
        np.linalg.norm(apart, axis=1),  # how far out
        apart[:, 2],  # how high
        np.arctan2(apart[:, 1], apart[:, 0]),  # which way round
    ):
        assert abs(np.corrcoef(shade, along)[0, 1]) < 0.25
    assert shade.min() < 0.1 and shade.max() > 0.9  # birds all along the palette


@pytest.mark.parametrize("home", ZONES)
def test_the_count_is_the_count_setting_whatever_the_lamps(home: str) -> None:
    ground = Ground.of(ZONES[home]())
    for count in (5, 40, 200):
        made = _flock(count=count).positions(tempo_ctx(2003.3), ground)
        assert made.count == count <= MAX_PARTICLES


def test_the_settings_reach_the_birds() -> None:
    flock = _flock(count=200, palette=["#ff0000", "#0000ff"], size=0.35)
    drawn(flock, tempo_ctx(2003.3), ROOM)
    colour = flock.particles.colour
    np.testing.assert_allclose(flock.particles.radius, 0.35)
    assert not colour[:, 1].any()  # red to blue, nothing else
    np.testing.assert_allclose(colour[:, 0] + colour[:, 2], 1.0, atol=1e-6)
    assert colour[:, 0].min() < 0.1 and colour[:, 0].max() > 0.9  # birds all along it


def test_every_bird_is_worked_out_at_once(call_counts: CallCounts) -> None:
    call_counts.spy(flock_module, "tour")
    call_counts.spy(flock_module, "draws")
    call_counts.spy(Ground, "on")

    for count in (5, 200):  # however many birds
        call_counts.calls.clear()
        drawn(_flock(count=count), tempo_ctx(2003.3), ROOM)
        assert call_counts.calls == {"tour": 1, "draws": 2, "on": 1}
