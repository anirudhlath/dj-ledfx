from __future__ import annotations

import numpy as np
import pytest
from conftest import render_ctx
from map_home import ROW, leds_at, lights_at, upright

from dj_ledfx.effects.fireflies import DRIFT_REACH_M, GLOW_LOW, RANGE_M, Fireflies
from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.effects.particle_tools import REACH
from dj_ledfx.effects.particles import drawn

# Three upright lamps round a room under a 3 m ceiling, and a 12 m row of LEDs 0.25 m
# apart, 1 m up, with a sofa near its west end.
THREE = lights_at(upright(0.5, 0.5), upright(4.5, 0.5), upright(2.5, 4.0))
ROW_12 = [[x, 0.0, 1.0] for x in np.linspace(0.0, 12.0, 49)]
SOFA = (2.0, 0.5, 0.5)


def _flies(**settings: object) -> Fireflies:
    flies = Fireflies(**settings)
    flies.reseed(1)
    return flies


def _moments(seconds: float = 30.0) -> list[float]:
    return [500.0 + t for t in np.arange(0.0, seconds, 0.1)]


def _paths(flies: Fireflies, leds: LedSet, seconds: float = 30.0) -> np.ndarray:
    """Each firefly's places over some seconds: shape (moments, fireflies, 3)."""
    seen = []
    for t in _moments(seconds):
        drawn(flies, render_ctx(t=t), leds)
        seen.append(flies.particles.pos)
    return np.stack(seen)


def test_each_firefly_wanders_round_a_lamp_of_its_own_every_lamp_taken_alike() -> None:
    paths = _paths(_flies(count=6, speed=1.0), THREE)
    lamps = np.array([[0.5, 0.5], [4.5, 0.5], [2.5, 4.0]])
    away = np.abs(paths[:, :, None, :2] - lamps[None, None, :, :]).max(axis=3)  # (m, f, lamp)
    home = (away <= RANGE_M + 1e-5).all(axis=0)  # the lamps each keeps within RANGE_M of
    assert home.any(axis=1).all()
    assert np.bincount(home.argmax(axis=1), minlength=3).tolist() == [2, 2, 2]
    assert paths[..., 2].min() >= 0.0 and paths[..., 2].max() <= 3.0  # floor to ceiling


def test_fireflies_spread_along_a_long_light() -> None:
    paths = _paths(_flies(count=10, speed=1.0), leds_at(ROW_12), seconds=5.0)
    assert np.ptp(paths[0, :, 0]) > 6.0  # round LEDs all along it, not round its middle


def test_fireflies_that_drift_toward_an_anchor_keep_near_it() -> None:
    leds = leds_at(ROW_12, anchors={"sofa": SOFA})
    flies = _flies(count=20, speed=1.0, drift_toward="sofa")
    for t in _moments():
        drawn(flies, render_ctx(t=t), leds)
        away = np.abs(flies.particles.pos - np.array(SOFA, dtype=np.float32))
        assert (away[:, :2] <= DRIFT_REACH_M + 1e-5).all()
        assert (flies.particles.pos[:, 2] >= 0.0).all()  # never under the floor


def test_fireflies_drawn_to_an_anchor_that_is_not_there_wander_round_the_lamps() -> None:
    gone, plain = _flies(drift_toward="gone"), _flies()  # THREE has no anchors
    lit = False
    for t in _moments(10.0)[::7]:
        frame = drawn(gone, render_ctx(t=t), THREE)
        np.testing.assert_array_equal(frame, drawn(plain, render_ctx(t=t), THREE))
        np.testing.assert_array_equal(gone.particles.pos, plain.particles.pos)
        lit = lit or bool(frame.any())
    assert lit


def test_each_firefly_glows_softly_and_flares_now_and_then() -> None:
    leds = leds_at(ROW)
    flies = _flies(count=5, palette=["#ffffff"])
    glow = []
    for t in _moments(10.0):
        drawn(flies, render_ctx(t=t), leds)
        glow.append(flies.particles.colour[:, 0])
    levels = np.array(glow)  # (moments, fireflies)
    assert levels.min() >= GLOW_LOW - 1e-6
    assert (levels.max(axis=0) > 0.95).all()  # each flares at least once in 10 s


def test_a_lamp_glows_only_while_a_firefly_drifts_through_it() -> None:
    leds = leds_at(ROW_12)
    flies = _flies(count=2, glow_size=0.3)
    for t in _moments(5.0):
        frame = drawn(flies, render_ctx(t=t), leds)
        gaps = np.linalg.norm(leds.pos[:, None, :] - flies.particles.pos[None, :, :], axis=2)
        far = gaps.min(axis=1) > REACH * 0.3
        assert not frame[far].any()  # black between them
        assert far.sum() >= len(far) - 14  # two fireflies light a few LEDs at most


@pytest.mark.parametrize("speed", [0.3, 1.0])
def test_fireflies_wander_at_about_their_speed(speed: float) -> None:
    paths = _paths(_flies(count=10, speed=speed), leds_at(ROW_12), seconds=10.0)
    metres = np.linalg.norm(np.diff(paths, axis=0), axis=2).sum(axis=0)  # each one's, in 10 s
    assert 0.7 * speed * 10.0 < metres.mean() < speed * 10.0


def test_each_firefly_flares_in_its_own_time() -> None:
    flies = _flies(count=5, palette=["#ffffff"])
    glow = []
    for t in _moments(10.0):
        drawn(flies, render_ctx(t=t), leds_at(ROW))
        glow.append(flies.particles.colour[:, 0])
    assert len(set(np.array(glow).argmax(axis=0))) > 1  # not all at the same moment


def test_fireflies_move_in_seconds_whatever_the_tempo() -> None:
    leds = leds_at(ROW)
    slow = drawn(_flies(), render_ctx(t=500.0, beat_phase=0.1, bpm=60.0), leds)
    quick = drawn(_flies(), render_ctx(t=500.0, beat_phase=0.9, bpm=300.0), leds)
    assert slow.any()
    np.testing.assert_array_equal(slow, quick)
