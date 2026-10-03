from __future__ import annotations

import math

import numpy as np
import pytest
from map_home import ROUND_MATRIX, SMALL_MATRIX, UPRIGHT_LAMP, tiny_home

from dj_ledfx.devices.govee.adapter_base import UPRIGHT_HEIGHT_M
from dj_ledfx.devices.lights import LightEntry, LightPart
from dj_ledfx.home.geometry import point_in_polygon
from dj_ledfx.home.guess import (
    GUESS_HEIGHT_M,
    SPREAD_RADIUS_M,
    UPRIGHT_BASE_M,
    UPRIGHT_GRID,
    first_placements,
    fitted,
    guess_placements,
    in_form,
    largest_room,
    moved_scene_placements,
    placed_in_form,
    seed_matches,
)
from dj_ledfx.home.model import Room
from dj_ledfx.home.seed import SeedLight
from dj_ledfx.home.shapes import (
    CylinderShape,
    GridShape,
    LineShape,
    Placement,
    PointShape,
    led_positions,
    shape_centre,
)
from dj_ledfx.home.store import ScenePlacement
from dj_ledfx.spatial.geometry import DeviceGeometry, MatrixGeometry, PointGeometry, StripGeometry

CANDLE = Placement(CylinderShape((1.0, 1.0, 0.8), 0.12, 0.02), "bottom-to-top", source="seed")


def _light(light_id: str, name: str | None = None, *devices: str, leds: int = 1) -> LightEntry:
    """A light of these devices (just itself by default), each part `leds` LEDs."""
    parts = tuple(LightPart(device, device, leds) for device in devices or (light_id,))
    return LightEntry(light_id, name or light_id, devices or (light_id,), leds * len(parts), parts)


def _seed(name: str, room: str, placement: Placement = CANDLE) -> SeedLight:
    return SeedLight(
        id=name.lower(), name=name, room=room, sub_zone=None, leds=26, placement=placement
    )


def test_seeds_match_by_name_and_each_seed_goes_to_one_light() -> None:
    lights = [_light("a", "Desk Lamp"), _light("b", "desk-lamp"), _light("c", "Other")]
    matches = seed_matches(lights, [_seed("Desk lamp", "west")])
    assert list(matches) == ["a"]


def test_unplaced_lights_take_their_seed_or_are_spread_round_the_largest_room() -> None:
    home = tiny_home()
    lights = [_light("candle-1", "Candle"), _light("x"), _light("y"), _light("done")]

    guesses = guess_placements(home, lights, {"done"}, [_seed("Candle", "west")])

    assert set(guesses) == {"candle-1", "x", "y"}
    assert guesses["candle-1"] == CANDLE and guesses["x"].source == "guess"
    room = largest_room(home)
    cx, cy = room.label_at
    for light_id in ("x", "y"):
        shape = guesses[light_id].shape
        assert isinstance(shape, PointShape)
        x, y, z = shape.position
        assert math.hypot(x - cx, y - cy) == pytest.approx(SPREAD_RADIUS_M)
        assert point_in_polygon((x, y), room.polygon) and z == GUESS_HEIGHT_M
    assert not any(guess.confirmed for guess in guesses.values())


def test_a_spread_point_outside_the_room_falls_back_to_its_label() -> None:
    hall = Room("hall", "Hall", ((0.0, 0.0), (1.0, 0.0), (1.0, 0.5), (0.0, 0.5)), (0.5, 0.25))
    home = tiny_home(rooms=(hall,), sub_zones=())

    guesses = guess_placements(home, [_light("x")], set(), [])

    assert guesses["x"].shape == PointShape((0.5, 0.25, GUESS_HEIGHT_M))  # 0.8 m east is outside


def test_scene_placements_move_onto_the_map_round_their_rooms_centre() -> None:
    home = tiny_home()
    scene = [
        ScenePlacement("s1", "lamp", (1.0, 2.0, 1.0), "point", None, None, None, None),
        ScenePlacement("s1", "strip", (3.0, 1.0, -1.0), "strip", (1.0, 0.0, 0.0), 0.5, None, None),
        ScenePlacement("s2", "lamp", (9.0, 9.0, 9.0), "point", None, None, None, None),
    ]

    moved = moved_scene_placements(home, scene, lambda device_id: "east")

    # The scene's centre is (2, 1.5, 0), its y is up and its z is south: the lamp sits
    # 1 m west, 1 m south and 0.5 m up from the east room's label point (6, 2).
    # Each is the owner's: they placed it on the old scene page.
    lamp = Placement(PointShape((5.0, 3.0, GUESS_HEIGHT_M + 0.5)), "", source="owner")
    assert moved["lamp"] == lamp
    assert moved["strip"] == Placement(
        LineShape(((7.0, 1.0, GUESS_HEIGHT_M - 0.5), (7.5, 1.0, GUESS_HEIGHT_M - 0.5))),
        "along-path",
        source="owner",
    )  # the first scene that placed a device wins


