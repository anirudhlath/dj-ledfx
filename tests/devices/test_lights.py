from __future__ import annotations

from conftest import FakeLight

from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.devices.lights import PC_NAME, LightIndex, LightPart, light_id_of
from dj_ledfx.devices.manager import DeviceManager
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.types import DeviceInfo

SERVER = "openrgb:localhost:6742"


def _part(index: int, name: str, leds: int, *, ghost: bool = False) -> DeviceInfo:
    """One of the PC's devices; a ghost knows only state.db's row, as main registers it."""
    return DeviceInfo(
        name=name,
        device_type="openrgb",
        led_count=leds,
        address="" if ghost else "localhost:6742",
        stable_id=f"{SERVER}:{index}",
        backend="" if ghost else "openrgb",
    )


def _lamp(stable_id: str = "lifx-lamp") -> DeviceInfo:
    return DeviceInfo("Lamp", "lifx", 1, "", stable_id=stable_id, backend="lifx")


def test_the_pcs_devices_are_one_light_with_parts() -> None:
    index = LightIndex.from_infos(
        [_part(0, "Keyboard", 104), _lamp(), _part(1, "RAM", 8), _part(2, "Hub", 0)]
    )

    pc, lamp = index.entries
    assert (pc.id, pc.name, pc.leds, pc.is_pc) == (SERVER, PC_NAME, 112, True)
    assert pc.devices == (f"{SERVER}:0", f"{SERVER}:1", f"{SERVER}:2")
    assert pc.parts == (
        LightPart(f"{SERVER}:0", "Keyboard", 104),
        LightPart(f"{SERVER}:1", "RAM", 8),
    )  # a device with no LEDs is no part
    assert (lamp.id, lamp.devices, lamp.parts, lamp.is_pc) == (
        "lifx-lamp",
        ("lifx-lamp",),
        (),
        False,
    )


def test_parts_follow_the_device_index_and_offline_parts_stay() -> None:
    index = LightIndex.from_infos([_part(10, "Mouse", 2), _part(2, "GPU", 16, ghost=True)])
    [pc] = index.entries
    assert [part.name for part in pc.parts] == ["GPU", "Mouse"]


def test_a_second_openrgb_server_is_a_second_pc() -> None:
    other = DeviceInfo(
        "Strip", "openrgb", 30, "", stable_id="openrgb:other.local:6742:0", backend="openrgb"
    )
    index = LightIndex.from_infos([other, _part(0, "Keyboard", 104)])
    assert [(entry.id, entry.name) for entry in index.entries] == [
        ("openrgb:other.local:6742", "PC 2"),
        (SERVER, "PC"),
    ]


def test_ids_expand_to_devices_and_collapse_to_lights() -> None:
    index = LightIndex.from_infos([_part(0, "Keyboard", 104), _part(1, "RAM", 8), _lamp()])

    assert index.expand([SERVER, "lifx-lamp", f"{SERVER}:1"]) == (
        f"{SERVER}:0",
        f"{SERVER}:1",
        "lifx-lamp",
    )
    assert index.expand(["gone"]) == ("gone",)  # a light no longer known passes through
    assert index.collapse([f"{SERVER}:1", "lifx-lamp", f"{SERVER}:0"]) == (SERVER, "lifx-lamp")
    assert index.light_of(f"{SERVER}:1") == SERVER and index.light_of("gone") == "gone"
    assert index.parts_of(SERVER) == (f"{SERVER}:0", f"{SERVER}:1")
    assert index.parts_of("lifx-lamp") == ("lifx-lamp",) and index.parts_of("gone") == ()
    assert index.get(SERVER) is not None and index.get(f"{SERVER}:0") is None


def test_light_ids() -> None:
    assert light_id_of(_part(3, "Keyboard", 104)) == SERVER
    assert light_id_of(_lamp()) == "lifx-lamp"
    unnamed = DeviceInfo("OpenRGB:0", "openrgb", 4, "", stable_id=None, backend="openrgb")
    assert light_id_of(unnamed) == "OpenRGB:0"  # no stable id: its own light


# M2 review A8: the device manager keeps the index, rebuilt with each change to its devices.
def test_the_device_manager_keeps_the_index() -> None:
    devices = DeviceManager()
    caps = DeviceCapabilities(protocol="OpenRGB")
    assert devices.lights.entries == ()
    for light in (FakeLight(f"{SERVER}:0", caps=caps), FakeLight(f"{SERVER}:1", caps=caps)):
        devices.add_device(light, LatencyTracker(strategy=StaticLatency(5.0)))
    [pc] = devices.lights.entries
    assert pc.id == SERVER and len(pc.parts) == 2
    assert devices.lights is devices.lights  # kept, not rebuilt on every read

    devices.remove_device(f"{SERVER}:1")
    [pc] = devices.lights.entries
    assert pc.devices == (f"{SERVER}:0",)
