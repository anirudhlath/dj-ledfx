from __future__ import annotations

import math

import numpy as np
import pytest
from conftest import tempo_ctx
from map_home import lights_at, upright

from dj_ledfx.effects.particles import drawn
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
