"""Every particle effect, swept (spec §9: every look stays finite and in range, outputs the
right shape, and repeats exactly with a fixed seed), on this home's LEDs and on the
smallest zones a home can have."""

from __future__ import annotations

import statistics
import time
from dataclasses import replace
from typing import Any

import numpy as np
import pytest
from conftest import tempo_ctx
from map_home import HOMES, leds_at, lights_at, seeded_ledset, upright

from dj_ledfx.effects.context import RenderContext
from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.effects.particle_tools import Ground
from dj_ledfx.effects.particles import MAX_PARTICLES, ParamParticles, ParticleEffect, drawn
from dj_ledfx.effects.registry import get_effect_class, get_effect_classes
from dj_ledfx.types import FloatRGB
from dj_ledfx.zones.runtime import FRAME_BUDGET_S

PARTICLE_KINDS = sorted(
    name for name, cls in get_effect_classes().items() if issubclass(cls, ParticleEffect)
)
START = 2000.0  # beats: 1000 s into a steady 120 BPM


def _effect(kind: str, seed: int = 1, **settings: Any) -> ParamParticles:
    effect = get_effect_class(kind)(**settings)
    assert isinstance(effect, ParamParticles)
    effect.reseed(seed)
    return effect


def _largest(kind: str) -> dict[str, Any]:
    """Every number the effect takes at its largest."""
    return {
        name: int(param.max) if param.type == "int" else param.max
        for name, param in get_effect_class(kind).parameters().items()
        if param.type in ("int", "float") and param.max is not None
    }


def _keeps_to_the_cap(effect: ParamParticles, ctx: RenderContext, ground: Ground) -> None:
    """What the effect makes itself, before `step` cuts it to the cap (the cut hides a miss),
    and that the cut took none: a particle cut is one cut mid-life, as the effect lets each
    live its life out."""
    if ground.lamps.count:  # no lamps, no particles
        made = effect.positions(ctx, ground)
        assert made.count <= MAX_PARTICLES
        assert effect.particles.count == made.count


def _frames(effect: ParamParticles, leds: LedSet, count: int = 120) -> list[FloatRGB]:
    """`count` frames at 60 a second (two seconds by default), checking each one's particles."""
    ground, frames = Ground.of(leds), []
    for step in range(count):
        ctx = tempo_ctx(START + step / 30)
        frames.append(drawn(effect, ctx, leds))
        _keeps_to_the_cap(effect, ctx, ground)
        particles = effect.particles
        assert particles.count <= MAX_PARTICLES
        assert np.isfinite(particles.pos).all() and np.isfinite(particles.radius).all()
    return frames


def _good(frames: list[FloatRGB], leds: LedSet) -> None:
    for frame in frames:
        assert frame.shape == (leds.count, 3) and frame.dtype == np.float32
        assert np.isfinite(frame).all()
        assert frame.min() >= 0.0 and frame.max() <= 1.0


@pytest.mark.parametrize("kind", PARTICLE_KINDS)
def test_every_particle_effect_is_finite_in_range_and_repeats_with_a_fixed_seed(
    kind: str,
) -> None:
    leds = seeded_ledset()
    frames = _frames(_effect(kind), leds)
    _good(frames, leds)
    assert any(frame.any() for frame in frames)  # it lights something
    again = _frames(_effect(kind), leds)
    for frame, repeat in zip(frames, again, strict=True):
        np.testing.assert_array_equal(frame, repeat)
    other = _frames(_effect(kind, seed=2), leds)
    assert any(not np.array_equal(a, b) for a, b in zip(frames, other, strict=True))


@pytest.mark.parametrize("kind", PARTICLE_KINDS)
def test_the_same_moment_gives_the_same_frame_however_the_frames_fall(kind: str) -> None:
    leds = seeded_ledset()
    stepped, jumped = _effect(kind), _effect(kind)
    for beats in (START, START + 0.4, START + 3.7):
        drawn(stepped, tempo_ctx(beats), leds)
    moment = tempo_ctx(START + 9.25)
    np.testing.assert_array_equal(drawn(stepped, moment, leds), drawn(jumped, moment, leds))


@pytest.mark.parametrize("kind", PARTICLE_KINDS)
def test_a_tempo_from_30_to_300_bpm_keeps_every_frame_in_range(kind: str) -> None:
    leds = seeded_ledset()
    ground = Ground.of(leds)
    effect, t, beats, frames = _effect(kind), 1000.0, START, []
    for bpm in (30.0, 300.0, 120.0):  # each for two seconds, the clock running on
        for _ in range(60):
            t, beats = t + 1 / 30, beats + bpm / 60.0 / 30
            ctx = replace(tempo_ctx(beats, bpm=bpm), t=t)
            frames.append(drawn(effect, ctx, leds))
            _keeps_to_the_cap(effect, ctx, ground)
            assert effect.particles.count <= MAX_PARTICLES
    _good(frames, leds)


