from __future__ import annotations

import asyncio
import json

from conftest import FakeLight
from zone_home import BREATHE_AND_GLOW, GLOW, TILE, HomeFactory

from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.looks.store import look_body
from dj_ledfx.zones.model import PreviewOnlyChanged, ZoneRecord

LAMP = DeviceCapabilities(protocol="Govee")
CANDLE = DeviceCapabilities(protocol="LIFX", matrix=True, chain=True)
STRIP = DeviceCapabilities(protocol="LIFX", multizone=True, extended_multizone=True)


def _zone(zone_id: str, *lights: str) -> ZoneRecord:
    return ZoneRecord(id=zone_id, name=zone_id.capitalize(), lights=lights)


# Review focus 2: a restart while a zone light is switched off elsewhere.
async def test_resume_never_powers_on_and_switched_off_lights_rejoin(
    make_home: HomeFactory,
) -> None:
    a, b = FakeLight("a"), FakeLight("b")
    home = await make_home([a, b], [_zone("z", "a", "b")])
    await home.manager.start("z", home.look("classic-breathe"))
    a.power = False  # switched off at the wall while the app was down

    home = await home.restart()

    info = home.manager.running_info("z")
    assert info is not None and info.lights == ("a", "b") and info.state == "running"
    assert a.calls == []  # not captured again, not switched on
    assert b.names() == ["prepare_stream"]
    assert "a" not in home.routes.routes and home.routes.routes["b"].zone_id == "z"
    assert home.manager.power_of("a") is False

    a.power = True
    await home.manager.on_power_reading("a", True)  # the light monitor sees it back on

    assert a.names() == ["prepare_stream"]
    assert home.routes.routes["a"].zone_id == "z"
    assert home.host.runtimes["z"].leds.count == 8  # it kept its LEDs while it was off


# Review focus 2 in the production order (B18): resume runs over ghost adapters before any
# light connects, then each light comes online, one event at a time, with its real
# capabilities.
async def test_resume_over_ghosts_then_each_light_online_never_powers_on(
    make_home: HomeFactory,
) -> None:
    a, b, tile = FakeLight("a"), FakeLight("b"), FakeLight("tile", caps=TILE)
    home = await make_home([a, b, tile], [_zone("z", "a", "b", "tile")])
    await home.manager.start("z", BREATHE_AND_GLOW)
    a.power = False  # switched off at the wall while the app was down

    home = await home.restart(ghosts=True)

    info = home.manager.running_info("z")
    assert info is not None and info.lights == ("a", "b", "tile") and info.state == "running"
    assert not any(route.streaming for route in home.routes.routes.values())
    assert home.manager.light_mode("tile") == "streaming"  # its ghost can't say it's a matrix
    for device_id in ("a", "b", "tile"):
        await home.come_online(device_id)

    assert a.calls == []  # not captured again, not switched on
    assert b.names() == ["prepare_stream"]
    assert tile.names() == ["firmware"]  # Glow, once the tile says it's a matrix
    assert home.manager.light_mode("tile") == "own-effect"
    assert home.routes.routes["b"].streaming
    assert "a" not in home.routes.routes or not home.routes.routes["a"].streaming
    assert home.manager.power_of("a") is False

    a.power = True
    await home.manager.on_power_reading("a", True)  # the light monitor sees it back on

    assert a.names() == ["prepare_stream"]
    assert home.routes.routes["a"].streaming
    assert home.host.runtimes["z"].leds.count == 12


async def test_resume_replays_take_overs_oldest_first(make_home: HomeFactory) -> None:
    a, b, c = FakeLight("a"), FakeLight("b"), FakeLight("c")
    home = await make_home([a, b, c], [_zone("left", "a", "b"), _zone("right", "b", "c")])
    await home.manager.start("left", home.look("classic-breathe"))
    home.clock[0] = home.clock[0].replace(minute=5)
    await home.manager.start("right", home.look("classic-strobe"))

    home = await home.restart()

    assert [(x.zone_id, x.lights) for x in home.manager.running()] == [
        ("left", ("a",)),
        ("right", ("b", "c")),
    ]
    assert home.routes.routes["b"].zone_id == "right"
    assert all("capture" not in light.names() for light in (a, b, c))


