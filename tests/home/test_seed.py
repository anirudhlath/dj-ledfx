from __future__ import annotations

import hashlib
from dataclasses import replace
from importlib.resources import files

from map_home import DESIGN, EAST, design_home_json, handoff_pins, tiny_home

from dj_ledfx.home.model import Room
from dj_ledfx.home.seed import (
    OWNER_ROOM_NAMES,
    _seed_light,
    normalise_name,
    seed_home,
    seed_lights,
    with_owner_names,
)
from dj_ledfx.home.shapes import LED_ORDERS, shape_to_dict

VENDORED = files("dj_ledfx.home") / "data" / "home.json"
SHAPE_FIELDS = ("position", "path", "base", "height", "radius", "center", "width", "depth")


def test_vendored_home_json_is_a_byte_copy_of_the_handoff() -> None:
    vendored = VENDORED.read_bytes()
    assert vendored == (DESIGN / "home.json").read_bytes()
    pinned = handoff_pins()
    assert hashlib.sha256(vendored).hexdigest() == pinned["home.json"]


def test_the_seed_map_is_the_handoff_map() -> None:
    raw, home = design_home_json(), seed_home()
    assert [room.id for room in home.rooms] == [room["id"] for room in raw["rooms"]]
    assert [sub.id for sub in home.sub_zones] == [sub["id"] for sub in raw["subZones"]]
    assert [anchor.id for anchor in home.anchors] == [anchor["id"] for anchor in raw["anchors"]]
    assert home.ceiling == raw["ceiling"]


def test_seed_lights_carry_the_handoff_placements() -> None:
    raw = design_home_json()["lights"]
    seeds = seed_lights()
    assert [seed.id for seed in seeds] == [light["id"] for light in raw]
    for seed, light in zip(seeds, raw, strict=True):
        assert (seed.name, seed.room, seed.sub_zone, seed.leds) == (
            light["name"],
            light["room"],
            light["subZone"],
            light["leds"],
        )
        shape = shape_to_dict(seed.placement.shape)
        assert shape["kind"] == light["shape"], seed.id
        for key in SHAPE_FIELDS:
            if key in light:
                assert shape[key] == light[key], (seed.id, key)
        assert seed.placement.led_order == (light.get("ledOrder") or LED_ORDERS[light["shape"]][0])
        assert not seed.placement.confirmed


def test_names_are_matched_without_case_or_punctuation() -> None:
    assert normalise_name("  Desk  Lamp-2 ") == "desk lamp 2"
    assert normalise_name("DESK_lamp 2") == normalise_name("desk lamp (2)")


def test_the_seed_names_the_corridor_entrance_and_keeps_every_other_name() -> None:
    raw = {room["id"]: room["name"] for room in design_home_json()["rooms"]}
    seeded = {room.id: room.name for room in seed_home().rooms}

    assert OWNER_ROOM_NAMES == {"corridor": "Entrance"}  # the owner's decision, 2026-09-24
    assert "corridor" in raw
    assert seeded == {**raw, "corridor": "Entrance"}


def test_the_owner_names_rename_a_room_once_and_leave_the_rest() -> None:
    hall = Room("corridor", "Hall", EAST, (6.0, 2.0))
    entrance = replace(hall, name="Entrance")

    assert with_owner_names(tiny_home(rooms=(hall,))).rooms == (entrance,)
    assert with_owner_names(tiny_home(rooms=(entrance,))) == tiny_home(rooms=(entrance,))
    assert with_owner_names(tiny_home()) == tiny_home()


def test_a_seed_marked_confirmed_in_its_source_still_seeds_unconfirmed() -> None:
    light = {
        "id": "lamp",
        "name": "Lamp",
        "room": "west",
        "shape": "point",
        "position": [1.0, 1.0, 1.0],
        "leds": 1,
        "confirmed": True,
    }
    assert not _seed_light(light).placement.confirmed  # seeds are estimates (spec §6.2)
