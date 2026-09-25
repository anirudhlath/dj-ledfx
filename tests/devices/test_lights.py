from __future__ import annotations

from conftest import OPENRGB, SERVER, FakeLight, lamp_info, pc_part_info

from dj_ledfx.devices.lights import PC_NAME, LightIndex, LightPart, light_id_of
from dj_ledfx.devices.manager import DeviceManager
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.types import DeviceInfo


def test_the_pcs_devices_are_one_light_with_parts() -> None:
    index = LightIndex.from_infos(
        [
            pc_part_info(0, "Keyboard", 104),
            lamp_info(),
            pc_part_info(1, "RAM", 8),
            pc_part_info(2, "Hub", 0),
        ]
    )

    pc, lamp = index.entries
    assert (pc.id, pc.name, pc.leds, pc.is_pc) == (SERVER, PC_NAME, 112, True)
    assert pc.devices == (f"{SERVER}:0", f"{SERVER}:1", f"{SERVER}:2")
    assert pc.parts == (
        LightPart(f"{SERVER}:0", "Keyboard", 104),
        LightPart(f"{SERVER}:1", "RAM", 8),
    )  # a device with no LEDs is no part
    assert (lamp.id, lamp.devices, lamp.parts, lamp.is_pc) == (
        "lamp",
        ("lamp",),
        (LightPart("lamp", "Lamp", 1),),  # a plain light is one part: itself
        False,
    )
    assert [(part.id, start, stop) for part, start, stop in pc.part_slices()] == [
        (f"{SERVER}:0", 0, 104),
        (f"{SERVER}:1", 104, 112),
    ]


def test_parts_follow_the_device_index_and_offline_parts_stay() -> None:
    index = LightIndex.from_infos(
        [pc_part_info(10, "Mouse", 2), pc_part_info(2, "GPU", 16, ghost=True)]
    )
    [pc] = index.entries
    assert [part.name for part in pc.parts] == ["GPU", "Mouse"]


def test_a_second_openrgb_server_is_a_second_pc() -> None:
    other = DeviceInfo(
        "Strip", "openrgb", 30, "", stable_id="openrgb:other.local:6742:0", backend="openrgb"
    )
    index = LightIndex.from_infos([other, pc_part_info(0, "Keyboard", 104)])
    assert [(entry.id, entry.name) for entry in index.entries] == [
        ("openrgb:other.local:6742", "PC 2"),
        (SERVER, "PC"),
    ]


def test_ids_expand_to_devices_and_collapse_to_lights() -> None:
    index = LightIndex.from_infos(
        [pc_part_info(0, "Keyboard", 104), pc_part_info(1, "RAM", 8), lamp_info()]
    )

    assert index.expand([SERVER, "lamp", f"{SERVER}:1"]) == (
        f"{SERVER}:0",
        f"{SERVER}:1",
        "lamp",
    )
    assert index.expand(["gone"]) == ("gone",)  # a light no longer known passes through
    assert index.collapse([f"{SERVER}:1", "lamp", f"{SERVER}:0"]) == (SERVER, "lamp")
    assert index.light_of(f"{SERVER}:1") == SERVER and index.light_of("gone") == "gone"
    assert index.parts_of(SERVER) == (f"{SERVER}:0", f"{SERVER}:1")
    assert index.parts_of("lamp") == ("lamp",) and index.parts_of("gone") == ()
    assert index.get(SERVER) is not None and index.get(f"{SERVER}:0") is None


def test_light_ids() -> None:
    assert light_id_of(pc_part_info(3, "Keyboard", 104)) == SERVER
    assert light_id_of(lamp_info()) == "lamp"
    unnamed = DeviceInfo("OpenRGB:0", "openrgb", 4, "", stable_id=None, backend="openrgb")
    assert light_id_of(unnamed) == "OpenRGB:0"  # no stable id: its own light


# M2 review A8: the device manager keeps the index, rebuilt with each change to its devices.
def test_the_device_manager_keeps_the_index() -> None:
    devices = DeviceManager()
    assert devices.lights.entries == ()
    for light in (FakeLight(f"{SERVER}:0", caps=OPENRGB), FakeLight(f"{SERVER}:1", caps=OPENRGB)):
        devices.add_device(light, LatencyTracker(strategy=StaticLatency(5.0)))
    [pc] = devices.lights.entries
    assert pc.id == SERVER and len(pc.parts) == 2
    assert devices.lights is devices.lights  # kept, not rebuilt on every read

    devices.remove_device(f"{SERVER}:1")
    [pc] = devices.lights.entries
    assert pc.devices == (f"{SERVER}:0",)
