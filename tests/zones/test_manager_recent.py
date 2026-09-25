from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
from datetime import timedelta

from conftest import FakeLight
from zone_home import START, FakeHome, Home, HomeFactory, zone_record

from dj_ledfx.zones.model import RecentLookInfo, StoppedLook


def _at(home: Home, minutes: int) -> None:
    home.clock[0] = START + timedelta(minutes=minutes)


def _pairs(recent: Sequence[RecentLookInfo | StoppedLook]) -> list[tuple[str, str]]:
    return [(entry.zone_id, entry.look_id) for entry in recent]


async def test_every_way_a_look_stops_is_remembered_newest_first(make_home: HomeFactory) -> None:
    zones = [
        zone_record("desk", "a"),
        zone_record("shelf", "b"),
        zone_record("both", "a", "b"),
        zone_record("lamp", "c"),
    ]
    home = await make_home([FakeLight("a"), FakeLight("b"), FakeLight("c")], zones)
    manager = home.manager
    breathe, strobe = home.look("classic-breathe"), home.look("classic-strobe")

    await manager.start("desk", breathe)
    _at(home, 1)
    await manager.start("desk", strobe)  # a new look replaces Breathe
    _at(home, 2)
    await manager.start("both", home.look("classic-rainbow-wave"))  # takes desk's only light
    _at(home, 3)
    await manager.off("both")
    _at(home, 4)
    await manager.start("shelf", breathe)
    _at(home, 5)
    await manager.start("lamp", strobe)
    _at(home, 6)
    await manager.stop_all()
    _at(home, 7)
    await manager.start("desk", breathe)
    await manager.start("desk", breathe)  # the same look again: hidden while it runs
    _at(home, 8)
    await manager.off("desk")  # the same zone and look as at 19:00: one entry, the newest stop

    recent = await manager.recent()

    assert _pairs(recent) == [
        ("desk", "classic-breathe"),
        ("lamp", "classic-strobe"),  # Stop all stopped both: the newer start first
        ("shelf", "classic-breathe"),
        ("both", "classic-rainbow-wave"),
        ("desk", "classic-strobe"),
    ]
    assert recent[0] == RecentLookInfo(
        zone_id="desk",
        zone_name="Desk",
        look_id="classic-breathe",
        look_name=breathe.name,
        started_at=START + timedelta(minutes=7),
        stopped_at=START + timedelta(minutes=8),
    )
    restarted = await home.restart()
    assert await restarted.manager.recent() == recent


async def test_the_list_leaves_out_what_one_tap_could_not_start_again(
    make_home: HomeFactory,
) -> None:
    view = FakeHome(rooms={"west": ["a"]}, sub_zones={"desk": ["a"]})
    home = await make_home(
        [FakeLight("a"), FakeLight("b")], [zone_record("shelf", "b")], view=view
    )
    manager = home.manager
    breathe, strobe = home.look("classic-breathe"), home.look("classic-strobe")
    mine = await home.looks.create(
        replace(breathe, name="Mine", built_in=False, derived_from=breathe.id)
    )
    draft = replace(breathe, id="draft", name="Draft", built_in=False)
    runs = [
        ("west", mine),
        ("west", draft),
        ("shelf", strobe),
        ("home", strobe),
        ("west", breathe),
    ]
    for index, (zone_id, look) in enumerate(runs):
        _at(home, 2 * index)
        await manager.start(zone_id, look)
        _at(home, 2 * index + 1)
        await manager.off(zone_id)
    _at(home, 10)
    await manager.start("desk", breathe)
    _at(home, 11)
    view.sub_zones["desk"] = []  # its only light moves out on the map, so the sub-zone stops
    await manager.home_changed()

    assert _pairs(await home.store.load_recent()) == [
        ("desk", "classic-breathe"),
        ("west", "classic-breathe"),
        ("home", "classic-strobe"),
        ("shelf", "classic-strobe"),
        ("west", mine.id),
    ]  # the draft isn't remembered: one tap can't start it
    assert _pairs(await manager.recent()) == [
        ("west", "classic-breathe"),
        ("home", "classic-strobe"),
        ("shelf", "classic-strobe"),
        ("west", mine.id),
    ]  # the desk holds no lights now

    view.sub_zones["desk"] = ["a"]
    await manager.home_changed()
    assert _pairs(await manager.recent())[0] == ("desk", "classic-breathe")

    await home.looks.delete(mine.id)
    await manager.delete_group("shelf")
    del view.sub_zones["desk"]
    await manager.home_changed()
    _at(home, 12)
    await manager.start("home", strobe)

    assert _pairs(await manager.recent()) == [("west", "classic-breathe")]
    # A deleted look's entry is left out when read, never deleted; a deleted zone's goes
    assert _pairs(await home.store.load_recent()) == [
        ("west", "classic-breathe"),
        ("home", "classic-strobe"),
        ("west", mine.id),
    ]


async def test_a_sub_zone_made_again_under_the_same_id_starts_with_no_looks(
    make_home: HomeFactory,
) -> None:
    view = FakeHome(rooms={"west": ["a"]}, sub_zones={"desk": ["a"]})
    home = await make_home([FakeLight("a")], [], view=view)
    await home.manager.start("desk", home.look("classic-breathe"))
    await home.manager.off("desk")

    del view.sub_zones["desk"]
    await home.manager.home_changed()
    view.sub_zones["desk"] = ["a"]  # a new sub-zone that happens to take the same id
    await home.manager.home_changed()

    assert await home.manager.recent() == []


async def test_a_group_deleted_while_its_look_runs_leaves_no_look_to_start_again(
    make_home: HomeFactory,
) -> None:
    home = await make_home([FakeLight("a")], [zone_record("shelf", "a")])
    await home.manager.start("shelf", home.look("classic-breathe"))

    await home.manager.delete_group("shelf")

    assert await home.manager.recent() == []
    assert await home.store.load_recent() == []


async def test_a_running_sub_zone_removed_from_the_map_leaves_no_look_to_start_again(
    make_home: HomeFactory,
) -> None:
    view = FakeHome(rooms={"west": ["a"]}, sub_zones={"desk": ["a"]})
    home = await make_home([FakeLight("a")], [], view=view)
    await home.manager.start("desk", home.look("classic-breathe"))

    del view.sub_zones["desk"]
    await home.manager.home_changed()

    assert await home.manager.recent() == []
    assert await home.store.load_recent() == []
