from __future__ import annotations

from collections.abc import Sequence

from conftest import KEYBOARD_AND_MOUSE, SERVER, FakeLight, pc_lights
from map_home import DESK_CORNER, open_map, tiny_home

from dj_ledfx.home.map import HomeMap
from dj_ledfx.home.shapes import GridShape, LineShape, Placement, PointShape
from dj_ledfx.persistence.state_db import StateDB
from dj_ledfx.zones.home_view import MapZones

PLACED = {
    "lamp": Placement(PointShape(DESK_CORNER), ""),  # west
    "spot": Placement(PointShape((2.0, 1.0, 1.0)), ""),  # west
    "rope": Placement(LineShape(((5.0, 1.0, 2.0), (7.0, 1.0, 2.0))), "along-path"),  # east
    "bulb": Placement(PointShape((5.0, 3.0, 1.0)), ""),  # east
}


async def _zones(
    db: StateDB, lights: Sequence[FakeLight], placements: dict[str, Placement]
) -> tuple[MapZones, HomeMap]:
    home_map = await open_map(db, lights, home=tiny_home(), placements=placements, seeded=True)
    return MapZones(home_map), home_map


async def test_the_map_gives_the_whole_home_its_rooms_and_sub_zones_as_zones(db: StateDB) -> None:
    zones, _ = await _zones(db, [], {})

    records = [(zone.id, zone.name, zone.kind) for zone in zones.zone_records()]

    assert records == [
        ("home", "Whole home", "home"),
        ("west", "West room", "room"),
        ("east", "East room", "room"),
        ("desk", "Desk", "sub-zone"),
    ]
    assert all(zone.lights == () for zone in zones.zone_records())  # the map says, live


async def test_a_zone_holds_the_lights_placed_in_it_from_west_to_east(db: StateDB) -> None:
    lights = [FakeLight(name) for name in ("rope", "loose", "bulb", "spot", "lamp")]
    zones, _ = await _zones(db, lights, PLACED)

    assert zones.members("west") == ("lamp", "spot")
    assert zones.members("east") == ("bulb", "rope")
    assert zones.members("desk") == ("lamp",)
    assert zones.members("home") == ("lamp", "spot", "bulb", "rope", "loose")  # unplaced last
    assert zones.members("nope") == ()
    assert zones.covers(["rope", "lamp", "loose"]) == ("West room", "East room")
    assert zones.room_of("rope") == "east" and zones.space().rooms == ("west", "east")


async def test_a_pc_part_is_where_the_pc_is_until_it_is_placed_on_its_own(db: StateDB) -> None:
    pc = pc_lights(*KEYBOARD_AND_MOUSE)
    grid = Placement(GridShape((6.0, 2.0, 0.8), 0.6, 0.0), "rows")
    zones, home_map = await _zones(db, pc, {SERVER: grid})
    assert zones.members("east") == (f"{SERVER}:0", f"{SERVER}:1")

    await home_map.set_placement(f"{SERVER}:1", PointShape((1.0, 1.0, 1.0)))

    assert zones.members("east") == (f"{SERVER}:0",)
    assert zones.members("west") == (f"{SERVER}:1",)
    mouse = zones.placed(f"{SERVER}:1")
    assert mouse is not None and mouse.count == 2
