from __future__ import annotations

import math

import numpy as np
import pytest
from map_home import tiny_home

from dj_ledfx.devices.lights import LightEntry, LightPart
from dj_ledfx.home.geometry import point_in_polygon
from dj_ledfx.home.guess import (
    GUESS_HEIGHT_M,
    SPREAD_RADIUS_M,
    UPRIGHT_BASE_M,
    first_placements,
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
)
from dj_ledfx.home.store import ScenePlacement
from dj_ledfx.spatial.geometry import MatrixGeometry, PointGeometry, StripGeometry, TileLayout

CANDLE = Placement(CylinderShape((1.0, 1.0, 0.8), 0.12, 0.02), "bottom-to-top")


def _light(light_id: str, name: str | None = None, *devices: str) -> LightEntry:
    parts = tuple(LightPart(device, device, 1) for device in devices or (light_id,))
    return LightEntry(light_id, name or light_id, devices or (light_id,), len(parts), parts)


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
    assert guesses["candle-1"] == CANDLE
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
    assert moved["lamp"] == Placement(PointShape((5.0, 3.0, GUESS_HEIGHT_M + 0.5)), "")
    assert moved["strip"] == Placement(
        LineShape(((7.0, 1.0, GUESS_HEIGHT_M - 0.5), (7.5, 1.0, GUESS_HEIGHT_M - 0.5))),
        "along-path",
    )  # the first scene that placed a device wins


def test_a_scene_matrix_becomes_a_standing_grid_and_the_room_defaults_to_the_largest() -> None:
    home = tiny_home()
    scene = [ScenePlacement("s1", "tile", (0.0, 1.0, 0.0), "matrix", None, None, 3, 4)]

    moved = moved_scene_placements(home, scene, lambda device_id: None)

    cx, cy = largest_room(home).label_at
    shape = moved["tile"].shape
    assert isinstance(shape, GridShape)
    assert shape.center == (cx, cy, GUESS_HEIGHT_M) and shape.rotation == (0.0, 90.0, 0.0)
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


UP = StripGeometry((0.0, 1.0, 0.0), 1.4)  # an upright lamp, its first LED at the bottom
DOWN = StripGeometry((0.0, -1.0, 0.0), 1.4)  # its first LED at the top
ALONG = StripGeometry((1.0, 0.0, 0.0), 1.0)  # a strip, running east
TILE = MatrixGeometry((TileLayout(0.0, 0.0, 5, 6),), pixel_pitch=0.03)
AT = (2.0, 2.0, 1.0)


def _many(light_id: str, leds: int) -> LightEntry:
    return LightEntry(
        light_id, light_id, (light_id,), leds, (LightPart(light_id, light_id, leds),)
    )


def test_an_upright_lamp_stands_on_the_floor_below_its_spot() -> None:
    top = UPRIGHT_BASE_M + 1.4
    up = placed_in_form(AT, 15, UP)
    assert up == Placement(LineShape(((2.0, 2.0, UPRIGHT_BASE_M), (2.0, 2.0, top))), "along-path")
    assert placed_in_form(AT, 15, DOWN).led_order == "reverse-path"
    assert not up.confirmed


def test_a_strip_lies_through_its_spot_along_its_length() -> None:
    strip = placed_in_form(AT, 30, ALONG)
    assert strip == Placement(LineShape(((1.5, 2.0, 1.0), (2.5, 2.0, 1.0))), "along-path")


def test_a_matrix_stands_as_a_grid_with_its_first_row_at_the_top() -> None:
    matrix = placed_in_form(AT, 30, TILE)
    assert isinstance(matrix.shape, GridShape) and matrix.led_order == "rows"
    assert (matrix.shape.width, matrix.shape.depth) == pytest.approx((0.15, 0.18))
    leds = led_positions(matrix.shape, 30, matrix.led_order).pos
    assert leds[0][2] > leds[-1][2]  # LED 1 on top, as a matrix's own frame has it
    assert np.allclose(leds[:, 1], AT[1])  # standing: every LED at one depth


def test_a_light_of_one_led_or_of_no_known_form_is_a_point() -> None:
    for leds, geometry in ((1, UP), (15, None), (15, PointGeometry())):
        assert placed_in_form(AT, leds, geometry) == Placement(PointShape(AT), "")


def test_only_many_leds_on_a_point_or_an_upright_lamp_lying_down_hide_a_form() -> None:
    point = PointShape(AT)
    lying = LineShape(((1.0, 2.0, 1.0), (2.4, 2.0, 1.0)))
    standing = LineShape(((2.0, 2.0, 0.1), (2.0, 2.0, 1.5)))
    assert not in_form(point, 15, UP) and not in_form(point, 30, TILE)
    assert not in_form(lying, 15, UP) and in_form(standing, 15, UP)
    assert in_form(lying, 30, ALONG) and in_form(point, 1, UP) and in_form(point, 15, None)


def test_a_guess_puts_each_loose_light_in_its_form() -> None:
    guesses = guess_placements(
        tiny_home(),
        [_many("lamp", 15), _light("bulb")],
        set(),
        [],
        geometry_of=lambda light: UP if light.id == "lamp" else None,
    )
    lamp = guesses["lamp"].shape
    assert isinstance(lamp, LineShape) and lamp.path[0][2] == UPRIGHT_BASE_M
    assert isinstance(guesses["bulb"].shape, PointShape)
