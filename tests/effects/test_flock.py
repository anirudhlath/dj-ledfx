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
from dj_ledfx.effects.flock import FLAT, MOVE_BEATS, Flock, scattered
from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.effects.particle_tools import Ground
from dj_ledfx.effects.particles import MAX_PARTICLES, drawn

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


def test_scattered_is_1_on_the_downbeat_its_scatter_at_the_peak_and_back_to_1_after() -> None:
    assert scattered(0.0, 3.0) == 1.0
    assert scattered(0.75, 3.0) == pytest.approx(3.0)
    assert scattered(0.75, 8.0) == pytest.approx(8.0)
    rising = [scattered(since, 3.0) for since in np.linspace(0.0, 0.75, 20)]
    falling = [scattered(since, 3.0) for since in np.linspace(0.75, MOVE_BEATS, 60)]
    assert all(a < b for a, b in zip(rising, rising[1:], strict=False))
    assert all(a > b for a, b in zip(falling, falling[1:], strict=False))
    assert all(scattered(since, 1.0) == 1.0 for since in np.linspace(0.0, MOVE_BEATS, 30))


@pytest.mark.parametrize("scatter", [1.5, 3.0, 8.0])
def test_scattered_is_exactly_1_again_when_the_next_move_opens(scatter: float) -> None:
    """The next scatter opens where this one closes, not 0.5 % wide of it: a flock that is
    scattered at the end of a move would jump back to its places on the downbeat."""
    assert scattered(MOVE_BEATS, scatter) == 1.0
    assert scattered(MOVE_BEATS - 1e-9, scatter) == pytest.approx(1.0, abs=1e-8)


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


@pytest.mark.parametrize(
    ("height", "beats", "shift"),
    [
        (1.5, 2000.0, 0.0),  # room to spare both ways: round its LED, unmoved
        (1.5, 2000.75, 0.0),  # … and at the scatter's peak, 1.2 m for its farthest bird
        (0.45, 2000.0, 0.0),  # 0.45 m over the floor is room enough for 0.4 m
        (0.1, 2000.0, 0.3),  # 0.3 m short of the 0.4 m under it: up by that, every bird
        (0.0, 2000.0, 0.4),  # on the floor: up by all of it
        (2.9, 2000.0, -0.3),
        (3.0, 2000.0, -0.4),  # on the ceiling: down by all of it
        (1.0, 2000.75, 0.2),  # a metre under it is 0.2 m short of the peak's 1.2 m
        (0.1, 2000.75, 1.1),
        (2.9, 2000.75, -1.1),
    ],
)
def test_a_flock_short_of_room_on_a_side_moves_in_from_it_whole_instead_of_lying_along_it(
    height: float, beats: float, shift: float
) -> None:
    """The farthest bird of this flock goes 0.4 m up or down (1.2 m at the scatter's peak). With
    less room than that on a side the flock moves in from it by the shortfall, every bird by the
    same, so it keeps its shape and is not flattened against the floor or the ceiling; where it
    has the room it stays round its LED, unmoved."""
    flock = _flock(count=80, spread_m=0.8, scatter=3.0)
    room = _bulb(height)  # a 3 m ceiling over the floor
    pos, _ = _places(flock, room, beats)
    free = _free(flock, room, beats)
    np.testing.assert_allclose(pos[:, :2], free[:, :2], atol=1e-5)
    np.testing.assert_allclose(pos[:, 2] - free[:, 2], shift, atol=1e-5)
    assert pos[:, 2].min() >= 0.0 and pos[:, 2].max() <= 3.0  # and in the room


@pytest.mark.parametrize("beats", [2000.0, 2000.75, 2003.0])
def test_a_band_less_high_than_the_flock_is_filled_by_it_scaled_to_fit(beats: float) -> None:
    """A band of 0.5 m (a bulb 0.1 m up under a ceiling at 0.5 m) is less high than the flock,
    0.8 m and more as it scatters. Then, and only then, the flock is scaled: about the band's
    middle, so that its farthest bird would come just to the edges, the birds in proportion."""
    flock = _flock(count=80, spread_m=0.8, scatter=3.0)
    room = _bulb(0.1, ceiling=0.5)
    pos, middle = _places(flock, room, beats)
    free = _free(flock, room, beats)
    fit = 0.25 / _farthest(0.8, 3.0, beats)
    np.testing.assert_allclose(pos[:, :2], free[:, :2], atol=1e-5)
    np.testing.assert_allclose(pos[:, 2], 0.25 + fit * (free[:, 2] - middle[2]), atol=1e-5)
    assert pos[:, 2].min() > 0.0 and pos[:, 2].max() < 0.5


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