def test_a_scene_matrix_becomes_a_standing_grid_and_the_room_defaults_to_the_largest() -> None:
    home = tiny_home()
    scene = [ScenePlacement("s1", "tile", (0.0, 1.0, 0.0), "matrix", None, None, 3, 4)]

    moved = moved_scene_placements(home, scene, lambda device_id: None)

    cx, cy = largest_room(home).label_at
    shape = moved["tile"].shape
    assert isinstance(shape, GridShape)
    assert shape.center == (cx, cy, GUESS_HEIGHT_M) and shape.rotation == UPRIGHT_GRID
    assert (shape.width, shape.depth) == pytest.approx((0.12, 0.09))  # 4 columns, 3 rows


def test_first_placements_put_the_scene_over_the_seed_and_spread_the_rest() -> None:
    home = tiny_home()
    lights = [_light("candle-1", "Candle"), _light("lamp"), _light("new")]
    scene = [
        ScenePlacement("s1", "candle-1", (0.0, 0.0, 0.0), "point", None, None, None, None),
        ScenePlacement("s1", "gone", (4.0, 0.0, 0.0), "point", None, None, None, None),
    ]

    first = first_placements(home, lights, [_seed("Candle", "west")], scene)

    assert set(first) == {"candle-1", "lamp", "new"}  # a device no longer known is skipped
    assert first["candle-1"].source == "owner"  # the old scene, the owner's, over the seed
    assert (first["lamp"].source, first["new"].source) == ("guess", "guess")
    west_label = (2.0, 2.0)  # tiny_home's west room
    assert first["candle-1"].shape == PointShape((*west_label, GUESS_HEIGHT_M))  # the seed's room
    assert isinstance(first["lamp"].shape, PointShape) and not first["new"].confirmed


def test_a_bad_scene_placement_is_skipped_and_its_light_is_guessed_instead() -> None:
    home = tiny_home()
    lights = [_light("lamp"), _light("far"), _light("lost"), _light("tile"), _light("huge")]
    scene = [
        ScenePlacement("s1", "lamp", (1.0, 2.0, 1.0), "point", None, None, None, None),
        ScenePlacement("s1", "far", (math.inf, 0.0, 0.0), "point", None, None, None, None),
        ScenePlacement(
            "s1", "lost", (1.0, 2.0, 1.0), "strip", (1.0, 0.0, 0.0), math.nan, None, None
        ),
        ScenePlacement("s2", "tile", (0.0, 1.0, 0.0), "matrix", None, None, 0, 0),
        ScenePlacement("s3", "huge", (0.0, 1.0, 0.0), "matrix", None, None, 1, 10**6),
    ]

    first = first_placements(home, lights, [], scene)

    cx, cy = largest_room(home).label_at
    assert first["lamp"].shape == PointShape(
        (cx, cy, GUESS_HEIGHT_M)
    )  # the bad one isn't in its centre
    for light_id in ("far", "lost", "huge"):  # skipped: spread round the largest room instead
        shape = first[light_id].shape
        assert isinstance(shape, PointShape)
        assert math.hypot(shape.position[0] - cx, shape.position[1] - cy) == pytest.approx(
            SPREAD_RADIUS_M
        )
    tile = first["tile"].shape  # a zero-size matrix still hangs as one LED's grid
    assert isinstance(tile, GridShape) and (tile.width, tile.depth) == pytest.approx((0.03, 0.03))


DOWN = StripGeometry((0.0, -1.0, 0.0), UPRIGHT_HEIGHT_M)  # an upright lamp, LED 1 at the top
ALONG = StripGeometry((1.0, 0.0, 0.0), 1.0)  # a strip, running east
AT = (2.0, 2.0, 1.0)


def test_an_upright_lamp_stands_on_the_floor_below_its_spot() -> None:
    top = UPRIGHT_BASE_M + UPRIGHT_HEIGHT_M
    up = placed_in_form(AT, 15, UPRIGHT_LAMP)
    assert up == Placement(LineShape(((2.0, 2.0, UPRIGHT_BASE_M), (2.0, 2.0, top))), "along-path")
    assert placed_in_form(AT, 15, DOWN).led_order == "reverse-path"
    assert not up.confirmed


def test_a_strip_lies_through_its_spot_along_its_length() -> None:
    strip = placed_in_form(AT, 30, ALONG)
    assert strip == Placement(LineShape(((1.5, 2.0, 1.0), (2.5, 2.0, 1.0))), "along-path")


def test_a_matrix_stands_as_a_grid_with_its_first_row_at_the_top() -> None:
    matrix = placed_in_form(AT, 30, SMALL_MATRIX)
    assert isinstance(matrix.shape, GridShape) and matrix.led_order == "rows"
    assert (matrix.shape.width, matrix.shape.depth) == pytest.approx((0.15, 0.18))
    leds = led_positions(matrix.shape, 30, matrix.led_order).pos
    assert leds[0][2] > leds[-1][2]  # LED 1 on top, as a matrix's own frame has it
    assert np.allclose(leds[:, 1], AT[1])  # standing: every LED at one depth


