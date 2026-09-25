from __future__ import annotations

import struct

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.devices.lights import LightIndex
from dj_ledfx.types import DeviceInfo
from dj_ledfx.web.frames import encode_frame_v1, encode_frame_v2, light_frames

SERVER = "openrgb:localhost:6742"


def _part(index: int, name: str, leds: int) -> DeviceInfo:
    return DeviceInfo(
        name=name,
        device_type="openrgb",
        led_count=leds,
        address="localhost:6742",
        stable_id=f"{SERVER}:{index}",
        backend="openrgb",
    )


def _lamp() -> DeviceInfo:
    return DeviceInfo(
        name="Lamp", device_type="lifx", led_count=1, address="", stable_id="lamp", backend="lifx"
    )


def colours(count: int, value: int) -> NDArray[np.uint8]:
    return np.full((count, 3), value, dtype=np.uint8)


def test_frames_encode_as_v1_and_v2() -> None:
    rgb = colours(2, 9)

    assert encode_frame_v1("lamp", 3, rgb) == b"\x04\x00lamp\x03\x00\x00\x00" + bytes([9] * 6)
    assert encode_frame_v2("preview", "lamp", 3, rgb) == (
        b"\x02\x04\x00lamp\x03\x00\x00\x00" + bytes([9] * 6)
    )
    live = encode_frame_v2("live", "lamp", 2**32 + 1, rgb)
    assert live[:1] == b"\x01" and live[7:11] == struct.pack("<I", 1)  # the sequence wraps
    assert encode_frame_v2("live", "Küche", 1, rgb)[1:3] == struct.pack("<H", 6)  # in bytes


# Review Focus 3: the PC streaming while one of its parts has no frame.
def test_the_pc_frame_always_has_every_part_led() -> None:
    index = LightIndex.from_infos(
        [_part(0, "Keyboard", 3), _part(1, "RAM", 2), _part(2, "Mouse", 1), _lamp()]
    )
    frames = {f"{SERVER}:0": colours(3, 10), f"{SERVER}:2": colours(1, 30), "lamp": colours(1, 99)}

    out = light_frames(index, frames)  # the RAM stick has none: offline, or in no zone

    assert list(out) == [SERVER, "lamp"]
    assert out[SERVER].tolist() == [[10] * 3] * 3 + [[0] * 3] * 2 + [[30] * 3]
    frames[f"{SERVER}:1"] = colours(5, 20)  # back with more LEDs than the PC knows of
    assert light_frames(index, frames)[SERVER].tolist() == (
        [[10] * 3] * 3 + [[20] * 3] * 2 + [[30] * 3]
    )
    frames[f"{SERVER}:0"] = colours(1, 40)  # ...or with fewer
    assert light_frames(index, frames)[SERVER][:3].tolist() == [[40] * 3] + [[0] * 3] * 2
    assert list(light_frames(index, {"lamp": colours(1, 5)})) == ["lamp"]  # no part: no PC