# Review focus 3: preview-only toggled around a start and an Off.
async def test_preview_only_defers_power_on_and_restore_until_turned_off(
    make_home: HomeFactory,
) -> None:
    lamp = FakeLight("lamp", power=False, captured=b"l0")
    lamp.record_frames = True
    home = await make_home([lamp], [_zone("z", "lamp")], preview_only=True)
    seen: list[bool] = []
    home.bus.subscribe(PreviewOnlyChanged, lambda event: seen.append(event.on))

    await home.manager.start("z", home.look("classic-breathe"))

    assert lamp.calls == []
    route = home.routes.routes["lamp"]
    assert route.ring is home.host.runtimes["z"].ring  # the preview still gets frames
    assert not route.streaming

    await home.manager.set_preview_only(False)

    assert lamp.names() == ["capture", "power", "prepare_stream"]  # no frame came first
    assert home.routes.routes["lamp"].streaming

    await home.manager.set_preview_only(True)
    assert not home.routes.routes["lamp"].streaming
    await home.manager.off("z")
    assert "restore" not in lamp.names()

    await home.manager.set_preview_only(False)
    await home.manager.set_preview_only(True)
    await home.manager.set_preview_only(False)

    assert lamp.calls.count(("restore", b"l0")) == 1
    assert await home.db.load_device_state("lamp") is None
    assert seen == [False, True, False, True, False]


# Review focus 4: a light comes back with a different LED count while its zone runs.
async def test_rejoin_with_new_led_count_rebuilds_routes(make_home: HomeFactory) -> None:
    ghost = FakeLight("candle", led_count=60, connected=False)  # known, not found yet
    lamp = FakeLight("lamp", led_count=3, caps=LAMP)
    home = await make_home([ghost, lamp], [_zone("z", "candle", "lamp")])
    await home.manager.start("z", BREATHE_AND_GLOW)
    runtime = home.host.runtimes["z"]
    assert runtime.leds.count == 63
    assert ghost.calls == []

    candle = FakeLight("candle", led_count=5, caps=CANDLE)
    home.devices.promote_device("candle", candle)
    await home.manager.on_device_online("candle")

    assert home.host.runtimes["z"] is runtime
    assert runtime.leds.count == 8
    candle_route, lamp_route = home.routes.routes["candle"], home.routes.routes["lamp"]
    assert (candle_route.start, candle_route.stop) == (0, 5)
    assert (lamp_route.start, lamp_route.stop) == (5, 8)
    assert candle_route.ring is runtime.ring and lamp_route.ring is runtime.ring
    assert not candle_route.streaming  # the Candle runs Glow itself now
    assert candle.names() == ["capture", "firmware"]  # captured, never switched on
    assert lamp.names() == ["capture", "prepare_stream"]  # from the start; now just a new slice
    runtime.tick(100.0)
    colours = lamp_route.colors_at(100.0, 3)
    assert colours is not None and colours.shape == (3, 3)


# Review focus 5: a saved assignment whose look no longer loads.
async def test_resume_with_broken_look_shows_crashed_and_off_restores(
    make_home: HomeFactory,
) -> None:
    a = FakeLight("a", captured=b"a-before")
    b = FakeLight("b", captured=b"b-before")
    home = await make_home([a, b], [_zone("good", "a"), _zone("bad", "b")])
    await home.manager.start("good", home.look("classic-breathe"))
    await home.manager.start("bad", home.look("classic-strobe"))
    retired = json.loads(look_body(home.look("classic-strobe")))
    retired["layers"][0]["kind"] = "retired_effect"  # an effect this version doesn't have
    await home.db.write(
        "UPDATE zone_assignments SET look=? WHERE zone_id='bad'", (json.dumps(retired),)
    )

    home = await home.restart()

    bad = home.manager.running_info("bad")
    assert bad is not None and bad.state == "crashed"
    assert bad.error is not None and "retired_effect" in bad.error.message
    assert b.calls == []  # a crashed zone leaves its lights alone
    good = home.manager.running_info("good")
    assert good is not None and good.state == "running"
    assert a.names() == ["prepare_stream"]

    await home.manager.off("bad")

    assert b.calls == [("restore", b"b-before")]