def test_a_matrix_stands_first_row_highest_whether_moved_from_a_scene_or_fitted() -> None:
    scene = [ScenePlacement("s1", "tile", (0.0, 1.0, 0.0), "matrix", None, None, 6, 5)]
    moved = moved_scene_placements(tiny_home(), scene, lambda device_id: None)["tile"]
    fitted = placed_in_form(AT, 30, SMALL_MATRIX)
    for placement in (moved, fitted):
        z = led_positions(placement.shape, 30, placement.led_order).pos[:, 2]
        assert z[0] == pytest.approx(z.max()) and z[0] > z[-1]  # row 0 is the highest


def test_a_candle_or_tube_stands_round_its_spot_as_a_cylinder_first_row_at_the_top() -> None:
    candle = placed_in_form(AT, 30, ROUND_MATRIX)
    shape = candle.shape
    assert isinstance(shape, CylinderShape) and candle.led_order == "top-to-bottom"
    assert shape_centre(shape) == pytest.approx(AT)
    assert shape.height == pytest.approx(0.18)  # its 6 rows
    assert 2 * math.pi * shape.radius == pytest.approx(0.15)  # its 5 columns go round it
    z = led_positions(shape, 30, candle.led_order, ROUND_MATRIX).pos[:, 2]
    assert z[0] == pytest.approx(z.max())  # row 0 at the top, as a grid's is


def test_a_light_of_one_led_or_of_no_known_form_is_a_point() -> None:
    for leds, geometry in ((1, UPRIGHT_LAMP), (15, None), (15, PointGeometry())):
        assert placed_in_form(AT, leds, geometry) == Placement(PointShape(AT), "")


def test_many_leds_on_a_point_and_an_upright_lamp_lying_down_hide_a_form() -> None:
    point = Placement(PointShape(AT), "")
    lying = Placement(LineShape(((1.0, 2.0, 1.0), (2.4, 2.0, 1.0))), "along-path")
    standing = Placement(LineShape(((2.0, 2.0, 0.1), (2.0, 2.0, 1.5))), "along-path")
    assert not in_form(point, 15, UPRIGHT_LAMP) and not in_form(point, 30, SMALL_MATRIX)
    assert not in_form(lying, 15, UPRIGHT_LAMP) and in_form(standing, 15, UPRIGHT_LAMP)
    assert (
        in_form(lying, 30, ALONG) and in_form(point, 1, UPRIGHT_LAMP) and in_form(point, 15, None)
    )


def test_a_candle_whose_rows_run_up_has_them_turned_where_it_stands() -> None:
    """On the lights, a candle's and a tube's first row is at the top (the light-output
    plan's Task 8), and home.json's seeds run their rows bottom to top: the fit turns the
    rows and keeps the seed's spot and size."""
    assert not in_form(CANDLE, 30, ROUND_MATRIX)
    turned = fitted(CANDLE, 30, ROUND_MATRIX)
    assert turned == Placement(CANDLE.shape, "top-to-bottom")  # a refit's, so a guess
    z = led_positions(turned.shape, 30, turned.led_order, ROUND_MATRIX).pos[:, 2]
    assert z[0] == pytest.approx(z.max())  # row 0 at the top
    assert fitted(turned, 30, ROUND_MATRIX) is None
    assert in_form(CANDLE, 30, SMALL_MATRIX)  # a flat matrix's rows aren't judged on one


def test_any_other_placement_that_hides_a_form_is_made_again_at_its_centre() -> None:
    point = Placement(PointShape(AT), "")
    assert fitted(point, 15, UPRIGHT_LAMP) == placed_in_form(AT, 15, UPRIGHT_LAMP)
    assert fitted(point, 1, UPRIGHT_LAMP) is None  # one LED has no form to hide


@pytest.mark.parametrize(
    "geometry",
    [
        UPRIGHT_LAMP,
        DOWN,
        ALONG,
        SMALL_MATRIX,
        ROUND_MATRIX,
        MatrixGeometry(()),
        PointGeometry(),
        None,
    ],
    ids=[
        "upright",
        "upside-down",
        "strip",
        "matrix",
        "round-matrix",
        "matrix-without-tiles",
        "point",
        "none",
    ],
)
@pytest.mark.parametrize("leds", [1, 30])
def test_a_light_placed_in_its_form_is_in_its_form(
    geometry: DeviceGeometry | None, leds: int
) -> None:
    """One classifier decides a light's form for both, so a placement made in form never
    hides it, and a refit never makes the same placement again."""
    placement = placed_in_form(AT, leds, geometry)
    assert in_form(placement, leds, geometry) and fitted(placement, leds, geometry) is None


def test_a_guess_puts_each_loose_light_in_its_form() -> None:
    guesses = guess_placements(
        tiny_home(),
        [_light("lamp", leds=15), _light("bulb")],
        set(),
        [],
        geometry_of=lambda light: UPRIGHT_LAMP if light.id == "lamp" else None,
    )
    lamp = guesses["lamp"].shape
    assert isinstance(lamp, LineShape) and lamp.path[0][2] == UPRIGHT_BASE_M
    assert isinstance(guesses["bulb"].shape, PointShape)
