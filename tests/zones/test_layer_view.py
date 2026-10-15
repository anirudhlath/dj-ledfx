"""Layer modifiers (spec §5.3): where a mask shows a layer, and where a mirror and a
transform make the effect look."""

from __future__ import annotations

import numpy as np
import pytest
from map_home import DESK_CORNER, leds_at, tiny_space

from dj_ledfx.effects.fx import Fx, planes, rings
from dj_ledfx.effects.particle_tools import swarm
from dj_ledfx.looks.model import (
    AnchorMask,
    HeightMask,
    Layer,
    Mirror,
    RoomMask,
    SubZoneMask,
    Transform,
)
from dj_ledfx.zones.layer_view import (
    layer_view,
    mask_weights,
    mask_weights_at,
    mirrored,
    transformed,
)


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


# What a layer draws in space, on the map (M8): in_home().


def _dots(*places: list[float]) -> Fx:
    return Fx(particles=swarm(places, (1.0, 0.5, 0.25), 0.2))


def test_in_home_undoes_the_transform_so_what_an_led_sees_lands_on_the_led() -> None:
    leds = leds_at([[1.0, 1.0, 1.0], [7.0, 3.0, 2.0], [4.0, 2.0, 0.5]], space=tiny_space())
    layer = Layer(
        id="a",
        name="A",
        type="field",
        kind="breathe",
        transform=Transform(offset=(0.5, -1.0, 0.25), rotate_deg=30.0, scale=1.5),
    )
    view = layer_view(layer, leds)
    seen = view.leds.pos.tolist()  # where in the effect's space each LED looks

    home = view.in_home(Fx(particles=swarm(seen, (1.0, 1.0, 1.0), 0.2)))

    assert np.allclose(home.particles.pos, leds.pos, atol=1e-5)
    assert np.allclose(home.particles.radius, 0.3)  # grown by the scale


def test_in_home_turns_a_planes_directions_and_grows_lengths_by_the_scale() -> None:
    leds = leds_at([[1.0, 1.0, 1.0], [7.0, 3.0, 1.0]], space=tiny_space())
    layer = Layer(
        id="a",
        name="A",
        type="field",
        kind="breathe",
        transform=Transform(offset=(1.0, 0.0, 0.0), rotate_deg=90.0, scale=2.0),
    )
    view = layer_view(layer, leds)
    at, ray, normal = [3.0, 2.0, 1.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]
    fx = Fx(
        rings=rings(at, 1.0, 0.1, (1.0, 0.0, 0.0)),
        planes=planes(at, normal, 0.2, (0.0, 1.0, 0.0), ray=ray),
    )
    # Where the map shows the effect's point, and the points a metre along its ray and
    # its normal.
    along = view.in_home(_dots(at, list(np.add(at, ray)), list(np.add(at, normal))))

    home = view.in_home(fx)

    there, ahead, up = along.particles.pos.astype(np.float64)
    assert np.allclose(home.rings.centre, [there]) and np.allclose(home.planes.point, [there])
    assert home.rings.radius.tolist() == [2.0]
    assert home.rings.width.tolist() == pytest.approx([0.2])
    assert home.planes.width.tolist() == pytest.approx([0.4])
    assert np.allclose(home.planes.ray[0] * 2.0, ahead - there, atol=1e-5)
    assert np.allclose(home.planes.normal[0] * 2.0, up - there, atol=1e-5)


def test_in_home_draws_a_particle_on_the_mirrors_low_side_at_both_its_images() -> None:
    leds = leds_at([[1.0, 1.0, 1.0], [7.0, 1.0, 1.0]], space=tiny_space())
    view = layer_view(
        Layer(id="a", name="A", type="field", kind="breathe", mirror=Mirror("x", 4.0)), leds
    )

    home = view.in_home(_dots([1.0, 1.0, 1.0], [6.0, 2.0, 1.0], [3.0, 2.0, 1.0]))

    # The particle at x 6 is on the high side, which no LED sees: left out. Each of the
    # others is drawn where it is and at its reflection, side by side, oldest first.
    assert home.particles.pos.tolist() == [
        [1.0, 1.0, 1.0],
        [7.0, 1.0, 1.0],
        [3.0, 2.0, 1.0],
        [5.0, 2.0, 1.0],
    ]
    # Every LED's own place is among the images of what it sees.
    seen = view.in_home(Fx(particles=swarm(view.leds.pos.tolist(), (1.0, 1.0, 1.0), 0.2)))
    for place in leds.pos:
        assert np.isclose(seen.particles.pos, place).all(axis=1).any()