async def test_an_unreadable_saved_look_restarts_from_the_look_store(
    make_home: HomeFactory,
) -> None:
    lamp = FakeLight("lamp")
    home = await make_home([lamp], [_zone("z", "lamp")])
    await home.manager.start("z", home.look("classic-breathe"))
    await home.db.write("UPDATE zone_assignments SET look='{not json' WHERE zone_id='z'")

    home = await home.restart()

    info = home.manager.running_info("z")
    assert info is not None and info.state == "crashed" and info.look_name == "Breathe"
    assert info.error is not None and "can't be read" in info.error.message
    assert lamp.calls == [] and "lamp" not in home.routes.routes
    assert "z" not in home.host.runtimes

    info = await home.manager.restart("z")

    assert info.state == "running" and info.error is None
    assert lamp.names() == ["prepare_stream"]
    [saved] = await home.store.load_assignments()
    assert json.loads(saved.look_json)["name"] == "Breathe"


async def test_a_light_switched_off_during_a_look_drops_out_and_rejoins(
    make_home: HomeFactory,
) -> None:
    tile = FakeLight("tile", caps=TILE)
    home = await make_home([tile], [_zone("z", "tile")])
    await home.manager.start("z", GLOW)

    tile.power = False
    await home.manager.on_power_reading("tile", False)
    assert "tile" not in home.routes.routes
    tile.firmware_running = False
    await home.manager.verify_firmware("tile")  # off: nothing is sent
    assert tile.names() == ["capture", "firmware"]

    tile.power = True
    await home.manager.on_power_reading("tile", True)

    assert tile.names() == ["capture", "firmware", "firmware"]
    assert "power" not in tile.names()
    assert not home.routes.routes["tile"].streaming


async def test_a_stopped_firmware_effect_is_sent_again(make_home: HomeFactory) -> None:
    tile = FakeLight("tile", caps=TILE)
    home = await make_home([tile], [_zone("z", "tile")])
    await home.manager.start("z", GLOW)

    await home.manager.verify_firmware("tile")  # still running: nothing to do
    assert tile.names().count("firmware") == 1

    tile.firmware_running = False  # the LIFX app changed it
    await home.manager.verify_firmware("tile")

    assert tile.names().count("firmware") == 2
    assert tile.firmware_running


# B5: asking a light about its effect happens outside the manager's lock.
async def test_checking_a_firmware_effect_holds_up_no_command(make_home: HomeFactory) -> None:
    tile = FakeLight("tile", caps=TILE)
    home = await make_home([tile], [_zone("z", "tile")])
    await home.manager.start("z", GLOW)
    tile.firmware_running = False  # it looks stopped when the check asks
    hold = tile.hold("is_running")
    check = asyncio.create_task(home.manager.verify_firmware("tile"))
    await hold.entered.wait()

    await asyncio.wait_for(home.manager.set_brightness("z", 0.5), timeout=1.0)
    assert tile.names().count("firmware") == 2  # the new brightness went out
    hold.release.set()
    await check

    assert tile.names().count("firmware") == 2  # the stale answer sent nothing more


# E6: a reading that changes nothing doesn't wait for the lock.
async def test_an_unchanged_power_reading_waits_for_nothing(make_home: HomeFactory) -> None:
    lamp, other = FakeLight("lamp"), FakeLight("other")
    home = await make_home([lamp, other], [_zone("z", "lamp"), _zone("y", "other")])
    await home.manager.start("z", home.look("classic-breathe"))
    hold = other.hold("read_light")
    starting = asyncio.create_task(home.manager.start("y", home.look("classic-breathe")))
    await hold.entered.wait()  # the start holds the lock while it reads the light

    await asyncio.wait_for(home.manager.on_power_reading("lamp", True), timeout=1.0)

    hold.release.set()
    await starting


