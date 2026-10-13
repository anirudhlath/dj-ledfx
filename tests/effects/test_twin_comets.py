from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import numpy as np
import pytest
from conftest import CallCounts, tempo_ctx
from map_home import HOMES, lights_at, upright
from stray_lamps import STRAYS, moves, on_the_beat, run_frames, stays_in_band, unpassed

from dj_ledfx.effects import twin_comets as comets_module
from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.effects.particle_tools import Ground, Particles
from dj_ledfx.effects.particles import MAX_PARTICLES, drawn
from dj_ledfx.effects.twin_comets import TwinComets

# Four upright lamps at the corners of a 4 x 4 m room: round its middle, (2, 2), they go
# south-west, south-east, north-east, north-west.
ROOM = lights_at(upright(0.5, 0.5), upright(3.5, 0.5), upright(3.5, 3.5), upright(0.5, 3.5))


def _comets(**settings: object) -> TwinComets:
    comets = TwinComets(**settings)
    comets.reseed(1)
    return comets


def _off_the_leds(pos: np.ndarray) -> np.ndarray:
    return np.linalg.norm(pos[:, None, :] - ROOM.pos[None, :, :], axis=2).min(axis=1)


@pytest.mark.parametrize("bpm", [30.0, 120.0, 300.0])
def test_each_comet_lands_on_an_led_on_every_beat_at_any_tempo(bpm: float) -> None:
    comets = _comets(tail=0)
    for beat in range(2000, 2008):
        drawn(comets, tempo_ctx(float(beat), bpm=bpm), ROOM)
        assert (_off_the_leds(comets.particles.pos) < 1e-4).all()
        drawn(comets, tempo_ctx(beat + 0.5, bpm=bpm), ROOM)
        assert (_off_the_leds(comets.particles.pos) > 0.5).all()  # in the air between


def test_the_comets_go_round_the_loop_a_lamp_a_beat_on_opposite_sides() -> None:
    comets = _comets(tail=0)
    turns = []
    for beat in range(2000, 2009):
        drawn(comets, tempo_ctx(float(beat)), ROOM)
        first, second = comets.particles.pos[:, :2].astype(np.float64)
        assert np.linalg.norm(first - second) > 4.0  # at opposite corners
        turns.append(math.atan2(first[1] - 2.0, first[0] - 2.0))
    steps = np.mod(np.diff(turns), 2.0 * math.pi)
    np.testing.assert_allclose(steps, math.pi / 2.0, atol=1e-5)  # the next lamp round


def test_a_tail_trails_where_its_comet_was_fading_and_shrinking() -> None:
    comets = _comets(tail=4, tail_beats=0.5, palette=["#ffffff"])
    drawn(comets, tempo_ctx(2003.3), ROOM)
    tail = comets.particles  # both tails, oldest first: the tails' ends (one of each comet) …
    for place, back in enumerate((4, 3, 2, 1, 0)):  # … to the two heads
        head = _comets(tail=0)
        drawn(head, tempo_ctx(2003.3 - 0.5 * back / 5), ROOM)
        np.testing.assert_allclose(
            tail.pos[2 * place : 2 * place + 2], head.particles.pos, atol=1e-5
        )
    first = tail.pick(np.arange(0, 10, 2))  # the first comet's five, its tail's end first
    assert (np.diff(first.colour[:, 0]) > 0.0).all() and (np.diff(first.radius) > 0.0).all()


# Two bulbs 40 m apart, a metre up, under the 3 m ceiling: a hop between them would rise 10 m.
FAR = lights_at([(0.0, 0.0, 1.0)], [(40.0, 0.0, 1.0)])
ZONES: dict[str, Callable[[], LedSet]] = {**HOMES, "four lamps": lambda: ROOM}


def _at(comets: TwinComets, room: LedSet, beats: list[float], comet: int = 0) -> np.ndarray:
    """Where a comet is at these beats."""
    return comets.at(np.array(beats), comet, Ground.of(room))


def _hop(
    comets: TwinComets, room: LedSet, beat: int, comet: int = 0, steps: int = 401
) -> np.ndarray:
    """Where a comet is along the hop that leaves on this beat: `steps` places, from the lamp
    it leaves to the one it lands on."""
    return _at(comets, room, list(beat + np.linspace(0.0, 1.0, steps)), comet)


def _same(a: Particles, b: Particles) -> None:
    for got, want in ((a.pos, b.pos), (a.colour, b.colour), (a.radius, b.radius)):
        np.testing.assert_array_equal(got, want)


