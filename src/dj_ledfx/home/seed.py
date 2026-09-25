"""The map and the lights this home starts with: the handoff's home.json, vendored byte
for byte in home/data (spec §6.2; ruling 1).

The seed's lights are the designer's estimates. They seed placements, matched to real
lights by name (home/guess.py), and are never lights themselves.
"""

from __future__ import annotations

import functools
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from importlib.resources import files
from typing import Any

from dj_ledfx.home.model import Home, home_from_dict
from dj_ledfx.home.shapes import Placement, check_led_order, shape_from_dict


@dataclass(frozen=True, slots=True)
class SeedLight:
    id: str
    name: str
    room: str
    sub_zone: str | None
    leds: int  # the designer's estimate, not the light's
    placement: Placement


@functools.cache
def handoff_home_json() -> Mapping[str, Any]:
    """The vendored home.json, read once. Callers must not change it."""
    data: Mapping[str, Any] = json.loads(
        (files("dj_ledfx.home") / "data" / "home.json").read_bytes()
    )
    return data


# The rooms the owner has named over home.json (ruling 18). The web spec and the renders call
# the room with id corridor "Entrance". The design files are never edited by hand, so the seed
# renames it, and once a handoff names the room so itself this changes nothing.
OWNER_ROOM_NAMES: Mapping[str, str] = {"corridor": "Entrance"}


def with_owner_names(home: Home) -> Home:
    """The map, with the owner's names for its rooms (OWNER_ROOM_NAMES)."""
    rooms = tuple(
        replace(room, name=OWNER_ROOM_NAMES[room.id]) if room.id in OWNER_ROOM_NAMES else room
        for room in home.rooms
    )
    return replace(home, rooms=rooms)


def seed_home() -> Home:
    return with_owner_names(home_from_dict(handoff_home_json()))


def _seed_light(light: Mapping[str, Any]) -> SeedLight:
    """A home.json light as a seed. Its placement is always unconfirmed: the seed is the
    designer's estimate (spec §6.2), whatever its confirmed field says."""
    kind = str(light["shape"])
    shape = shape_from_dict({**light, "kind": kind})
    return SeedLight(
        id=str(light["id"]),
        name=str(light["name"]),
        room=str(light["room"]),
        sub_zone=light.get("subZone"),
        leds=int(light["leds"]),
        placement=Placement(shape, check_led_order(kind, light.get("ledOrder"))),
    )


@functools.cache
def seed_lights() -> tuple[SeedLight, ...]:
    return tuple(_seed_light(light) for light in handoff_home_json().get("lights", ()))


def normalise_name(name: str) -> str:
    """A light's name as matching sees it: lower case, words split on anything else."""
    return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()
