from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pytest
import pytest_asyncio
from conftest import FakeLight
from map_home import tiny_home

from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.devices.manager import DeviceManager
from dj_ledfx.home.map import HomeMap
from dj_ledfx.home.model import Home, HomeError, HomeNotFoundError
from dj_ledfx.home.shapes import GridShape, LineShape, Placement, PointShape, ShapeError
from dj_ledfx.home.store import HomeStore
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.persistence.state_db import StateDB

NOW = datetime(2026, 9, 24, 19, 0, tzinfo=UTC)
SERVER = "openrgb:localhost:6742"
OPENRGB = DeviceCapabilities(protocol="OpenRGB")
DESK_LAMP = Placement(PointShape((1.0, 3.5, 1.0)), "")  # in tiny_home's desk corner
ROPE = Placement(LineShape(((5.0, 1.0, 2.0), (7.0, 1.0, 2.0))), "along-path")


@pytest_asyncio.fixture
async def db(tmp_path: Path) -> AsyncIterator[StateDB]:
    state_db = StateDB(tmp_path / "state.db")
    await state_db.open()
    yield state_db
    await state_db.close()


async def _map(
    db: StateDB,
    lights: Sequence[FakeLight],
    *,
    home: Home | None = None,
    placements: dict[str, Placement] | None = None,
) -> HomeMap:
    store = HomeStore(db)
    await store.save_home(home or tiny_home())
    for target, placement in (placements or {}).items():
        await store.save_placement(target, placement)
    devices = DeviceManager()
    for light in lights:
        devices.add_device(light, LatencyTracker(strategy=StaticLatency(20.0)))
    home_map = HomeMap(store, devices, seeds=lambda: (), now=lambda: NOW)
    await home_map.load()
    return home_map


def _pc() -> list[FakeLight]:
    return [
        FakeLight(f"{SERVER}:0", name="Keyboard", led_count=4, caps=OPENRGB),
        FakeLight(f"{SERVER}:1", name="Mouse", led_count=2, caps=OPENRGB),
    ]


async def test_the_first_start_with_lights_places_each_of_them_once(db: StateDB) -> None:
    empty = await _map(db, [])
    assert empty.placements == {}
    assert not await HomeStore(db).placements_seeded()  # no lights yet: wait for them

    first = await _map(db, [FakeLight("lamp-1"), FakeLight("lamp-2")])
    assert set(first.placements) == {"lamp-1", "lamp-2"}
    assert not any(placement.confirmed for placement in first.placements.values())

    later = await _map(db, [FakeLight("lamp-1"), FakeLight("lamp-2"), FakeLight("lamp-3")])
    assert later.placement("lamp-3") is None  # seeded once; a new light waits for a guess


async def test_rooms_and_sub_zones_come_from_where_a_light_sits(db: StateDB) -> None:
    home_map = await _map(
        db, [FakeLight("lamp"), FakeLight("rope")], placements={"lamp": DESK_LAMP, "rope": ROPE}
    )
    assert (home_map.room_of("lamp"), home_map.sub_zone_of("lamp")) == ("west", "desk")
    assert (home_map.room_of("rope"), home_map.sub_zone_of("rope")) == ("east", None)
    assert home_map.room_at(20.0, 20.0) is None and home_map.room_of("unknown") is None
    assert home_map.room_index() == {"west": 0, "east": 1}
    placed = home_map.placed("rope")
    assert placed is not None and placed.count == 4 and np.allclose(placed.pos[:, 2], 2.0)


async def test_a_light_is_placed_moved_confirmed_and_removed(db: StateDB) -> None:
    home_map = await _map(db, [FakeLight("lamp")], placements={"lamp": DESK_LAMP})

    moved = await home_map.set_placement("lamp", LineShape(((0, 0, 1), (1, 0, 1))))
    assert (moved.led_order, moved.confirmed) == ("along-path", False)  # moving doesn't confirm
    confirmed = await home_map.confirm("lamp")
    assert (confirmed.confirmed, confirmed.confirmed_at) == (True, NOW)
    again = await home_map.set_placement("lamp", LineShape(((0, 0, 1), (2, 0, 1))))
    assert again.confirmed and again.led_order == "along-path"
    await home_map.remove_placement("lamp")
    assert home_map.placement("lamp") is None
    assert await HomeStore(db).load_placements() == {}

    with pytest.raises(HomeNotFoundError):
        await home_map.set_placement("nope", PointShape((0, 0, 0)))
    with pytest.raises(ShapeError, match="rows, columns"):
        await home_map.set_placement("lamp", GridShape((0, 0, 0), 1, 1), "along-path")
    with pytest.raises(HomeNotFoundError):
        await home_map.confirm("lamp")  # removed: nothing to confirm