def test_both_tails_are_listed_together_oldest_first_the_heads_last() -> None:
    """Oldest first, so that a cut to the newest would keep the heads: the older, the dimmer
    and smaller, so the glow and the size never fall along the list, and the two comets'
    particles for an age come together, the first comet's first."""
    comets = _comets(tail=6, palette=["#ffffff"])
    drawn(comets, tempo_ctx(2003.3), ROOM)
    particles = comets.particles
    assert particles.count == 2 * 7
    assert (np.diff(particles.colour[:, 0]) >= 0.0).all()
    assert (np.diff(particles.radius) >= 0.0).all()
    heads = _comets(tail=0)
    drawn(heads, tempo_ctx(2003.3), ROOM)
    np.testing.assert_allclose(particles.pos[-2:], heads.particles.pos, atol=1e-5)  # the last two


@pytest.mark.parametrize("bpm", [30.0, 120.0, 300.0])
def test_a_tail_reaches_back_tail_beats_beats_at_any_tempo(bpm: float) -> None:
    comets = _comets(tail=4, tail_beats=1.5)
    drawn(comets, tempo_ctx(2003.3, bpm=bpm), ROOM)
    for place, back in enumerate((4, 3, 2, 1, 0)):
        then = _comets(tail=0)
        drawn(then, tempo_ctx(2003.3 - 1.5 * back / 5, bpm=bpm), ROOM)
        np.testing.assert_allclose(
            comets.particles.pos[2 * place : 2 * place + 2], then.particles.pos, atol=1e-5
        )


def test_a_tail_fades_and_shrinks_by_how_far_back_it_reaches() -> None:
    comets = _comets(tail=4, palette=["#ffffff"], size=0.4)
    drawn(comets, tempo_ctx(2003.3), ROOM)
    back = np.arange(4, -1, -1) / 5.0
    for comet in range(2):  # the same for both comets
        tail = comets.particles.pick(np.arange(comet, 10, 2))
        np.testing.assert_allclose(tail.colour[:, 0], (1.0 - back) ** 2, atol=1e-6)
        np.testing.assert_allclose(tail.radius, 0.4 * (1.0 - 0.6 * back), atol=1e-6)


