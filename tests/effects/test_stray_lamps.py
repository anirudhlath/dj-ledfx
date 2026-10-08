"""The run the stray-lamp tests of the particle effects judge motion by (tests/stray_lamps.py):
a look is moving if its heights change from one frame to the next, not if they are spread
over some range, which a look frozen in place with its particles at different heights is too."""

from __future__ import annotations

import math

import numpy as np
import pytest
from conftest import tempo_ctx
from stray_lamps import (
    MOVES_IN,
    STRAYS,
    moves,
    on_the_beat,
    run_frames,
    run_heights,
    stays_in_band,
    unpassed,
)

from dj_ledfx.effects import vortex as vortex_module
from dj_ledfx.effects.particle_tools import F64
from dj_ledfx.effects.particles import ParamParticles, ParticleEffect
from dj_ledfx.effects.registry import get_effect_class, get_effect_classes
from dj_ledfx.effects.vortex import Vortex

PARTICLE_KINDS = sorted(
    name for name, cls in get_effect_classes().items() if issubclass(cls, ParticleEffect)
)


def _run_of(pairs: int, changed: int) -> list[F64]:
    """`pairs` + 1 frames whose heights differ from the frame before's in the first `changed`
    pairs of frames and stand still in the rest."""
    return [np.full(5, float(min(frame, changed))) for frame in range(pairs + 1)]


def test_frames_whose_heights_change_from_one_to_the_next_move() -> None:
    assert moves([np.linspace(0.0, 3.0, 50) + 0.01 * frame for frame in range(40)])


def test_frames_that_never_change_do_not_move_however_far_apart_their_heights_are() -> None:
    frozen = [np.linspace(0.0, 3.0, 50)] * 40
    assert np.ptp(np.concatenate(frozen)) > 2.9  # the heights are spread over the whole band
    assert not moves(frozen)


def test_a_run_moves_when_the_heights_change_in_at_least_moves_in_of_its_frames() -> None:
    pairs = 20
    needed = math.ceil(MOVES_IN * pairs)
    assert moves(_run_of(pairs, needed))
    assert not moves(_run_of(pairs, needed - 1))


def test_a_frame_with_more_or_fewer_particles_than_the_last_has_changed() -> None:
    assert moves([np.zeros(n) for n in (3, 4, 5, 6, 7, 8)])  # one born in each frame


def test_a_run_of_no_frames_or_one_frame_does_not_move() -> None:
    assert not moves([])
    assert not moves([np.zeros(5)])


def _vortex(**settings: object) -> Vortex:
    vortex = Vortex(**settings)
    vortex.reseed(1)
    return vortex


@pytest.mark.parametrize("where", STRAYS)
def test_a_vortex_frozen_in_place_has_every_height_the_pooled_checks_ask_but_does_not_move(
    where: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(vortex_module, "kicked", lambda beats, kick: 0.0)  # the beat count: 0
    leds = STRAYS[where]
    frames = run_frames(_vortex(count=120), leds, moment=on_the_beat)
    z = np.concatenate(frames)
    assert np.ptp(z) > 0.1 and unpassed(z, leds) == [] and stays_in_band(z, leds)
    assert not moves(frames)


@pytest.mark.parametrize("where", STRAYS)
def test_a_vortex_that_turns_and_rises_moves(where: str) -> None:
    assert moves(run_frames(_vortex(), STRAYS[where], moment=on_the_beat))


@pytest.mark.parametrize("kind", PARTICLE_KINDS)
def test_an_effect_that_is_always_shown_the_same_moment_does_not_move(kind: str) -> None:
    effect = get_effect_class(kind)()
    assert isinstance(effect, ParamParticles)
    effect.reseed(1)
    standing = run_frames(
        effect, STRAYS["straddling the floor"], seconds=5.0, moment=lambda t: tempo_ctx(2000.0)
    )
    assert not moves(standing)


def test_the_heights_of_a_run_are_its_frames_heights_one_after_the_other() -> None:
    leds = STRAYS["straddling the floor"]
    frames = run_frames(_vortex(count=30), leds, seconds=2.0, moment=on_the_beat)
    assert all(frame.shape == (30,) and frame.dtype == np.float64 for frame in frames)
    pooled = run_heights(_vortex(count=30), leds, seconds=2.0, moment=on_the_beat)
    np.testing.assert_array_equal(pooled, np.concatenate(frames))