def test_in_home_draws_rings_and_planes_whole_at_both_images_of_a_mirror() -> None:
    leds = leds_at([[1.0, 1.0, 1.0], [7.0, 1.0, 1.0]], space=tiny_space())
    view = layer_view(
        Layer(id="a", name="A", type="field", kind="breathe", mirror=Mirror("x", 4.0)), leds
    )
    fx = Fx(
        rings=rings([2.0, 1.0, 1.0], 3.0, 0.1, (1.0, 0.0, 0.0)),
        planes=planes(
            [2.0, 1.0, 1.0], (0.6, 0.8, 0.0), 0.2, (0.0, 1.0, 0.0), ray=(0.8, -0.6, 0.0)
        ),
    )

    home = view.in_home(fx)

    assert home.rings.centre.tolist() == [[2.0, 1.0, 1.0], [6.0, 1.0, 1.0]]
    assert home.rings.radius.tolist() == [3.0, 3.0]  # whole: a ring crossing the plane too
    assert home.planes.point.tolist() == [[2.0, 1.0, 1.0], [6.0, 1.0, 1.0]]
    assert np.allclose(home.planes.normal, [[0.6, 0.8, 0.0], [-0.6, 0.8, 0.0]])
    assert np.allclose(home.planes.ray, [[0.8, -0.6, 0.0], [-0.8, -0.6, 0.0]])


def test_in_home_weighs_particles_by_the_mask_where_they_land_and_drops_those_it_hides() -> None:
    leds = leds_at([[1.0, 1.0, 1.0], [1.0, 1.0, 2.0]], space=tiny_space())
    view = layer_view(
        Layer(id="a", name="A", type="field", kind="breathe", mask=HeightMask(0.5, 1.5)), leds
    )

    home = view.in_home(_dots([1.0, 1.0, 1.0], [1.0, 1.0, 1.5], [1.0, 1.0, 3.0]))

    # Inside in full, on the edge at half, above it gone.
    assert home.particles.pos[:, 2].tolist() == [1.0, 1.5]
    assert np.allclose(home.particles.colour, [[1.0, 0.5, 0.25], [0.5, 0.25, 0.125]])


def test_a_mask_keeps_rings_and_planes_whole_while_it_shows_any_led() -> None:
    fx = Fx(
        rings=rings([1.0, 1.0, 1.0], 2.0, 0.1, (1.0, 0.0, 0.0)),
        planes=planes([1.0, 1.0, 1.0], (0.0, 0.0, 1.0), 0.2, (0.0, 1.0, 0.0)),
    )
    leds = leds_at([[1.0, 1.0, 1.0], [7.0, 1.0, 1.0]], space=tiny_space())

    def masked(mask: RoomMask) -> Fx:
        layer = Layer(id="a", name="A", type="field", kind="breathe", mask=mask)
        return layer_view(layer, leds).in_home(fx)

    shown = masked(RoomMask("west"))
    assert (shown.rings.count, shown.planes.count) == (1, 1)
    assert shown.rings.radius.tolist() == [2.0]  # whole, past the room's outline too
    hidden = masked(RoomMask("no-such-room"))
    assert (hidden.rings.count, hidden.planes.count) == (0, 0)


def test_mask_weights_at_an_leds_place_is_the_leds_weight() -> None:
    leds = leds_at(
        [[1.0, 1.0, 0.2], [1.0, 1.0, 1.0], [7.0, 1.0, 0.5], [7.0, 3.0, 2.0]], space=tiny_space()
    )
    for mask in (HeightMask(0.5, 2.0), RoomMask("west"), AnchorMask("gone", 2.0)):
        assert np.array_equal(mask_weights_at(mask, leds.pos, leds), mask_weights(mask, leds))
