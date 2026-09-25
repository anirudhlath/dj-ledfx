from __future__ import annotations

import hashlib
import json
from importlib.resources import files
from pathlib import Path
from typing import Any

from dj_ledfx.home.seed import normalise_name, seed_home, seed_lights
from dj_ledfx.home.shapes import LED_ORDERS, shape_to_dict

DESIGN = Path(__file__).parents[2] / "docs" / "design" / "web-app"
VENDORED = files("dj_ledfx.home") / "data" / "home.json"
SHAPE_FIELDS = ("position", "path", "base", "height", "radius", "center", "width", "depth")


def _raw() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((DESIGN / "home.json").read_bytes())
    return data


def test_vendored_home_json_is_a_byte_copy_of_the_handoff() -> None:
    vendored = VENDORED.read_bytes()
    assert vendored == (DESIGN / "home.json").read_bytes()
    pinned = {
        name: digest
        for digest, name in (
            line.split() for line in (DESIGN / "HANDOFF.sha256").read_text().splitlines() if line
        )
    }
    assert hashlib.sha256(vendored).hexdigest() == pinned["home.json"]


def test_the_seed_map_is_the_handoff_map() -> None:
    raw, home = _raw(), seed_home()
    assert [room.id for room in home.rooms] == [room["id"] for room in raw["rooms"]]
    assert [sub.id for sub in home.sub_zones] == [sub["id"] for sub in raw["subZones"]]
    assert [anchor.id for anchor in home.anchors] == [anchor["id"] for anchor in raw["anchors"]]
    assert home.ceiling == raw["ceiling"]


def test_seed_lights_carry_the_handoff_placements() -> None:
    raw = _raw()["lights"]
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
