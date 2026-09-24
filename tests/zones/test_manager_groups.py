from __future__ import annotations

import json

import pytest
from conftest import FakeLight
from zone_home import GLOW, HomeFactory

from dj_ledfx.looks.model import LookError, LookNotFoundError
from dj_ledfx.zones.model import (
    ZoneError,
    ZoneNotFoundError,
    ZoneNotRunningError,
    ZoneRecord,
)


def _zone(zone_id: str, *lights: str) -> ZoneRecord:
    return ZoneRecord(id=zone_id, name=zone_id.capitalize(), lights=lights)


async def test_groups_are_created_renamed_and_deleted(make_home: HomeFactory) -> None:
    home = await make_home([FakeLight("a"), FakeLight("b")], [])

    group = await home.manager.create_group(" Desk ", ["b", "a", "b"])

    assert group.id.startswith("group-")
    assert (group.name, group.kind, group.lights) == ("Desk", "group", ("b", "a"))
    assert home.manager.get_zone(group.id) == group
    assert await home.store.load_zones() == [group]

    renamed = await home.manager.update_group(group.id, name="Desk lamps")
    assert (renamed.name, renamed.lights) == ("Desk lamps", ("b", "a"))

    await home.manager.delete_group(group.id)
    assert home.manager.zones() == [] and await home.store.load_zones() == []
    assert len(home.changes) == 3


async def test_bad_groups_are_refused(make_home: HomeFactory) -> None:
    home = await make_home([FakeLight("a")], [])
    with pytest.raises(ZoneError, match="needs a name"):
        await home.manager.create_group("  ", ["a"])
    with pytest.raises(ZoneError, match="at least one light"):
        await home.manager.create_group("Desk", [])
    with pytest.raises(ZoneError, match="Unknown light 'nope'"):
        await home.manager.create_group("Desk", ["a", "nope"])
    with pytest.raises(ZoneNotFoundError):
        await home.manager.update_group("nope", name="X")
    with pytest.raises(ZoneNotFoundError):
        await home.manager.delete_group("nope")
    assert home.manager.zones() == []


async def test_changing_a_running_group_takes_over_and_releases_lights(
    make_home: HomeFactory,
) -> None:
    a, b = FakeLight("a", captured=b"a0"), FakeLight("b")
    c = FakeLight("c", power=False)
    home = await make_home([a, b, c], [_zone("other", "c")])
    group = await home.manager.create_group("Desk", ["a", "b"])
    await home.manager.start("other", home.look("classic-strobe"))
    await home.manager.start(group.id, home.look("classic-breathe"))
    await home.manager.set_brightness(group.id, 0.5)
    home.clock[0] = home.clock[0].replace(minute=30)

    await home.manager.update_group(group.id, lights=["b", "c"])

    info = home.manager.running_info(group.id)
    assert info is not None and info.lights == ("b", "c")
    assert (info.brightness, info.since.minute) == (0.5, 0)  # same look, same start
    assert home.manager.running_info("other") is None  # it had nothing left
    assert ("restore", b"a0") in a.calls and "a" not in home.routes.routes
    assert c.names().count("capture") == 1  # captured once, by the first zone
    assert home.routes.routes["c"].zone_id == group.id
    [saved] = await home.store.load_assignments()
    assert saved.lights == ("b", "c")


async def test_deleting_a_running_group_turns_it_off_first(make_home: HomeFactory) -> None:
    a = FakeLight("a", captured=b"a0")
    home = await make_home([a], [])
    group = await home.manager.create_group("Desk", ["a"])
    await home.manager.start(group.id, home.look("classic-breathe"))

    await home.manager.delete_group(group.id)

    assert a.calls[-1] == ("restore", b"a0")
    assert home.manager.running() == [] and home.host.runtimes == {}
    assert await home.store.load_assignments() == []


async def test_the_effect_deck_starts_and_tunes_a_zones_classic_effect(
    make_home: HomeFactory,
) -> None:
    home = await make_home([FakeLight("a")], [_zone("z", "a")])
    assert home.manager.classic_layer("z") is None

    kind, params = await home.manager.set_classic_effect("z", "breathe", {"min_brightness": 0.1})

    assert kind == "breathe" and params["min_brightness"] == 0.1
    info = home.manager.running_info("z")
    assert info is not None and info.look_id == "classic-breathe"
    runtime = home.host.runtimes["z"]
    effect = runtime.field_effect

    kind, params = await home.manager.set_classic_effect("z", None, {"min_brightness": 0.2})

    assert (kind, params["min_brightness"]) == ("breathe", 0.2)
    assert home.host.runtimes["z"] is runtime and runtime.field_effect is effect  # in place
    [saved] = await home.store.load_assignments()
    settings = json.loads(saved.look_json)["layers"][0]["settings"]
    assert settings["min_brightness"] == {"value": 0.2}

    kind, _ = await home.manager.set_classic_effect("z", "strobe", {})

    assert kind == "strobe" and home.host.runtimes["z"] is not runtime
    strobe = home.host.runtimes["z"].field_effect
    assert strobe is not None
    assert home.manager.classic_layer("z") == ("strobe", strobe.get_params())


async def test_the_effect_deck_refuses_what_it_cannot_play(make_home: HomeFactory) -> None:
    home = await make_home([FakeLight("a")], [_zone("z", "a")])
    with pytest.raises(ZoneNotRunningError):
        await home.manager.set_classic_effect("z", None, {"min_brightness": 0.2})
    with pytest.raises(LookNotFoundError):
        await home.manager.set_classic_effect("z", "nope", {})
    with pytest.raises(LookError, match="min_brightness"):
        await home.manager.set_classic_effect("z", "breathe", {"min_brightness": 0.9})
    with pytest.raises(ZoneNotFoundError):
        await home.manager.set_classic_effect("nope", "breathe", {})
    assert home.manager.running() == []

    await home.manager.start("z", GLOW)
    assert home.manager.classic_layer("z") is None  # a firmware look has no classic effect