BAND_ZONES: dict[str, LedSet] = {
    # two lamps in the band and one under the floor: a different band from one pair to the next
    "one lamp under the floor": lights_at(
        upright(0.5, 0.5), upright(3.5, 0.5), upright(2.0, 3.5, -1.0, -0.5), ceiling=3.0
    ),
    # lamps whose ends are at the floor and at the ceiling: a flock gathered there is moved in
    "lamps from the floor to the ceiling": lights_at(
        upright(0.5, 0.5, 0.0, 1.4), upright(3.5, 0.5, 1.6, 3.0), upright(2.0, 3.5), ceiling=3.0
    ),
    # no map: a band of half a metre, less high than a flock, which is scaled to fit it
    "bulbs with no map": lights_at(*[[(float(x), 0.0, 1.0)] for x in range(4)], ceiling=None),
}
SCATTERS: dict[str, dict[str, float]] = {
    "no scatter": {"scatter": 1.0},
    "the default": {"scatter": 3.0},
    "the largest": {"scatter": 8.0, "spread_m": 3.0},
}


@pytest.mark.parametrize("settings", SCATTERS.values(), ids=list(SCATTERS))
@pytest.mark.parametrize("where", BAND_ZONES)
def test_the_flock_does_not_jump_at_the_downbeat_whatever_its_scatter_and_the_lamps_bands(
    where: str, settings: dict[str, float]
) -> None:
    """At the downbeat the flock's middle, its band, its scatter and so the way it gives way to
    the band all carry on from the move before: the flock comes to a lamp in the band of the lamp
    it was leaving, scattered as it was, so no bird pops anywhere."""
    flock = _flock(count=200, **settings)
    steps = []
    for move in range(2000 // 8, 2000 // 8 + 40):  # across 40 downbeats
        beat = float(MOVE_BEATS * move)
        before, _ = _places(flock, BAND_ZONES[where], beat - 1e-9)
        after, _ = _places(flock, BAND_ZONES[where], beat + 1e-9)
        steps.append(np.linalg.norm(after - before, axis=1).max())
    assert max(steps) < 1e-5  # float32 rounding is within 1e-6; the old scatter popped 1e-3


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


def _on_the_end_of_its_lamp(monkeypatch: pytest.MonkeyPatch, end: str) -> None:
    """Gather the flock on the lowest or the highest LED of each lamp it comes to (a lamp's
    LEDs are listed from the bottom up)."""

    def led(self: Ground, stop: Any, u: Any) -> Any:
        stops = np.asarray(stop, dtype=np.intp)
        which = self.lamps.starts[stops] if end == "lowest" else self.lamps.starts[stops + 1] - 1
        return self.leds.pos[self.lamps.members[which]].astype(np.float64)

    monkeypatch.setattr(Ground, "on", led)


ENDS: dict[str, tuple[LedSet, str]] = {
    "the lowest LED of a lamp with no map": (lights_at(upright(1.0, 1.0), ceiling=None), "lowest"),
    "the lowest LED of a lamp under the floor": (STRAYS["under the floor"], "lowest"),
    "the highest LED of a lamp up to the ceiling": (
        lights_at(upright(1.0, 1.0, 1.6, 3.0), ceiling=3.0),
        "highest",
    ),
    "the highest LED of a lamp over the ceiling": (STRAYS["over the ceiling"], "highest"),
}


def _heights_over(flock: Flock, leds: LedSet) -> np.ndarray:
    """The heights of every bird, over a bar of the move, a quarter beat apart."""
    return np.concatenate(
        [_places(flock, leds, float(beats))[0][:, 2] for beats in np.arange(2000.0, 2008.0, 0.25)]
    )


@pytest.mark.parametrize("where", ENDS)
def test_a_flock_gathered_with_no_room_on_a_side_has_no_sheet_of_birds_along_that_edge(
    monkeypatch: pytest.MonkeyPatch, where: str
) -> None:
    """Nothing under the lowest LED of a band, or over its highest: the flock stands on that
    edge or hangs from it, whole, and none of it is level with it (half of it was)."""
    leds, end = ENDS[where]
    _on_the_end_of_its_lamp(monkeypatch, end)
    ground = Ground.of(leds)
    low, high = float(ground.floor_for(0)), float(ground.ceiling_for(0))
    z = _heights_over(_flock(count=200), leds)
    assert z.min() >= low - 1e-9 and z.max() <= high + 1e-9  # in the band
    edge = low if end == "lowest" else high
    assert np.mean(np.abs(z - edge) < 0.01) < 0.01  # no sheet at the edge's height
    assert np.abs(z - edge).min() < 0.1  # and it comes down to the floor, up to the ceiling


def test_a_lone_bulb_with_no_map_fills_its_half_metre_band_with_no_sheet_at_its_own_height() -> (
    None
):
    """With no map the band over a lone bulb is the half metre from it up, less high than the
    flock (half of which was held at the bulb's height, in every frame)."""
    leds = lights_at([(1.0, 1.0, 1.0)], ceiling=None)
    z = _heights_over(_flock(count=200), leds)
    assert z.min() >= 1.0 - 1e-6 and z.max() <= 1.5 + 1e-6
    assert np.mean(np.abs(z - 1.0) < 0.01) < 0.01 and np.mean(np.abs(z - 1.5) < 0.01) < 0.01
    assert z.min() < 1.05 and z.max() > 1.45  # birds all through the band


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
    ("z_a", "z_b", "shift"),
    [
        (1.0, -0.6, 1.0),  # a lamp in the band, one under the floor: 0.5 m under the middle
        (2.0, 3.6, -1.0),  # a lamp in the band, one over the ceiling: 0.5 m over the middle
    ],
)
def test_half_way_between_two_lamps_the_flock_gives_way_to_the_band_half_way_between_theirs(
    z_a: float, z_b: float, shift: float
) -> None:
    """The band of the lamp it leaves is blended into that of the lamp it comes to by the
    share of the move done, as the flock's middle is: half-way, the band is half-way between
    the two lamps' bands (a 3 m ceiling, and the floor, widened to each lamp's own LEDs). This
    flock's farthest bird goes 1.5 m, and there is 0.5 m of room on the one side: it moves
    in from it by the 1 m it is short."""
    zone = lights_at([(1.0, 1.0, z_a)], [(3.0, 1.0, z_b)], ceiling=3.0)
    flock = _flock(count=200, spread_m=3.0, scatter=1.0)
    beats = 2000.0 + MOVE_BEATS / 2.0
    pos, _ = _places(flock, zone, beats)
    free = _free(flock, zone, beats)
    np.testing.assert_allclose(pos[:, :2], free[:, :2], atol=1e-5)
    np.testing.assert_allclose(pos[:, 2] - free[:, 2], shift, atol=1e-5)


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
    the band of the lamp it leaves to that of the lamp it comes to, so how far it is moved in
    from the floor differs between the two (half-way can't tell the way (above); a quarter of
    the way can). Its farthest bird goes 1.5 m."""
    zone = lights_at([(1.0, 1.0, 1.0)], [(3.0, 1.0, -0.6)], ceiling=3.0)
    flock = _flock(count=200, spread_m=3.0, scatter=1.0)
    start, _ = _places(flock, zone, MOVE_BEATS * trip)  # gathered on the lamp it leaves
    assert (start[:, 0].mean() < 2.0) == leaves_the_one_in_the_band
    share = ease_in_out(0.25)  # a quarter of the move done, eased: 5/32
    # The floor goes from 0 to -0.6 as the flock's middle goes from z = 1 to -0.6, or back.
    room_under = 1.0 - share if leaves_the_one_in_the_band else share
    beats = MOVE_BEATS * trip + MOVE_BEATS / 4.0
    pos, _ = _places(flock, zone, beats)
    free = _free(flock, zone, beats)
    np.testing.assert_allclose(pos[:, :2], free[:, :2], atol=1e-5)
    np.testing.assert_allclose(pos[:, 2] - free[:, 2], 1.5 - room_under, atol=1e-5)


@pytest.mark.parametrize(
    ("low", "high"),
    [(0.0, 0.1), (2.9, 3.0), (1.0, 1.0), (1.2, 1.0)],
    ids=["over the band", "under the band", "no height", "less than none"],
)
def test_a_band_not_around_the_lamp_holds_every_bird_and_one_of_no_height_puts_them_at_one(
    monkeypatch: pytest.MonkeyPatch, low: float, high: float
) -> None:
    """The backstop for a band that is not around the lamp, which Ground never gives: the
    flock is moved into the band all the same, and a band of no height (or less) puts every
    bird at one height, with no bird flung out of it by a negative room."""

    def floor_for(self: Ground, stop: Any) -> Any:
        return np.full(np.shape(stop), low)

    def ceiling_for(self: Ground, stop: Any) -> Any:
        return np.full(np.shape(stop), high)

    monkeypatch.setattr(Ground, "floor_for", floor_for)
    monkeypatch.setattr(Ground, "ceiling_for", ceiling_for)
    flock = _flock(count=80, spread_m=0.8, scatter=3.0)
    for beats in (2000.0, 2000.75, 2002.5, 2006.0):
        pos, _ = _places(flock, _bulb(1.5), beats)  # the bulb is in none of these bands
        assert np.isfinite(pos).all()
        assert pos[:, 2].min() >= min(low, high) - 1e-9
        assert pos[:, 2].max() <= max(low, high) + 1e-9
        if high <= low:
            assert np.ptp(pos[:, 2]) < 1e-9


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
    call_counts.spy(flock_module, "in_ball")
    call_counts.spy(Ground, "on")

    for count in (5, 200):  # however many birds
        call_counts.calls.clear()
        drawn(_flock(count=count), tempo_ctx(2003.3), ROOM)
        assert call_counts.calls == {"tour": 1, "draws": 2, "in_ball": 1, "on": 1}
