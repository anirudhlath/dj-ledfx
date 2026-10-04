"""Layer modifiers (spec §5.3): where a mask shows a layer, and where a mirror and a
transform make the effect look."""

from __future__ import annotations

import numpy as np
import pytest
from map_home import DESK_CORNER, leds_at, tiny_space

from dj_ledfx.looks.model import (
    AnchorMask,
    HeightMask,
    Layer,
    Mirror,
    RoomMask,
    SubZoneMask,
    Transform,
)
from dj_ledfx.zones.layer_view import layer_view, mask_weights, mirrored, transformed


def test_a_height_mask_shows_the_layer_between_its_heights_with_a_soft_edge() -> None:
    leds = leds_at(
        [[1.0, 1.0, 0.2], [1.0, 1.0, 1.0], [1.0, 1.0, 0.5], [1.0, 1.0, 2.0], [1.0, 1.0, 2.5]],
        space=tiny_space(),
    )
    assert np.allclose(mask_weights(HeightMask(0.5, 2.0), leds), [0.0, 1.0, 0.5, 0.5, 0.0])


def test_a_room_or_sub_zone_mask_shows_the_layer_inside_its_outline() -> None:
    leds = leds_at([[1.0, 1.0, 1.0], [6.0, 1.0, 1.0], DESK_CORNER], space=tiny_space())
    assert mask_weights(RoomMask("west"), leds).tolist() == [1.0, 0.0, 1.0]
    assert mask_weights(RoomMask("east"), leds).tolist() == [0.0, 1.0, 0.0]
    assert mask_weights(SubZoneMask("desk"), leds).tolist() == [0.0, 0.0, 1.0]


@pytest.mark.parametrize("mask", [RoomMask("attic"), SubZoneMask("nook")])
def test_a_room_or_sub_zone_the_map_lacks_shows_the_layer_nowhere(
    mask: RoomMask | SubZoneMask,
) -> None:
    leds = leds_at([[1.0, 1.0, 1.0], [6.0, 1.0, 1.0]], space=tiny_space())
    assert mask_weights(mask, leds).tolist() == [0.0, 0.0]


def test_an_anchor_mask_shows_the_layer_within_its_reach() -> None:
    sofa = (6.0, 2.0, 0.5)
    leds = leds_at([[6.5, 2.0, 0.5], [7.0, 2.0, 0.5], [8.0, 2.0, 0.5]], space=tiny_space())
    assert np.allclose(mask_weights(AnchorMask("sofa", 1.0), leds), [1.0, 0.5, 0.0])
    # An anchor the map lacks is the zone's middle, as it is for the effects.
    middle = leds_at([sofa, [6.0, 2.0, 3.5]], space=tiny_space())  # the middle is at z 2.0
    assert np.allclose(mask_weights(AnchorMask("gone", 1.0), middle), [0.0, 0.0])
    assert np.allclose(mask_weights(AnchorMask("gone", 2.0), middle), [1.0, 1.0])


def test_a_mirror_folds_the_high_side_onto_the_low_side() -> None:
    pos = np.array([[1.0, 0.0, 0.0], [5.0, 3.0, 0.0], [7.0, 1.0, 2.0]])
    centre = np.array([3.0, 1.0, 1.0], dtype=np.float32)
    assert np.allclose(mirrored(Mirror("x", 4.0), pos, centre), [[1, 0, 0], [3, 3, 0], [1, 1, 2]])
    assert np.allclose(mirrored(Mirror("y"), pos, centre), [[1, 0, 0], [5, -1, 0], [7, 1, 2]])
    assert np.allclose(mirrored(Mirror("z"), pos, centre), [[1, 0, 0], [5, 3, 0], [7, 1, 0]])


def test_a_transform_moves_turns_and_grows_the_field_about_the_zones_centre() -> None:
    centre = np.array([4.0, 2.0, 1.0], dtype=np.float32)
    east_of_it = np.array([[5.0, 2.0, 1.0]])
    # Moved a metre east, the field the LED shows is the one at the centre.
    assert np.allclose(
        transformed(Transform(offset=(1.0, 0.0, 0.0)), east_of_it, centre), [centre]
    )
    # Turned a quarter clockwise seen from above, the LED east of the centre shows what was
    # north of it (y points south).
    assert np.allclose(transformed(Transform(rotate_deg=90.0), east_of_it, centre), [[4, 1, 1]])
    # Grown twice as big, the LED shows what was half as far out.
    assert np.allclose(transformed(Transform(scale=2.0), east_of_it, centre), [[4.5, 2, 1]])


def test_a_layer_without_modifiers_draws_on_the_zones_own_leds() -> None:
    leds = leds_at([[1.0, 1.0, 1.0], [6.0, 1.0, 1.0]], space=tiny_space())
    view = layer_view(Layer(id="a", name="A", type="field", kind="breathe"), leds)
    assert view.leds is leds and view.weight is None


def test_a_moved_view_keeps_the_zones_bounds_and_weighs_by_where_the_leds_are() -> None:
    leds = leds_at([[1.0, 1.0, 1.0], [7.0, 1.0, 1.0]], space=tiny_space())
    layer = Layer(
        id="a",
        name="A",
        type="field",
        kind="breathe",
        mask=RoomMask("west"),
        mirror=Mirror("x", 4.0),
    )
    view = layer_view(layer, leds)
    assert np.allclose(view.leds.pos[:, 0], [1.0, 1.0])  # the east LED sees the west side
    assert all(np.allclose(a, b) for a, b in zip(view.leds.bounds, leds.bounds, strict=True))
    assert view.weight is not None and view.weight.tolist() == [[1.0], [0.0]]  # where it is
