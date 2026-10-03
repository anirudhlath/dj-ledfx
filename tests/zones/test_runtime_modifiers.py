"""A zone runtime plays its layers' and its look's modifiers (spec §5.3)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace
from types import MappingProxyType

import numpy as np
import pytest
from map_home import tiny_home
from runtime_fakes import (
    FlatField,
    PlaceField,
    field_layer,
    latest,
    look_of,
    place_layer,
    placed_light,
    register_fields,
    runtime_of,
)

from dj_ledfx.home.map import space_of
from dj_ledfx.looks.model import Mirror, RoomMask, SubZoneMask, Transform

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
