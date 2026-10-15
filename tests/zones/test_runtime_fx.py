"""What a running zone draws in space (M8, engine spec §4.1): each frame's fx, kept in the
ring beside its colours, on the map."""

from __future__ import annotations

import numpy as np
import pytest
from conftest import nearest_frame
from loguru import logger
from runtime_fakes import (
    FADE,
    DotParticles,
    dot_layer,
    field_layer,
    glow_layer,
    latest,
    look_of,
    placed_light,
    runtime_of,
)
from tempo_fakes import START, FakeTime, tempo_clock

from dj_ledfx.effects.context import RenderContext
from dj_ledfx.effects.fx import Fx
from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.looks.model import Layer, LookModifiers, Mirror, Transform
from dj_ledfx.zones.runtime import ZoneRuntime

pytestmark = pytest.mark.usefixtures("_fields")

# One light of 9 LEDs, 0.5 m apart along x from 0 to 4 m, 1 m up: its centre is at 2 m.
ROW_LIGHT = placed_light("row", *[(0.5 * i, 0.0, 1.0) for i in range(9)])
UNDER_THE_DOT = 4  # the LED at 2 m


def _fx(runtime: ZoneRuntime) -> Fx | None:
    """What the newest frame draws in space."""
    return nearest_frame(runtime.ring, 1e9).fx


def _dots(runtime: ZoneRuntime) -> list[list[float]]:
    fx = _fx(runtime)
    assert fx is not None
    return fx.particles.pos.tolist()


def test_each_frame_keeps_what_its_layers_draw_in_space_beside_its_colours() -> None:
    runtime = runtime_of(look_of(field_layer(0.2), dot_layer(x=2.0, blend="add")), [ROW_LIGHT])
    runtime.tick(100.0)

    frame = nearest_frame(runtime.ring, 1e9)
    assert frame.fx is not None and frame.colors[UNDER_THE_DOT, 0] > 0.2  # the dot's light
    assert frame.fx.particles.pos.tolist() == [[2.0, 0.0, 1.0]]  # the field draws nothing
    assert frame.fx.particles.colour.tolist() == [[1.0, 1.0, 1.0]]
    assert (frame.fx.rings.count, frame.fx.planes.count) == (0, 0)


def test_a_layers_transform_and_mirror_move_its_fx_onto_the_map() -> None:
    shifted = runtime_of(
        look_of(dot_layer(x=2.0, transform=Transform(offset=(1.0, 0.0, 0.0)))), [ROW_LIGHT]
    )
    mirrored = runtime_of(look_of(dot_layer(x=1.0, mirror=Mirror(axis="x"))), [ROW_LIGHT])
    shifted.tick(100.0)
    mirrored.tick(100.0)
    assert _dots(shifted) == [[3.0, 0.0, 1.0]]  # where the lights show it: 1 m further east
    assert _dots(mirrored) == [[1.0, 0.0, 1.0], [3.0, 0.0, 1.0]]  # and across the middle


def test_a_layers_opacity_dims_its_fx_whatever_its_blend() -> None:
    for blend in ("normal", "add", "screen", "max"):
        runtime = runtime_of(look_of(dot_layer(x=2.0, opacity=0.5, blend=blend)), [ROW_LIGHT])
        runtime.tick(100.0)
        fx = _fx(runtime)
        assert fx is not None and fx.particles.colour.tolist() == [[0.5, 0.5, 0.5]]


def test_the_evening_and_the_cap_change_the_fx_as_they_change_the_leds() -> None:
    modifiers = LookModifiers(evening=True, brightness_cap=0.4)
    runtime = runtime_of(
        look_of(dot_layer(x=2.0), modifiers=modifiers), [ROW_LIGHT], evening=lambda: 1.0
    )
    runtime.tick(100.0)
    fx = _fx(runtime)
    assert fx is not None
    # The LED under the dot shows the dot's own colour, so the two match.
    np.testing.assert_allclose(fx.particles.colour[0], latest(runtime)[UNDER_THE_DOT], rtol=1e-6)
    assert float(fx.particles.colour.max()) == pytest.approx(0.4)


def test_a_flash_and_trails_light_the_leds_alone() -> None:
    clock = tempo_clock(FakeTime())  # beat 0 at START, 120 BPM: a bar every 2 s
    modifiers = LookModifiers(trails_s=10.0, downbeat_flash=True)
    runtime = runtime_of(
        look_of(dot_layer(x=2.0, level=0.5), modifiers=modifiers), [ROW_LIGHT], clock=clock
    )

    runtime.tick(START + 2.0)  # just past the downbeat: the flash
    assert latest(runtime)[UNDER_THE_DOT, 0] > 0.75
    fx = _fx(runtime)
    assert fx is not None and fx.particles.colour.tolist() == [[0.5, 0.5, 0.5]]
    runtime.tick(START + 2.3)  # the flash is over, its trail isn't
    assert latest(runtime)[UNDER_THE_DOT, 0] > 0.5
    fx = _fx(runtime)
    assert fx is not None and fx.particles.colour.tolist() == [[0.5, 0.5, 0.5]]


@pytest.mark.parametrize(
    "layers",
    [(field_layer(0.5),), (field_layer(0.5), glow_layer())],
    ids=["field", "firmware"],
)
def test_layers_that_draw_nothing_in_space_give_a_frame_no_fx(layers: tuple[Layer, ...]) -> None:
    runtime = runtime_of(look_of(*layers))
    runtime.tick(100.0)
    assert latest(runtime).any() and _fx(runtime) is None


def test_a_waiting_look_and_a_dark_dot_draw_nothing_in_space() -> None:
    waiting = runtime_of(look_of(dot_layer(x=2.0), needs=("music",)), [ROW_LIGHT])
    dark = runtime_of(look_of(dot_layer(x=2.0, level=0.0)), [ROW_LIGHT])
    waiting.tick(100.0)
    dark.tick(100.0)
    assert waiting.state == "waiting" and _fx(waiting) is None
    fx = _fx(dark)  # a black particle is still a particle: the channel leaves it out
    assert fx is not None and fx.particles.count == 1


def test_mid_transition_a_zone_draws_the_new_looks_fx_from_its_first_frame() -> None:
    old = runtime_of(look_of(dot_layer(x=1.0)), [ROW_LIGHT])
    new = runtime_of(look_of(dot_layer(x=3.0)), [ROW_LIGHT])
    new.begin_transition(FADE, [old])

    new.tick(1000.0)
    assert new.state == "transition"
    assert latest(new)[2, 0] > 0.0  # the old look's dot still lights its LED...
    assert _dots(new) == [[3.0, 0.0, 1.0]]  # ...but only the new look's is drawn in space
    new.tick(1001.0)
    assert _dots(new) == [[3.0, 0.0, 1.0]]


def test_an_effect_that_cant_say_what_it_draws_loses_its_fx_not_its_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(self: DotParticles, ctx: RenderContext, leds: LedSet) -> Fx | None:
        raise RuntimeError("no fx")

    monkeypatch.setattr(DotParticles, "in_space", broken)
    runtime = runtime_of(look_of(dot_layer(x=2.0)), [ROW_LIGHT])
    warnings: list[str] = []
    sink = logger.add(lambda message: warnings.append(str(message)), level="WARNING")
    try:
        runtime.tick(100.0)
        runtime.tick(100.1)
    finally:
        logger.remove(sink)

    assert runtime.state == "running"
    assert latest(runtime)[UNDER_THE_DOT, 0] == pytest.approx(1.0)
    assert _fx(runtime) is None
    assert len(warnings) == 1 and "RuntimeError: no fx" in warnings[0]
