from __future__ import annotations

import numpy as np
import pytest
from conftest import FakeLight
from zone_home import FakeHome, HomeFactory, zone_record

from dj_ledfx.effects.ledset import PlacedLeds, Space
from dj_ledfx.home.map import RESERVED_ZONE_IDS
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.zones.model import ALL_LIGHTS_ZONE_ID, HOME_ZONE_ID, ZoneError, ZoneNotFoundError


def _lights(*ids: str) -> list[FakeLight]:
    return [FakeLight(light_id, captured=f"{light_id}0".encode()) for light_id in ids]


def test_the_map_reserves_the_whole_home_and_all_lights_ids() -> None:
    assert RESERVED_ZONE_IDS == {HOME_ZONE_ID, ALL_LIGHTS_ZONE_ID}


async def test_the_whole_home_its_rooms_and_sub_zones_are_zones(make_home: HomeFactory) -> None:
    view = FakeHome(
        rooms={"west": ["a"], "east": ["b", "c"], "attic": []}, sub_zones={"desk": ["a"]}
    )
    home = await make_home(_lights("a", "b", "c"), [zone_record("shelf", "b")], view=view)

    zones = [(zone.id, zone.kind, zone.lights) for zone in home.manager.zones()]

    assert zones == [
        ("home", "home", ("a", "b", "c")),
        ("west", "room", ("a",)),
        ("east", "room", ("b", "c")),
        ("desk", "sub-zone", ("a",)),
        ("shelf", "group", ("b",)),
    ]  # the attic has no lights, so the zone picker doesn't offer it
    assert home.manager.get_zone("attic").lights == ()
    stored = {zone.id: zone.kind for zone in await home.store.load_zones()}
    assert stored == {
        "shelf": "group",
        "home": "home",
        "west": "room",
        "east": "room",
        "attic": "room",
        "desk": "sub-zone",
    }
    with pytest.raises(ZoneError, match="isn't a group"):
        await home.manager.update_group("west", name="Den")
    with pytest.raises(ZoneError, match="has no lights"):
        await home.manager.start("attic", home.look("classic-breathe"))


async def test_a_room_runs_on_its_lights_and_says_which_rooms_a_zone_covers(
    make_home: HomeFactory,
) -> None:
    view = FakeHome(rooms={"west": ["a"], "east": ["b", "c"]})
    home = await make_home(_lights("a", "b", "c"), [], view=view)

    await home.manager.start(HOME_ZONE_ID, home.look("classic-breathe"))
    home.clock[0] = home.clock[0].replace(minute=5)
    await home.manager.start("east", home.look("classic-strobe"))

    whole, east = home.manager.running_info(HOME_ZONE_ID), home.manager.running_info("east")
    assert whole is not None and (whole.lights, whole.covers) == (("a",), ("West",))
    assert east is not None and (east.lights, east.covers) == (("b", "c"), ("East",))


# Review Focus 2: a light moved on the map into, or out of, a running room.
async def test_moving_a_light_into_a_running_room_takes_it_over_but_keeps_newer_takeovers(
    make_home: HomeFactory,
) -> None:
    view = FakeHome(rooms={"west": ["a", "b"], "east": ["c", "d", "e"]})
    lights = _lights("a", "b", "c", "d", "e")
    home = await make_home(lights, [zone_record("shelf", "d")], view=view)
    manager = home.manager
    await manager.start(HOME_ZONE_ID, home.look("classic-breathe"))
    home.clock[0] = home.clock[0].replace(minute=5)
    await manager.start("west", home.look("classic-strobe"))
    home.clock[0] = home.clock[0].replace(minute=10)
    await manager.start("shelf", home.look("classic-rainbow-wave"))

    view.rooms = {"west": ["a", "b", "c", "d"], "east": ["e"]}
    await manager.home_changed()

    owned = {info.zone_id: info.lights for info in manager.running()}
    assert owned == {HOME_ZONE_ID: ("e",), "west": ("a", "b", "c"), "shelf": ("d",)}
    west = home.host.runtimes["west"]
    assert west.leds.count == 12
    assert all(home.routes.routes[light].ring is west.ring for light in ("a", "b", "c"))
    assert home.lights["c"].names().count("capture") == 1  # it changed zones, never released
    assert "restore" not in home.lights["c"].names()

    view.rooms = {"west": ["a", "c", "d"], "east": ["b", "e"]}
    await manager.home_changed()

    owned = {info.zone_id: info.lights for info in manager.running()}
    assert owned == {HOME_ZONE_ID: ("e",), "west": ("a", "c"), "shelf": ("d",)}
    assert ("restore", b"b0") in home.lights["b"].calls and "b" not in home.routes.routes
    assert manager.owner_of("b") is None  # the whole home had lost it to west: not back
    saved = {a.zone_id: a.lights for a in await home.store.load_assignments()}
    assert saved == owned