def test_each_comet_has_a_colour_of_its_own_from_the_palette() -> None:
    comets = _comets(tail=0, palette=["#ff0000", "#00ff00", "#0000ff"])
    drawn(comets, tempo_ctx(2003.3), ROOM)
    np.testing.assert_allclose(comets.particles.colour, [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
    one = _comets(tail=0, palette=["#0000ff"])
    drawn(one, tempo_ctx(2003.3), ROOM)
    np.testing.assert_allclose(one.particles.colour, [[0.0, 0.0, 1.0]] * 2)


@pytest.mark.parametrize("bpm", [30.0, 300.0])
def test_the_comets_and_their_tails_follow_the_beat_count_not_the_tempo(bpm: float) -> None:
    steady, other = _comets(), _comets()
    for beats in (2000.0, 2001.3, 2006.9):
        drawn(steady, tempo_ctx(beats), ROOM)
        drawn(other, tempo_ctx(beats, bpm=bpm), ROOM)
        _same(steady.particles, other.particles)


def test_at_gives_every_comet_at_every_beat_in_one_call() -> None:
    comets, ground = _comets(), Ground.of(ROOM)
    beats = np.array([2000.0, 2000.5, 2001.25])
    together = comets.at(beats[None, :], np.arange(2)[:, None], ground)  # comets by beats
    assert together.shape == (2, 3, 3)
    for comet in range(2):
        np.testing.assert_array_equal(together[comet], comets.at(beats, comet, ground))


@pytest.mark.parametrize("lamps", [2, 3, 4, 5, 7])
def test_the_comets_start_half_the_loop_apart(lamps: int) -> None:
    """Round a circle of lamps, in their order round its middle: the second comet is
    `lamps // 2` lamps on from the first (with 3, one on; with 2, opposite)."""
    angles = 2.0 * math.pi * np.arange(lamps) / lamps
    circle = lights_at(
        *[upright(2.0 + 1.5 * math.cos(a), 2.0 + 1.5 * math.sin(a)) for a in angles]
    )
    comets = _comets(tail=0)
    for beat in range(2000, 2010):
        drawn(comets, tempo_ctx(float(beat)), circle)
        first, second = (
            int(np.linalg.norm(circle.pos[::14, :2] - where[:2], axis=1).argmin())
            for where in comets.particles.pos
        )
        assert (second - first) % lamps == lamps // 2


def test_a_comet_lands_on_a_different_led_of_its_lamp_each_visit() -> None:
    comets = _comets(tail=0)
    landed: dict[int, set[int]] = {}
    for beat in range(2000, 2080):  # 20 visits to each lamp
        drawn(comets, tempo_ctx(float(beat)), ROOM)
        led = int(np.linalg.norm(ROOM.pos - comets.particles.pos[0], axis=1).argmin())
        landed.setdefault(led // 14, set()).add(led)
    assert sorted(landed) == [0, 1, 2, 3]
    assert all(len(leds) >= 8 for leds in landed.values())  # of its 14


def test_the_two_comets_choose_their_leds_independently() -> None:
    one = lights_at(upright(2.0, 2.0))
    comets = _comets(tail=0)
    alike = 0
    for beat in range(2000, 2060):
        drawn(comets, tempo_ctx(float(beat)), one)
        alike += int(comets.particles.pos[0, 2] == comets.particles.pos[1, 2])
    assert 0 < alike < 15  # one beat in 14 by chance; every beat if they shared their draws


def test_a_hop_rises_a_quarter_of_the_way_it_goes_over_the_line_between_its_lamps() -> None:
    comets = _comets()
    for comet in range(2):
        for beat in range(2000, 2012):
            here, middle, there = _at(comets, ROOM, [beat, beat + 0.5, beat + 1.0], comet)
            np.testing.assert_allclose(middle[:2], (here[:2] + there[:2]) / 2.0, atol=1e-9)
            rise = middle[2] - (here[2] + there[2]) / 2.0
            assert rise == pytest.approx(0.25 * np.linalg.norm(there - here), abs=1e-9)


def test_a_hop_eases_out_of_a_lamp_and_into_the_next() -> None:
    """A quarter of the beat in, it is 5/32 of the way across: the smoothstep, 3s² - 2s³."""
    comets = _comets()
    for beat in range(2000, 2008):
        here, quarter, there = _at(comets, ROOM, [beat, beat + 0.25, beat + 1.0])
        np.testing.assert_allclose(quarter[:2], here[:2] + (5.0 / 32.0) * (there - here)[:2])


def test_a_long_hop_rises_to_the_ceiling_and_no_higher_not_flat_along_it() -> None:
    """40 m would rise 10 m. It rises the 2 m of room over the bulbs instead, so the hop
    is a parabola whose top is at the ceiling, and not a stretch along the ceiling."""
    comets = _comets()
    for beat in range(2000, 2008):
        for comet in range(2):
            _, middle, _ = _at(comets, FAR, [beat, beat + 0.5, beat + 1.0], comet)
            assert middle[2] == pytest.approx(3.0, abs=1e-6)
        quarter = _at(comets, FAR, [beat + 0.25])[0]
        assert quarter[2] == pytest.approx(1.0 + 8.0 * (5.0 / 32.0) * (27.0 / 32.0), abs=1e-6)
    z = np.concatenate(run_frames(_comets(tail=0), FAR, moment=on_the_beat))
    assert z.max() <= 3.0 + 1e-6
    assert np.mean(z > 3.0 - 1e-3) < 0.2  # the top of each hop alone; flattened, three in four


def test_a_hop_rises_until_its_top_touches_the_higher_ceiling_of_its_two_lamps() -> None:
    """One lamp is in the band (a 3 m ceiling over its bulb at 2.9 m). The other has an LED
    at 3.4 m, which lifts its own ceiling to that (Ground.ceiling_for), and an LED at 1 m.
    A hop between them, 40 m apart, would rise 10 m. It rises as far as it can under 3.4 m
    instead, going and coming back and on whichever LED of the second lamp it lands: the
    top of its arc touches that ceiling, and where the LED it lands on is at the ceiling it
    still arcs, over the line to it."""
    room = lights_at([(0.0, 0.0, 2.9)], [(40.0, 0.0, 1.0), (40.0, 0.0, 3.4)])
    comets = _comets()
    landed_on = set()
    for comet in range(2):
        for beat in range(2000, 2040):
            hop = _hop(comets, room, beat, comet)
            here, there = hop[0], hop[-1]
            landed_on.add(round(float(there[2] if there[0] == 40.0 else here[2]), 1))
            assert hop[:, 2].max() <= 3.4 + 1e-6
            assert hop[:, 2].max() == pytest.approx(3.4, abs=1e-4)
            assert hop[200, 2] - (here[2] + there[2]) / 2.0 > 0.1  # over the line half-way
    assert landed_on == {1.0, 3.4}


def test_a_hop_to_an_led_near_the_top_of_the_band_still_arcs_and_stays_under_the_ceiling() -> None:
    """The room over the higher end, an LED 2.95 m up, is 5 cm, but there is more over the
    line to it. The hop rises 0.67 m over that line, the most that keeps its top at the
    3 m ceiling, going and coming back; not the 5 cm, which would make it a straight line."""
    room = lights_at([(0.0, 0.0, 1.0)], [(40.0, 0.0, 2.95)], ceiling=3.0)
    comets = _comets()
    for comet in range(2):
        for beat in range(2000, 2012):
            hop = _hop(comets, room, beat, comet)
            line = (hop[0, 2] + hop[-1, 2]) / 2.0
            assert hop[200, 2] - line == pytest.approx(0.6706, abs=1e-3)
            assert hop[:, 2].max() <= 3.0 + 1e-6
            assert hop[:, 2].max() == pytest.approx(3.0, abs=1e-4)


def test_a_hop_between_leds_at_a_ceiling_float32_holds_a_little_over_stays_on_the_line() -> None:
    """2.45 is stored as 2.4500000477, so these LEDs are 5e-8 over the ceiling (which
    Ground.ceiling_for keeps at 2.45: they are no further out than float32 can tell). The room
    over them is a hair under nothing: it counts as nothing, not as a NaN."""
    room = lights_at([(0.0, 0.0, 2.45)], [(40.0, 0.0, 2.45)], ceiling=2.45)
    comets = _comets()
    for comet in range(2):
        for beat in range(2000, 2010):
            hop = _hop(comets, room, beat, comet, steps=21)
            assert np.isfinite(hop).all()
            np.testing.assert_allclose(hop[:, 2], 2.45, atol=1e-6)


def test_a_hop_starts_where_the_last_one_landed_between_lamps_with_different_bands() -> None:
    room = lights_at([(0.0, 0.0, 2.9)], [(40.0, 0.0, 1.0), (40.0, 0.0, 3.4)])
    comets = _comets()
    for comet in range(2):
        for beat in range(2000, 2040):
            before, after = _at(comets, room, [beat - 1e-9, beat + 1e-9], comet)
            assert np.linalg.norm(after - before) < 1e-4


def test_a_hop_with_no_room_under_the_ceiling_stays_on_the_line_between_its_leds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The backstop for a ceiling under the LEDs, which Ground.ceiling_for never gives: there
    is no room to rise, and the hop doesn't dip under the line between its LEDs either."""

    def under_every_led(self: Ground, stop: Any) -> Any:
        return np.full(np.shape(stop), 0.05)

    monkeypatch.setattr(Ground, "ceiling_for", under_every_led)
    comets = _comets()
    for comet in range(2):
        for beat in range(2000, 2012):
            here, quarter, there = _at(comets, ROOM, [beat, beat + 0.25, beat + 1.0], comet)
            np.testing.assert_allclose(quarter, here + (5.0 / 32.0) * (there - here), atol=1e-9)


@pytest.mark.parametrize("where", STRAYS)
def test_comets_land_along_the_whole_length_of_a_lamp_outside_the_floor_and_ceiling(
    where: str,
) -> None:
    leds = STRAYS[where]
    frames = run_frames(_comets(), leds, moment=on_the_beat)
    z = np.concatenate(frames)
    assert moves(frames)  # hopping from frame to frame, not just spread over heights
    assert unpassed(z, leds) == []  # landing along the lamp's whole length
    assert stays_in_band(z, leds)  # and the hops stay under the lamp's ceiling


@pytest.mark.parametrize("home", ZONES)
def test_the_count_is_a_head_and_a_tail_for_each_comet_whatever_the_lamps(home: str) -> None:
    ground = Ground.of(ZONES[home]())
    for tail in (0, 8, 30):
        made = _comets(tail=tail).positions(tempo_ctx(2003.3), ground)
        assert made.count == 2 * (tail + 1) <= MAX_PARTICLES


def test_both_comets_and_all_their_tails_are_worked_out_at_once(call_counts: CallCounts) -> None:
    call_counts.spy(comets_module, "draws")
    call_counts.spy(comets_module, "around")
    call_counts.spy(Ground, "on")

    for tail in (0, 30):  # however long the tails
        call_counts.calls.clear()
        drawn(_comets(tail=tail), tempo_ctx(2003.3), ROOM)
        assert call_counts.calls == {"draws": 2, "around": 1, "on": 1}
