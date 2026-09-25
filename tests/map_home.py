"""Home maps for tests.

tiny_home() is two 4 x 4 m rooms side by side, west and east, with a desk corner in the
west one, a sofa anchor and a speaker pair in the east one. Task 20 adds this home's
lights from the vendored home.json.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any

import numpy as np

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.devices.manager import DeviceManager
from dj_ledfx.effects.ledset import NO_ROOM, LedSet, LedSource, PlacedLeds, Space, build_ledset
from dj_ledfx.home.map import HomeMap, space_of
from dj_ledfx.home.model import Anchor, Box2, Furniture, Home, Location, Room, SubZone, Wall
from dj_ledfx.home.seed import handoff_home_json, seed_home, seed_lights
from dj_ledfx.home.shapes import Placement, led_positions
from dj_ledfx.home.store import HomeStore
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.persistence.state_db import StateDB
from dj_ledfx.timing import utcnow
from dj_ledfx.zones.runtime import ZoneLight

WEST = ((0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0))
EAST = ((4.0, 0.0), (8.0, 0.0), (8.0, 4.0), (4.0, 4.0))
DESK = ((0.0, 3.0), (2.0, 3.0), (2.0, 4.0), (0.0, 4.0))


# Points on tiny_home: in the west room's desk corner, and in the east room. The dicts are
# the contract's shapes of lights placed there.
DESK_CORNER = (1.0, 3.5, 1.0)
EAST_SPOT = (6.0, 3.0, 1.0)
IN_THE_DESK_CORNER = {"kind": "point", "position": list(DESK_CORNER)}
IN_THE_EAST_ROOM = {"kind": "point", "position": list(EAST_SPOT)}

# The design handoff's files, which the vendored copies must equal byte for byte.
DESIGN = Path(__file__).parents[1] / "docs" / "design" / "web-app"


def handoff_pins() -> dict[str, str]:
    """HANDOFF.sha256: each design file's pinned SHA-256, by file name."""
    lines = (DESIGN / "HANDOFF.sha256").read_text().splitlines()
    return {name: digest for digest, name in (line.split() for line in lines if line)}


def design_home_json() -> dict[str, Any]:
    """The handoff's home.json, as the design files have it."""
    data: dict[str, Any] = json.loads((DESIGN / "home.json").read_bytes())
    return data


def tiny_home(**changes: Any) -> Home:
    home = Home(
        outline=((0.0, 0.0), (8.0, 0.0), (8.0, 4.0), (0.0, 4.0)),
        rooms=(
            Room("west", "West room", WEST, (2.0, 2.0)),
            Room("east", "East room", EAST, (6.0, 2.0)),
        ),
        sub_zones=(SubZone("desk", "Desk", "west", DESK),),
        walls=(
            Wall((0.0, 0.0), (0.0, 4.0), "window", west_facing=True, exterior=True, thickness=0.2),
            Wall((4.0, 0.0), (4.0, 4.0), "wall", west_facing=False, exterior=False, thickness=0.1),
        ),
        columns=(Box2((3.9, 0.0), (4.1, 0.2)),),
        furniture=(Furniture("table", "Table", 0.7, box=(5.0, 1.0, 6.0, 2.0)),),
        anchors=(
            Anchor("sofa", "Sofa", (6.0, 2.0, 0.5)),
            Anchor("speakers", "Speakers", (7.5, 2.0, 1.0), ((7.5, 1.0, 1.0), (7.5, 3.0, 1.0))),
        ),
        ceiling=3.0,
        beams=2.8,
        wall_cut_height=1.0,
        size=(8.0, 4.0),
        location=Location("Test", 10.0, 20.0),
    )
    return replace(home, **changes)


def devices_of(lights: Sequence[DeviceAdapter]) -> DeviceManager:
    """A device manager holding these lights, each at 20 ms."""
    devices = DeviceManager()
    for light in lights:
        devices.add_device(light, LatencyTracker(strategy=StaticLatency(20.0)))
    return devices


async def open_map(
    db: StateDB,
    devices: DeviceManager | Sequence[DeviceAdapter],
    *,
    home: Home | None = None,
    placements: Mapping[str, Placement] | None = None,
    seeded: bool = False,
    now: Callable[[], datetime] = utcnow,
) -> HomeMap:
    """A HomeMap over state.db and these lights, as main wires it but with no seeds. The
    map (if given) and the placements are saved first; seeded marks the first start's
    placing done, so only these placements exist."""
    store = HomeStore(db)
    if home is not None:
        await store.save_home(home)
    for target, placement in (placements or {}).items():
        await store.save_placement(target, placement)
    if seeded:
        await store.mark_placements_seeded({})
    manager = devices if isinstance(devices, DeviceManager) else devices_of(devices)
    home_map = HomeMap(store, manager, seeds=lambda: (), now=now)
    await home_map.load()
    return home_map


def leds_at(
    points: Sequence[Sequence[float]],
    *,
    ceiling: float | None = 3.0,
    anchors: Mapping[str, Sequence[float]] | None = None,
) -> LedSet:
    """One light's LEDs at these map positions, in a zone with this ceiling and anchors."""
    space = Space(
        anchors=MappingProxyType(
            {name: np.asarray(p, dtype=np.float32) for name, p in (anchors or {}).items()}
        ),
        ceiling=ceiling,
    )
    placed = PlacedLeds.from_positions(np.asarray(points, dtype=np.float64).reshape(-1, 3))
    return build_ledset([LedSource("light", len(points), placed=placed)], space)


def seeded_zone_lights() -> list[ZoneLight]:
    """This home's lights where home.json places them. Capabilities follow each light's
    protocol and shape: a LIFX cylinder is a matrix, a LIFX line a multizone strip."""
    rooms = {room.id: index for index, room in enumerate(seed_home().rooms)}
    lights = []
    for seed, entry in zip(seed_lights(), handoff_home_json()["lights"], strict=True):
        kind, protocol = seed.placement.shape.kind, entry["protocol"]
        caps = DeviceCapabilities(
            protocol=protocol,
            model=entry["model"],
            matrix=protocol == "LIFX" and kind == "cylinder",
            multizone=protocol == "LIFX" and kind in ("line", "bent-line"),
        )
        placed = led_positions(seed.placement.shape, seed.leds, seed.placement.led_order)
        room = rooms.get(seed.room, NO_ROOM)
        lights.append(
            ZoneLight(
                seed.id,
                seed.leds,
                caps,
                placed=placed,
                room=room,
                light_id=seed.id,
                name=seed.name,
            )
        )
    return lights


def seeded_space() -> Space:
    return space_of(seed_home())


def seeded_ledset() -> LedSet:
    sources = [
        LedSource(light.device_id, light.led_count, placed=light.placed, room=light.room)
        for light in seeded_zone_lights()
    ]
    return build_ledset(sources, seeded_space())