@pytest.mark.parametrize("kind", PARTICLE_KINDS)
def test_a_zone_of_one_lamp_with_no_map_draws_in_range(kind: str) -> None:
    leds = leds_at([[1.0, 1.0, 0.1 + 0.1 * i] for i in range(14)], ceiling=None)
    _good(_frames(_effect(kind), leds, count=60), leds)


@pytest.mark.parametrize("ceiling", [None, 3.0], ids=["no map", "a 3 m ceiling"])
@pytest.mark.parametrize("kind", PARTICLE_KINDS)
def test_a_zone_of_one_bulb_draws_in_range_and_lights_it(kind: str, ceiling: float | None) -> None:
    leds = leds_at([[1.0, 1.0, 1.0]], ceiling=ceiling)  # one LED: its lamp's top and foot
    frames = _frames(_effect(kind), leds, count=600)
    _good(frames, leds)
    assert max(float(frame.max()) for frame in frames) > 0.1  # it lights at some moment


@pytest.mark.parametrize("kind", PARTICLE_KINDS)
def test_a_zone_with_no_leds_draws_nothing(kind: str) -> None:
    effect = _effect(kind)
    frame = drawn(effect, tempo_ctx(START), leds_at([]))
    assert frame.shape == (0, 3) and effect.particles.count == 0
    assert effect.in_space(tempo_ctx(START), leds_at([])) is None  # nothing in space either


# M8: each particle look's particles reach the stage as they are, with no code of its own.
@pytest.mark.parametrize("kind", PARTICLE_KINDS)
def test_every_particle_effect_draws_its_particles_in_space(kind: str) -> None:
    effect, leds, ctx = _effect(kind), seeded_ledset(), tempo_ctx(START)
    drawn(effect, ctx, leds)
    fx = effect.in_space(ctx, leds)
    assert fx is not None and fx.particles is effect.particles and fx.particles.count > 0


# Ceilings float32 stores a little over (2.45 as 2.4500000477): a lamp with its top LED exactly
# there is inside the band, so it is drawn as the zone's own floor and ceiling draw it.
@pytest.mark.parametrize("ceiling", [2.45, 2.7])
@pytest.mark.parametrize("kind", PARTICLE_KINDS)
def test_lamps_inside_the_band_are_drawn_with_the_zones_own_floor_and_ceiling(
    monkeypatch: pytest.MonkeyPatch, kind: str, ceiling: float
) -> None:
    leds = lights_at(
        upright(1.0, 1.0, 0.7, ceiling),
        upright(2.0, 1.0, 0.1, ceiling),
        upright(3.0, 1.0, 0.3, 1.4),
        ceiling=ceiling,
    )

    def run() -> list[tuple[Any, ...]]:
        effect = _effect(kind, **_largest(kind))
        seen = []
        for step in range(40):
            drawn(effect, tempo_ctx(START + step * 0.7), leds)
            assert np.isfinite(effect.particles.pos).all()  # a hair over a ceiling is no NaN
            seen.append((effect.particles.pos, effect.particles.colour, effect.particles.radius))
        return seen

    def zones_floor(self: Ground, stop: Any) -> Any:
        return np.full(np.shape(stop), self.floor)

    def zones_ceiling(self: Ground, stop: Any) -> Any:
        return np.full(np.shape(stop), self.ceiling)

    lamp_by_lamp = run()
    monkeypatch.setattr(Ground, "floor_for", zones_floor)
    monkeypatch.setattr(Ground, "ceiling_for", zones_ceiling)
    for ours, zones in zip(lamp_by_lamp, run(), strict=True):
        for a, b in zip(ours, zones, strict=True):
            np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize("home", HOMES)
@pytest.mark.parametrize("kind", PARTICLE_KINDS)
def test_the_largest_settings_keep_to_the_particle_cap(kind: str, home: str) -> None:
    leds = HOMES[home]()
    _good(_frames(_effect(kind, **_largest(kind)), leds, count=30), leds)


@pytest.mark.parametrize("home", HOMES)
@pytest.mark.parametrize("kind", PARTICLE_KINDS)
def test_the_largest_settings_cut_no_particle_mid_life_however_long_they_run(
    kind: str, home: str
) -> None:
    """An ember lives 19 s at the longest; this runs 105 s, in steps no life divides."""
    leds = HOMES[home]()
    ground = Ground.of(leds)
    for seed in (1, 2):
        effect = _effect(kind, seed=seed, **_largest(kind))
        effect.place(leds)
        for step in range(150):
            ctx = tempo_ctx(START + step * 1.4)
            effect.step(ctx)
            _keeps_to_the_cap(effect, ctx, ground)


# Spec §9's benchmark: every particle effect at its largest settings, on this home's LEDs.
@pytest.mark.perf
@pytest.mark.parametrize("kind", PARTICLE_KINDS)
def test_every_particle_effect_at_its_largest_settings_draws_in_the_budget(kind: str) -> None:
    leds = seeded_ledset()
    effect = _effect(kind, **_largest(kind))
    durations = []
    for step in range(240):
        started = time.perf_counter()
        drawn(effect, tempo_ctx(START + step / 30), leds)
        durations.append(time.perf_counter() - started)
    assert statistics.median(durations) < FRAME_BUDGET_S
