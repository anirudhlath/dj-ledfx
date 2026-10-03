"""A zone runtime plays its layers' and its look's modifiers (spec §5.3)."""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import replace
from types import MappingProxyType
from typing import Any

import numpy as np
import pytest
from map_home import tiny_home
from runtime_fakes import (
    FlatField,
    PlaceField,
    field_layer,
    glow_layer,
    latest,
    look_of,
    place_layer,
    placed_light,
    register_fields,
    runtime_of,
)
from tempo_fakes import START, FakeTime, tempo_clock

from dj_ledfx.effects.base import Effect
from dj_ledfx.effects.context import EVENING, RenderContext
from dj_ledfx.effects.field import FieldEffect
from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.home.map import space_of
from dj_ledfx.looks.model import Layer, LookModifiers, Mirror, RoomMask, SubZoneMask, Transform
from dj_ledfx.types import FloatRGB
from dj_ledfx.zones.look_modifiers import EVENING_FULLEST, TRAILS_FALL

SPACE = space_of(tiny_home())  # west and east rooms, the desk in the west's north-west
WEST = placed_light("west-lamp", (1.0, 1.0, 1.0), (2.0, 1.0, 1.0), room=0)
EAST = placed_light("east-lamp", (6.0, 1.0, 1.0), (7.0, 1.0, 1.0), room=1)


@pytest.fixture(autouse=True)
def _fields() -> Iterator[None]:
    register_fields()
    yield
    FlatField.mode = "ok"


def test_a_masked_layer_draws_only_where_its_mask_lets_it() -> None:
    look = look_of(field_layer(0.2, id="base"), field_layer(0.8, id="top", mask=RoomMask("east")))
    runtime = runtime_of(look, [WEST, EAST], space=SPACE)

    runtime.tick(100.0)

    assert np.allclose(latest(runtime)[:, 0], [0.2, 0.2, 0.8, 0.8])


def test_a_masked_bottom_layer_draws_over_black() -> None:
    runtime = runtime_of(
        look_of(field_layer(0.8, mask=RoomMask("west"))), [WEST, EAST], space=SPACE
    )

    runtime.tick(100.0)

    assert np.allclose(latest(runtime)[:, 0], [0.8, 0.8, 0.0, 0.0])


def test_mirror_and_transform_move_where_the_effect_looks() -> None:
    mirror = runtime_of(look_of(place_layer(mirror=Mirror("x", 4.0))), [WEST, EAST], space=SPACE)
    moved = runtime_of(
        look_of(place_layer(transform=Transform(offset=(1.0, 0.0, 0.0)))),
        [WEST, EAST],
        space=SPACE,
    )

    mirror.tick(100.0)
    moved.tick(100.0)

    assert np.allclose(latest(mirror)[:, 0], [1.0, 2.0, 2.0, 1.0])  # east folded onto west
    assert np.allclose(latest(moved)[:, 0], [0.0, 1.0, 5.0, 6.0])  # each LED sees 1 m west


def test_a_layers_view_is_kept_until_its_modifiers_or_the_leds_change() -> None:
    look = look_of(place_layer(mirror=Mirror("x", 4.0)))
    runtime = runtime_of(look, [WEST, EAST], space=SPACE)
    runtime.tick(100.0)
    runtime.tick(100.1)
    first, again = PlaceField.seen
    assert again is first  # the effect's per-LED work is kept between frames

    runtime.update_look(look_of(place_layer(mirror=Mirror("x", 3.0))))
    runtime.tick(100.2)
    assert PlaceField.seen[-1] is not first
    assert np.allclose(latest(runtime)[:, 0], [1.0, 2.0, 0.0, -1.0])  # folded at 3 m now


def test_a_map_change_redraws_a_masked_layer() -> None:
    runtime = runtime_of(look_of(field_layer(0.8, mask=SubZoneMask("desk"))), [WEST], space=SPACE)
    runtime.tick(100.0)
    assert np.allclose(latest(runtime)[:, 0], [0.0, 0.0])  # the desk is in the room's corner

    nook = ((0.0, 0.0), (3.0, 0.0), (3.0, 2.0), (0.0, 2.0))
    bigger = replace(SPACE, sub_zone_outlines=MappingProxyType({"desk": nook}))
    runtime.set_lights([WEST], bigger)
    runtime.tick(100.1)

    assert np.allclose(latest(runtime)[:, 0], [0.8, 0.8])


# H8 = M12: an outline edited keeps a zone's trails, and its masked layer follows the new
# outline.
def test_an_outline_edit_keeps_the_trails_and_redraws_the_mask() -> None:
    nook = ((0.0, 0.0), (3.0, 0.0), (3.0, 2.0), (0.0, 2.0))
    bigger = replace(SPACE, sub_zone_outlines=MappingProxyType({"desk": nook}))
    look = look_of(
        field_layer(0.8, mask=SubZoneMask("desk")), modifiers=LookModifiers(trails_s=1.0)
    )
    runtime = runtime_of(look, [WEST], space=bigger)
    runtime.tick(100.0)
    assert np.allclose(latest(runtime)[:, 0], 0.8)  # the desk takes in the west lamp

    runtime.set_lights([WEST], SPACE)  # the desk shrinks back to its corner
    runtime.tick(100.1)
    fading = 0.8 * math.exp(-TRAILS_FALL * 0.1)
    assert np.allclose(latest(runtime)[:, 0], fading, rtol=1e-5)  # a trail, not black
    runtime.tick(102.0)
    assert np.allclose(latest(runtime)[:, 0], 0.0)  # the mask follows the new outline


