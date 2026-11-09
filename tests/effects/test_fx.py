"""What effects draw in space (engine spec §4.1, web spec §12.4's `fx` payload): the shapes,
and the hook every effect has."""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest
from conftest import tempo_ctx
from map_home import ROW, leds_at
from runtime_fakes import DotParticles

from dj_ledfx.effects.base import Effect
from dj_ledfx.effects.fx import NO_FX, Fx, fx_joined, planes, rings
from dj_ledfx.effects.particle_tools import swarm
from dj_ledfx.effects.particles import ParticleEffect, drawn
from dj_ledfx.effects.registry import get_effect_classes

# The field effects that draw something in space (web spec §12.4: "What draws what").
FIELDS_IN_SPACE = {
    "shockwave_shell",
    "speaker_waves",
    "ripples",
    "scanner_plane",
    "lighthouse_beam",
}


def test_rings_and_planes_take_one_value_for_all_or_one_for_each() -> None:
    two = rings([[0.0, 0.0, 0.0], [1.0, 2.0, 3.0]], [1.0, 2.0], 0.5, (1.0, 0.5, 0.0))
    assert two.count == 2 and two.radius.tolist() == [1.0, 2.0] and two.width.tolist() == [0.5] * 2
    assert two.colour.tolist() == [[1.0, 0.5, 0.0]] * 2 and not two.circle.any()
    assert rings([0.0, 0.0, 0.0], 1.0, 0.1, (1.0, 1.0, 1.0), circle=True).circle.tolist() == [True]
    level = planes([0.0, 0.0, 1.0], (0.0, 0.0, 1.0), 0.2, (0.0, 1.0, 1.0))
    assert level.count == 1 and level.ray.tolist() == [[0.0, 0.0, 0.0]]  # no ray: whole
    assert all(array.dtype == np.float32 for array in (two.centre, level.normal, level.ray))


def test_fx_join_bottom_layer_first_and_recolour_every_kind() -> None:
    low = Fx(particles=swarm([[0.0, 0.0, 1.0]], (1.0, 1.0, 1.0), 0.2))
    high = Fx(
        particles=swarm([[1.0, 0.0, 1.0]], (0.5, 0.5, 0.5), 0.3),
        rings=rings([0.0, 0.0, 0.0], 1.0, 0.1, (1.0, 0.0, 0.0)),
        planes=planes([0.0, 0.0, 1.0], (0.0, 0.0, 1.0), 0.2, (0.0, 1.0, 0.0)),
    )
    both = fx_joined([low, high])
    assert both is not None and both.particles.pos[:, 0].tolist() == [0.0, 1.0]
    assert (both.rings.count, both.planes.count) == (1, 1)
    assert fx_joined([low]) is low and fx_joined([]) is None

    halved = both.recoloured(lambda colours: colours * np.float32(0.5))
    assert halved.particles.colour[:, 0].tolist() == [0.5, 0.25]
    assert halved.rings.colour.tolist() == [[0.5, 0.0, 0.0]]
    assert halved.planes.colour.tolist() == [[0.0, 0.5, 0.0]]
    assert both.particles.colour[0, 0] == 1.0  # a new Fx: the old one is as it was
    assert NO_FX.empty and not both.empty


def test_a_particle_effect_draws_its_last_steps_particles_in_space() -> None:
    effect, leds, ctx = DotParticles(x=2.0), leds_at(ROW), tempo_ctx(8.0)
    assert effect.in_space(ctx, leds) is None  # no step yet: no particles

    drawn(effect, ctx, leds)
    fx = effect.in_space(ctx, leds)

    assert fx is not None and fx.particles is effect.particles
    assert fx.particles.pos.tolist() == [[2.0, 0.0, 1.0]]
    assert (fx.rings.count, fx.planes.count) == (0, 0)


@pytest.mark.parametrize(
    "kind",
    sorted(
        name
        for name, cls in get_effect_classes().items()
        if name not in FIELDS_IN_SPACE and not issubclass(cls, ParticleEffect)
    ),
)
def test_other_field_strip_and_firmware_effects_draw_nothing_in_space(kind: str) -> None:
    effect: Effect = get_effect_classes()[kind]()
    assert effect.in_space(tempo_ctx(8.0), leds_at(ROW)) is None


def test_an_fxs_arrays_are_read_only_so_a_joined_one_can_share_them() -> None:
    fx = Fx(
        particles=swarm([[0.0, 0.0, 1.0]], (1.0, 1.0, 1.0), 0.2),
        rings=rings([0.0, 0.0, 0.0], 1.0, 0.1, (1.0, 0.0, 0.0)),
        planes=planes([0.0, 0.0, 1.0], (0.0, 0.0, 1.0), 0.2, (0.0, 1.0, 0.0)),
    )
    joined = fx_joined([fx])
    assert joined is fx  # the very arrays: none can be written
    kinds = (fx.particles, fx.rings, fx.planes)
    arrays = [getattr(kind, name) for kind in kinds for name in kind.__slots__]
    assert len(arrays) == 13 and not any(array.flags.writeable for array in arrays)
    with pytest.raises(ValueError, match="read-only"):
        fx.rings.radius[0] = 2.0
    both = fx_joined([fx, fx])
    assert both is not None and not both.planes.point.flags.writeable


@pytest.mark.parametrize(
    "make",
    [
        lambda: rings([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]], [1.0, 2.0, 3.0], 0.1, (1.0, 1.0, 1.0)),
        lambda: rings([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]], 1.0, 0.1, [(1.0, 1.0, 1.0)] * 3),
        lambda: planes([[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]], [(0.0, 0.0, 1.0)] * 3, 0.1, (1, 1, 1)),
        lambda: planes([[0.0, 0.0, 0.0]], (0.0, 0.0, 1.0), [0.1, 0.2], (1.0, 1.0, 1.0)),
        lambda: planes([[0.0, 0.0, 0.0]], (0.0, 0.0, 1.0), 0.1, (1.0, 1.0, 1.0), ray=(1.0, 0.0)),
    ],
    ids=["radius", "colour", "normal", "width", "ray"],
)
def test_rings_and_planes_refuse_values_that_dont_match_their_count(make: Any) -> None:
    with pytest.raises(ValueError, match=r"one for all or one for each of the \d items"):
        make()