async def test_a_light_that_drops_out_rejoins_with_its_effect(make_home: HomeFactory) -> None:
    tile = FakeLight("tile", caps=TILE)
    home = await make_home([tile], [_zone("z", "tile")])
    await home.manager.start("z", GLOW)
    ring = home.host.runtimes["z"].ring

    home.devices.demote_device("tile")
    await asyncio.sleep(0)  # let the demoted adapter's disconnect run
    await home.manager.on_device_offline("tile")
    await tile.connect()
    home.devices.promote_device("tile", tile)
    await home.manager.on_device_online("tile")

    assert tile.names() == ["capture", "firmware", "firmware"]
    assert home.host.runtimes["z"].ring is ring  # same LEDs: no rebuild


async def test_a_strip_back_online_gets_no_frames_before_it_is_ready(
    make_home: HomeFactory,
) -> None:
    strip = FakeLight("strip", caps=STRIP)
    home = await make_home([strip], [_zone("z", "strip")])
    await home.manager.start("z", home.look("classic-breathe"))
    home.devices.demote_device("strip")
    await asyncio.sleep(0)
    await home.manager.on_device_offline("strip")
    assert not home.routes.routes["strip"].streaming
    await strip.connect()
    home.devices.promote_device("strip", strip)
    strip.calls.clear()
    strip.record_frames = True

    await home.manager.on_device_online("strip")

    assert strip.names() == ["prepare_stream"]  # its own effect stops before any frame
    assert home.routes.routes["strip"].streaming


async def test_off_while_a_light_is_offline_restores_it_when_it_is_back(
    make_home: HomeFactory,
) -> None:
    lamp = FakeLight("lamp", captured=b"l0")
    home = await make_home([lamp], [_zone("z", "lamp")])
    await home.manager.start("z", home.look("classic-breathe"))
    home.devices.demote_device("lamp")
    await asyncio.sleep(0)
    await home.manager.on_device_offline("lamp")

    await home.manager.off("z")

    assert "restore" not in lamp.names()
    assert await home.db.load_device_state("lamp") == b"l0"  # kept until it's back

    await lamp.connect()
    home.devices.promote_device("lamp", lamp)
    await home.manager.on_device_online("lamp")

    assert lamp.calls[-1] == ("restore", b"l0")
    assert await home.db.load_device_state("lamp") is None


async def test_a_new_light_joins_the_newest_all_lights_zone(make_home: HomeFactory) -> None:
    a = FakeLight("a")
    everything = ZoneRecord(id="all", name="Everything", all_lights=True)
    home = await make_home([a], [everything, _zone("desk", "a")])
    await home.manager.start("all", home.look("classic-breathe"))

    new = FakeLight("new", power=False)
    home.devices.add_device(new, LatencyTracker(strategy=StaticLatency(20.0)))
    await home.manager.on_device_discovered("new")

    info = home.manager.running_info("all")
    assert info is not None and info.lights == ("a", "new")
    assert new.names() == ["capture"]  # ready for Off, but left switched off
    assert "new" not in home.routes.routes
    assert home.host.runtimes["all"].leds.count == 8
    [saved] = await home.store.load_assignments()
    assert saved.lights == ("a", "new")


async def test_a_new_light_is_left_alone_when_no_all_lights_zone_runs(
    make_home: HomeFactory,
) -> None:
    a = FakeLight("a")
    home = await make_home([a], [_zone("desk", "a")])
    await home.manager.start("desk", home.look("classic-breathe"))

    new = FakeLight("new")
    home.devices.add_device(new, LatencyTracker(strategy=StaticLatency(20.0)))
    await home.manager.on_device_discovered("new")

    assert new.calls == [] and home.manager.owner_of("new") is None
