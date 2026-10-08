from __future__ import annotations

from typing import ClassVar

import numpy as np
import pytest
from conftest import render_ctx
from map_home import ROW, leds_at

from dj_ledfx.effects.base import ParamSettings
from dj_ledfx.effects.context import RenderContext
from dj_ledfx.effects.field import ParamField
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.effects.particle_tools import Ground, Particles, swarm
from dj_ledfx.effects.particles import MAX_PARTICLES, ParamParticles, ParticleEffect, drawn


class _Dots(ParamParticles, register=False):
    """`count` dots in a row along x from the zone's west end, 0.5 m apart, at `t` metres
    east: each the palette's first colour. `grounds` keeps every Ground it moved on."""

    grounds: ClassVar[list[Ground]] = []

    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "count": EffectParam(type="int", default=1, min=0, max=2000),
            "palette": EffectParam(type="color_list", default=["#ff0000"]),
        }

    def positions(self, ctx: RenderContext, ground: Ground) -> Particles:
        assert ground.leds.count > 0
        _Dots.grounds.append(ground)
        count = int(self._values["count"])
        x = ground.low[0] + ctx.t + 0.5 * np.arange(count)
        pos = np.stack([x, np.zeros(count), np.full(count, 1.0)], axis=1)
        return swarm(pos, self._palette[0], 0.25)


@pytest.fixture(autouse=True)
def _grounds() -> None:
    _Dots.grounds = []


def test_particle_and_field_effects_keep_their_settings_alike() -> None:
    assert issubclass(ParamParticles, ParamSettings) and issubclass(ParamField, ParamSettings)
    dots = _Dots(count=3)
    assert dots.get_params() == {"count": 3, "palette": ["#ff0000"]}
    np.testing.assert_allclose(dots._palette, [[1.0, 0.0, 0.0]])
    with pytest.raises(TypeError, match="no setting speed"):
        _Dots(speed=1.0)


def test_a_step_moves_the_particles_to_the_moment_and_sample_lights_the_leds() -> None:
    leds = leds_at(ROW)  # 0.5 m apart from x = 0
    dots = _Dots()
    dots.place(leds)

    dots.step(render_ctx(t=1.0))

    assert isinstance(dots, ParticleEffect)
    np.testing.assert_allclose(dots.particles.pos, [[1.0, 0.0, 1.0]])
    frame = dots.sample(render_ctx(t=1.0), leds)
    assert frame.shape == (9, 3) and frame.dtype == np.float32
    assert int(np.argmax(frame[:, 0])) == 2  # the LED at 1 m
    assert not frame[:, 1:].any()


def test_drawn_places_steps_and_samples() -> None:
    leds = leds_at(ROW)
    dots = _Dots()
    first = drawn(dots, render_ctx(t=0.5), leds)
    later = drawn(dots, render_ctx(t=2.0), leds)
    assert int(np.argmax(first[:, 0])) == 1 and int(np.argmax(later[:, 0])) == 4


def test_the_ground_is_made_once_for_each_led_set() -> None:
    leds, other = leds_at(ROW), leds_at(ROW[:4])
    dots = _Dots()
    for t in (0.0, 0.1, 0.2):
        drawn(dots, render_ctx(t=t), leds)
    assert len({id(ground) for ground in _Dots.grounds}) == 1
    drawn(dots, render_ctx(t=0.3), other)
    assert _Dots.grounds[-1].leds is other


def test_a_step_keeps_the_newest_500() -> None:
    dots = _Dots(count=MAX_PARTICLES + 300)
    dots.place(leds_at(ROW))
    dots.step(render_ctx(t=0.0))
    assert dots.particles.count == MAX_PARTICLES
    np.testing.assert_allclose(dots.particles.pos[0, 0], 0.5 * 300)  # the oldest 300 dropped


def test_no_leds_or_no_place_give_no_particles() -> None:
    dots = _Dots(count=4)
    dots.step(render_ctx(t=1.0))  # never placed
    assert dots.particles.count == 0
    empty = leds_at([])
    frame = drawn(dots, render_ctx(t=1.0), empty)
    assert frame.shape == (0, 3)
    assert dots.particles.count == 0
    assert not _Dots.grounds  # positions() never ran: every effect has an LED to go by


def test_a_settings_change_applies_at_the_next_step() -> None:
    leds = leds_at(ROW)
    dots = _Dots(count=1)
    drawn(dots, render_ctx(t=0.0), leds)
    dots.set_params(count=3, palette=["#00ff00"])
    frame = drawn(dots, render_ctx(t=0.0), leds)
    assert dots.particles.count == 3
    assert frame[:, 1].max() > 0.9 and not frame[:, 0].any()
