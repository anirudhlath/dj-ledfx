from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from pathlib import Path

import pytest_asyncio
from conftest import FakeLight
from map_home import tiny_home

from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.devices.manager import DeviceManager
from dj_ledfx.home.map import HomeMap
from dj_ledfx.home.shapes import GridShape, LineShape, Placement, PointShape
from dj_ledfx.home.store import HomeStore
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.persistence.state_db import StateDB
from dj_ledfx.zones.home_view import MapZones

SERVER = "openrgb:localhost:6742"
OPENRGB = DeviceCapabilities(protocol="OpenRGB")
PLACED = {
    "lamp": Placement(PointShape((1.0, 3.5, 1.0)), ""),  # west, in the desk corner
    "spot": Placement(PointShape((2.0, 1.0, 1.0)), ""),  # west
    "rope": Placement(LineShape(((5.0, 1.0, 2.0), (7.0, 1.0, 2.0))), "along-path"),  # east
    "bulb": Placement(PointShape((5.0, 3.0, 1.0)), ""),  # east
}


@pytest_asyncio.fixture
async def db(tmp_path: Path) -> AsyncIterator[StateDB]:
    state_db = StateDB(tmp_path / "state.db")
    await state_db.open()
    yield state_db
    await state_db.close()


async def _zones(
    db: StateDB, lights: Sequence[FakeLight], placements: dict[str, Placement]
) -> tuple[MapZones, HomeMap]:
    store = HomeStore(db)
    await store.save_home(tiny_home())
    for target, placement in placements.items():
        await store.save_placement(target, placement)
    await store.mark_placements_seeded({})  # no first-start guessing: the test places them
    devices = DeviceManager()
    for light in lights:
        devices.add_device(light, LatencyTracker(strategy=StaticLatency(20.0)))
    home_map = HomeMap(store, devices, seeds=lambda: ())
    await home_map.load()
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
    assert zones.room_of("rope") == "east" and zones.room_index() == {"west": 0, "east": 1}


async def test_a_pc_part_is_where_the_pc_is_until_it_is_placed_on_its_own(db: StateDB) -> None:
    pc = [
        FakeLight(f"{SERVER}:0", name="Keyboard", led_count=4, caps=OPENRGB),
        FakeLight(f"{SERVER}:1", name="Mouse", led_count=2, caps=OPENRGB),
    ]
    grid = Placement(GridShape((6.0, 2.0, 0.8), 0.6, 0.0), "rows")
    zones, home_map = await _zones(db, pc, {SERVER: grid})
    assert zones.members("east") == (f"{SERVER}:0", f"{SERVER}:1")

    await home_map.set_placement(f"{SERVER}:1", PointShape((1.0, 1.0, 1.0)))

    assert zones.members("east") == (f"{SERVER}:0",)
    assert zones.members("west") == (f"{SERVER}:1",)
    mouse = zones.placed(f"{SERVER}:1")
    assert mouse is not None and mouse.count == 2