# Review Focus 4: a sub-zone deleted while a look runs on it.
async def test_deleting_a_running_sub_zone_turns_it_off_and_restores_its_lights(
    make_home: HomeFactory,
) -> None:
    view = FakeHome(rooms={"west": ["a", "b"]}, sub_zones={"desk": ["a"]})
    home = await make_home(_lights("a", "b"), [], view=view)
    await home.manager.start("desk", home.look("classic-breathe"))
    heard = len(home.changes)

    del view.sub_zones["desk"]
    await home.manager.home_changed()

    assert home.manager.running() == [] and "desk" not in home.host.runtimes
    assert ("restore", b"a0") in home.lights["a"].calls and "a" not in home.routes.routes
    assert await home.db.load_device_state("a") is None  # released, so its capture is gone
    assert await home.store.load_assignments() == []
    assert "desk" not in {zone.id for zone in await home.store.load_zones()}
    with pytest.raises(ZoneNotFoundError):
        home.manager.get_zone("desk")
    assert len(home.changes) == heard + 1


async def test_a_running_room_redraws_its_leds_when_a_light_moves_inside_it(
    make_home: HomeFactory,
) -> None:
    here = PlacedLeds.from_positions(np.array([[1.0, 1.0, 1.0]] * 4))
    there = PlacedLeds.from_positions(np.array([[3.0, 2.0, 1.0]] * 4))
    view = FakeHome(rooms={"west": ["a", "b"]}, placed_at={"a": here})
    home = await make_home(_lights("a", "b"), [], view=view)
    await home.manager.start("west", home.look("classic-breathe"))
    runtime = home.host.runtimes["west"]
    assert np.allclose(runtime.leds.pos[:4], here.pos)

    view.placed_at["a"] = there
    view.space_now = Space(rooms=("west",), ceiling=2.5)
    await home.manager.home_changed()

    assert home.host.runtimes["west"] is runtime  # the same look, redrawn
    assert np.allclose(runtime.leds.pos[:4], there.pos) and runtime.space.ceiling == 2.5
    assert runtime.leds.room.tolist() == [0] * 8
    assert all(home.routes.routes[light].ring is runtime.ring for light in ("a", "b"))


async def test_a_room_resumes_but_one_gone_from_the_map_meanwhile_does_not(
    make_home: HomeFactory,
) -> None:
    view = FakeHome(rooms={"west": ["a"], "east": ["b"]})
    home = await make_home(_lights("a", "b"), [], view=view)
    await home.manager.start("west", home.look("classic-breathe"))
    await home.manager.start("east", home.look("classic-strobe"))

    del view.rooms["east"]
    again = await home.restart()

    assert [info.zone_id for info in again.manager.running()] == ["west"]
    assert "east" not in {zone.id for zone in await again.store.load_zones()}
    assert ("restore", b"b0") in again.lights["b"].calls


async def test_a_light_found_later_joins_a_running_whole_home(make_home: HomeFactory) -> None:
    view = FakeHome(rooms={"west": ["a"]})
    home = await make_home(_lights("a"), [], view=view)
    await home.manager.start(HOME_ZONE_ID, home.look("classic-breathe"))

    new = FakeLight("new", power=False)
    home.devices.add_device(new, LatencyTracker(strategy=StaticLatency(20.0)))
    view.unplaced.append("new")
    await home.manager.on_device_discovered("new")

    info = home.manager.running_info(HOME_ZONE_ID)
    assert info is not None and info.lights == ("a", "new")
