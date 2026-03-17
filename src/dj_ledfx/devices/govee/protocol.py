from __future__ import annotations

import base64
from collections.abc import Sequence
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


def build_solid_color_message(r: int, g: int, b: int) -> dict[str, Any]:
    return {
        "msg": {
            "cmd": "colorwc",
            "data": {"color": {"r": r, "g": g, "b": b}, "colorTemInKelvin": 0},
        }
    }


def build_status_query() -> dict[str, Any]:
    return {"msg": {"cmd": "devStatus", "data": {}}}


def xor_checksum(data: bytes) -> int:
    result = 0
    for b in data:
        result ^= b
    return result


def build_ble_packet(command_type: int, sub_command: int, payload: bytes) -> bytes:
    buf = bytearray(20)
    buf[0] = 0x33
    buf[1] = command_type
    buf[2] = sub_command
    end = min(3 + len(payload), 19)
    buf[3:end] = payload[: end - 3]
    buf[19] = xor_checksum(bytes(buf[:19]))
    return bytes(buf)


def encode_segment_mask(segment_indices: Sequence[int], total_segments: int = 15) -> bytes:
    left = 0
    right = 0
    for idx in segment_indices:
        if 0 <= idx < 8:
            left |= 1 << idx
        elif 8 <= idx < total_segments:
            right |= 1 << (idx - 8)
    return bytes([left, right])


def build_segment_color_packet(r: int, g: int, b: int, segment_mask: bytes) -> bytes:
    payload = bytes([r, g, b, 0x00, 0x00]) + segment_mask
    return build_ble_packet(0x05, 0x0B, payload)


def build_pt_real_message(ble_packets: Sequence[bytes]) -> dict[str, Any]:
    encoded = [base64.b64encode(pkt).decode("ascii") for pkt in ble_packets]
    return {"msg": {"cmd": "ptReal", "data": {"command": encoded}}}


def map_colors_to_segments(
    colors: NDArray[np.uint8], num_segments: int
) -> list[tuple[int, int, int]]:
    n_leds = len(colors)
    result: list[tuple[int, int, int]] = []
    for seg in range(num_segments):
        start = seg * n_leds / num_segments
        end = (seg + 1) * n_leds / num_segments
        i_start = int(start)
        i_end = max(i_start + 1, int(end))
        segment_slice = colors[i_start:i_end]
        avg = segment_slice.mean(axis=0).astype(np.uint8)
        result.append((int(avg[0]), int(avg[1]), int(avg[2])))
    return result