async def test_pc_parts_share_the_pc_placement_until_placed_on_their_own(db: StateDB) -> None:
    grid = Placement(GridShape((6.0, 2.0, 0.8), 0.6, 0.0), "rows")  # 6 LEDs in one row
    home_map = await _map(db, _pc(), placements={SERVER: grid})

    keyboard, mouse = home_map.placed(f"{SERVER}:0"), home_map.placed(f"{SERVER}:1")
    assert keyboard is not None and mouse is not None
    assert np.allclose(keyboard.pos[:, 0], [5.75, 5.85, 5.95, 6.05])
    assert np.allclose(mouse.pos[:, 0], [6.15, 6.25])
    assert home_map.room_of(f"{SERVER}:1") == "east"  # the PC's room

    await home_map.set_placement(f"{SERVER}:1", PointShape((1.0, 1.0, 1.0)))

    mouse = home_map.placed(f"{SERVER}:1")
    assert mouse is not None and np.allclose(mouse.pos[:, :2], [1.0, 1.0])
    assert (home_map.room_of(f"{SERVER}:1"), home_map.room_of(SERVER)) == ("west", "east")


async def test_the_space_has_the_anchors_rooms_ceiling_and_centre(db: StateDB) -> None:
    space = (await _map(db, [])).space()
    assert np.allclose(space.anchors["sofa"], [6.0, 2.0, 0.5])
    assert space.anchor_points["speakers"].shape == (2, 3)
    assert space.anchor_points["sofa"].shape == (1, 3)
    assert (space.rooms, space.ceiling, space.centre) == (("west", "east"), 3.0, (4.0, 2.0, 1.0))


async def test_anchors_are_added_changed_and_deleted(db: StateDB) -> None:
    home_map = await _map(db, [])

    chair = await home_map.add_anchor("Reading chair", (1.0, 1.0, 0.5))
    twin = await home_map.add_anchor("Reading chair", (2.0, 1.0, 0.5))
    assert (chair.id, twin.id, chair.confirmed) == ("reading-chair", "reading-chair-2", False)
    moved = await home_map.update_anchor("reading-chair", position=(1.5, 1.0, 0.5), confirmed=True)
    assert moved.position == (1.5, 1.0, 0.5) and moved.confirmed
    await home_map.delete_anchor("reading-chair-2")

    reloaded = HomeMap(HomeStore(db), DeviceManager(), seeds=lambda: ())
    await reloaded.load()
    assert [anchor.id for anchor in reloaded.home.anchors][-1] == "reading-chair"
    with pytest.raises(HomeNotFoundError):
        await home_map.update_anchor("nope", name="x")
    with pytest.raises(HomeError, match="finite"):
        await home_map.add_anchor("Bad", (float("nan"), 0.0, 0.0))


async def test_sub_zones_are_added_changed_and_deleted(db: StateDB) -> None:
    home_map = await _map(db, [])
    nook = ((5.0, 0.0), (6.0, 0.0), (6.0, 1.0), (5.0, 1.0))

    added = await home_map.add_sub_zone("Reading nook", "east", nook)
    clash = await home_map.add_sub_zone("Home", "east", nook)
    assert (added.id, added.room, clash.id) == ("reading-nook", "east", "home-2")
    changed = await home_map.update_sub_zone("reading-nook", name="Nook", room="west")
    assert (changed.name, changed.room) == ("Nook", "west")
    await home_map.delete_sub_zone("home-2")
    assert [sub.id for sub in home_map.home.sub_zones] == ["desk", "reading-nook"]

    with pytest.raises(HomeError, match="unknown room"):
        await home_map.add_sub_zone("Attic", "attic", nook)
    with pytest.raises(HomeNotFoundError):
        await home_map.delete_sub_zone("nope")


async def test_the_map_settings_are_changed_and_checked(db: StateDB) -> None:
    home_map = await _map(db, [])

    home = await home_map.update({"ceiling": 2.7, "northOffsetDeg": 12})

    assert (home.ceiling, home.north_offset_deg, home_map.space().ceiling) == (2.7, 12.0, 2.7)
    with pytest.raises(HomeError, match="can't be changed here"):
        await home_map.update({"rooms": []})
    with pytest.raises(HomeError, match="greater than 0"):
        await home_map.update({"ceiling": -1})
    assert home_map.home.ceiling == 2.7


async def test_listeners_hear_each_change_and_a_failing_one_is_only_logged(db: StateDB) -> None:
    home_map = await _map(db, [FakeLight("lamp")], placements={"lamp": DESK_LAMP})
    heard: list[str] = []

    async def listener() -> None:
        heard.append(str(home_map.room_of("lamp")))

    async def broken() -> None:
        raise RuntimeError("boom")

    home_map.on_change(broken)
    home_map.on_change(listener)

    await home_map.set_placement("lamp", PointShape((6.0, 2.0, 1.0)))
    await home_map.update({"beams": 2.5})

    assert heard == ["east", "east"]  # each listener sees the new map


async def test_a_guess_places_only_unplaced_lights(db: StateDB) -> None:
    home_map = await _map(db, [FakeLight("lamp")], placements={"lamp": DESK_LAMP})
    await home_map.confirm("lamp")

    assert await home_map.guess() == {}  # everything placed
    assert home_map.placement("lamp") is not None and home_map.placement("lamp").confirmed  # type: ignore[union-attr]

    await home_map.remove_placement("lamp")
    guesses = await home_map.guess()
    assert list(guesses) == ["lamp"] and not guesses["lamp"].confirmed
