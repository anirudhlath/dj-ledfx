from __future__ import annotations

import base64
from typing import Any

import numpy as np
from numpy.typing import NDArray


def build_scan_message() -> dict[str, Any]:
    return {"msg": {"cmd": "scan", "data": {"account_topic": "reserve"}}}


def build_turn_message(on: bool) -> dict[str, Any]:
    return {"msg": {"cmd": "turn", "data": {"value": 1 if on else 0}}}


def build_brightness_message(value: int) -> dict[str, Any]:
    clamped = max(1, min(100, value))
    return {"msg": {"cmd": "brightness", "data": {"value": clamped}}}


def build_solid_color_message(r: int, g: int, b: int, kelvin: int = 0) -> dict[str, Any]:
    """A colour, or with `kelvin` a white at that colour temperature (the colour is ignored)."""
    return {
        "msg": {
            "cmd": "colorwc",
            "data": {"color": {"r": r, "g": g, "b": b}, "colorTemInKelvin": kelvin},
        }
    }


def build_status_query() -> dict[str, Any]:
    return {"msg": {"cmd": "devStatus", "data": {}}}


def xor_checksum(data: bytes) -> int:
    result = 0
    for b in data:
        result ^= b
    return result


# Razer (DreamView) packets, as LedFx 2.1.9's Govee driver sends them to UDP 4003: a frame
# is the header, the segment count, an RGB triple per segment and an XOR checksum; the
# switch is its four bytes, 1 or 0, and the checksum. Razer frames get no replies.
RAZER_HEADER = bytes((0xBB, 0x00, 0xFA, 0xB0, 0x00))
RAZER_SWITCH = bytes((0xBB, 0x00, 0x01, 0xB1))
MAX_RAZER_SEGMENTS = 255  # the count is one byte


def _razer(packet: bytes) -> dict[str, Any]:
    """A razer message: the packet and its XOR checksum, in base64."""
    framed = packet + bytes((xor_checksum(packet),))
    return {"msg": {"cmd": "razer", "data": {"pt": base64.b64encode(framed).decode("ascii")}}}


def build_razer_switch(on: bool) -> dict[str, Any]:
    """Switch the lamp's razer mode on (it takes razer frames) or off (its own modes)."""
    return _razer(RAZER_SWITCH + bytes((1 if on else 0,)))


def build_razer_frame(colors: NDArray[np.uint8]) -> dict[str, Any]:
    """One razer frame: a colour for each of the lamp's segments, in segment order."""
    count = len(colors)
    if not 0 < count <= MAX_RAZER_SEGMENTS:
        raise ValueError(f"A razer frame takes 1 to {MAX_RAZER_SEGMENTS} segments, not {count}")
    rgb = np.ascontiguousarray(colors, dtype=np.uint8).tobytes()
    return _razer(RAZER_HEADER + bytes((count,)) + rgb)
