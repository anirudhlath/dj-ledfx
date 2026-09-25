from __future__ import annotations

import math

import pytest
from map_home import tiny_home

from dj_ledfx.devices.lights import LightEntry
from dj_ledfx.home.geometry import point_in_polygon
from dj_ledfx.home.guess import (
    GUESS_HEIGHT_M,
    SPREAD_RADIUS_M,
    first_placements,
    guess_placements,
    largest_room,
    moved_scene_placements,
    seed_matches,
)
from dj_ledfx.home.model import Room
from dj_ledfx.home.seed import SeedLight
from dj_ledfx.home.shapes import CylinderShape, GridShape, LineShape, Placement, PointShape
from dj_ledfx.home.store import ScenePlacement

CANDLE = Placement(CylinderShape((1.0, 1.0, 0.8), 0.12, 0.02), "bottom-to-top")


def _light(light_id: str, name: str | None = None, *devices: str) -> LightEntry:
    return LightEntry(light_id, name or light_id, devices or (light_id,), 1)


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
        ScenePlacement("s1", "lamp", (1.0, 2.0, 1.0), "point", None, None, None, None, None),
        ScenePlacement(
            "s1", "strip", (3.0, 1.0, -1.0), "strip", (1.0, 0.0, 0.0), 0.5, None, None, None
        ),
        ScenePlacement("s2", "lamp", (9.0, 9.0, 9.0), "point", None, None, None, None, None),
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
    scene = [ScenePlacement("s1", "tile", (0.0, 1.0, 0.0), "matrix", None, None, None, 3, 4)]

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
        ScenePlacement("s1", "candle-1", (0.0, 0.0, 0.0), "point", None, None, None, None, None),
        ScenePlacement("s1", "gone", (4.0, 0.0, 0.0), "point", None, None, None, None, None),
    ]

    first = first_placements(home, lights, [_seed("Candle", "west")], scene)

    assert set(first) == {"candle-1", "lamp", "new"}  # a device no longer known is skipped
    west_label = (2.0, 2.0)  # tiny_home's west room
    assert first["candle-1"].shape == PointShape((*west_label, GUESS_HEIGHT_M))  # the seed's room
    assert isinstance(first["lamp"].shape, PointShape) and not first["new"].confirmed


def test_first_placements_are_unconfirmed_even_from_a_confirmed_seed() -> None:
    confirmed = Placement(CANDLE.shape, CANDLE.led_order, confirmed=True)
    first = first_placements(
        tiny_home(), [_light("candle-1", "Candle")], [_seed("Candle", "west", confirmed)], []
    )
    assert first["candle-1"] == CANDLE  # spec §6.2: every first placement starts unconfirmed