def test_trails_hold_a_light_that_drops() -> None:
    look = look_of(field_layer(1.0), modifiers=LookModifiers(trails_s=1.0))
    runtime = runtime_of(look)
    runtime.tick(1000.0)

    runtime.update_look(replace(look, layers=(field_layer(0.0),)))
    runtime.tick(1000.5)

    assert latest(runtime)[0, 0] == pytest.approx(math.exp(-TRAILS_FALL * 0.5), rel=1e-5)


def test_trails_turned_off_forget_what_they_held() -> None:
    look = look_of(field_layer(1.0), modifiers=LookModifiers(trails_s=1.0))
    runtime = runtime_of(look)
    runtime.tick(1000.0)

    runtime.update_look(replace(look, layers=(field_layer(0.0),), modifiers=LookModifiers()))
    runtime.tick(1000.1)
    runtime.update_look(replace(look, layers=(field_layer(0.0),)))
    runtime.tick(1000.2)

    assert latest(runtime)[0, 0] == 0.0


def test_the_downbeat_flash_follows_the_tempo_clock() -> None:
    clock = tempo_clock(FakeTime())  # beat 0 at START, 120 BPM: a bar every 2 s
    look = look_of(field_layer(0.5), modifiers=LookModifiers(downbeat_flash=True))
    runtime = runtime_of(look, clock=clock)

    runtime.tick(START + 2.0)  # renders a few hundredths of a beat past the downbeat
    assert latest(runtime)[0, 0] > 0.75
    runtime.tick(START + 2.5)  # a beat later
    assert latest(runtime)[0, 0] == pytest.approx(0.5)


# M2: the flash runs before the trails, so it leaves one.
def test_a_downbeat_flash_leaves_a_trail() -> None:
    clock = tempo_clock(FakeTime())  # beat 0 at START, 120 BPM: a bar every 2 s
    modifiers = LookModifiers(trails_s=10.0, downbeat_flash=True)
    runtime = runtime_of(look_of(field_layer(0.5), modifiers=modifiers), clock=clock)

    runtime.tick(START + 2.0)  # renders a few hundredths of a beat past the downbeat
    flash = latest(runtime)[0, 0]
    runtime.tick(START + 2.3)  # the flash is over (half a beat), its trail isn't

    assert flash > 0.75
    trail = flash * math.exp(-TRAILS_FALL * 0.3 / 10.0)
    assert latest(runtime)[0, 0] == pytest.approx(trail, rel=1e-5)


@pytest.mark.parametrize("on", [True, False])
def test_a_look_follows_the_evening_only_when_it_asks(on: bool) -> None:
    look = look_of(field_layer(0.5), modifiers=LookModifiers(evening=on))
    runtime = runtime_of(look, evening=lambda: 1.0)

    runtime.tick(1000.0)

    fullest = 0.5 * EVENING_FULLEST
    np.testing.assert_allclose(latest(runtime)[0], fullest if on else [0.5] * 3, rtol=1e-6)


class EveningField(FieldEffect, register=False):
    """Grey at the evening's amount, as the frame's signals carry it."""

    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {}

    def get_params(self) -> dict[str, Any]:
        return {}

    def _apply_params(self, **kwargs: Any) -> None:
        pass

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        return np.full((leds.count, 3), ctx.signals.get(EVENING), dtype=np.float32)


def test_an_effect_can_read_the_evening() -> None:
    Effect._registry["evening_field"] = EveningField
    layer = Layer(id="evening", name="Evening", type="field", kind="evening_field")
    runtime = runtime_of(look_of(layer), evening=lambda: 0.6)  # the look's own evening off

    runtime.tick(1000.0)

    np.testing.assert_allclose(latest(runtime), 0.6, rtol=1e-6)


def test_the_cap_caps_streamed_lights_and_the_preview_of_firmware_ones() -> None:
    look = look_of(field_layer(0.9), glow_layer(0.9), modifiers=LookModifiers(brightness_cap=0.6))
    runtime = runtime_of(look, brightness=0.5)

    runtime.tick(1000.0)

    assert runtime.mode_of("tile") == "own-effect"  # drawn for the preview, capped too
    np.testing.assert_allclose(latest(runtime), 0.6, rtol=1e-6)
    assert runtime.start_brightness("tile") == pytest.approx(0.3)  # brightness × cap


def test_a_new_cap_starts_the_firmware_effects_again() -> None:
    look = look_of(field_layer(), glow_layer(), modifiers=LookModifiers(brightness_cap=0.6))
    runtime = runtime_of(look)
    tile, lamp = runtime.applied_key("tile"), runtime.applied_key("lamp")

    runtime.update_look(replace(look, modifiers=LookModifiers(brightness_cap=0.8)))

    assert runtime.applied_key("tile") != tile  # its effect starts again, at 0.8
    assert runtime.start_brightness("tile") == pytest.approx(0.8)
    assert runtime.applied_key("lamp") == lamp  # no streamed light starts again
