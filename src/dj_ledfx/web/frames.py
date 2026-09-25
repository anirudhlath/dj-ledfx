"""The web app's binary frames (web spec §12.4).

v1, the old UI's, by device id: [2B name_len LE][name UTF-8][4B seq LE][RGB × leds].
v2, by light id: [1B stream: 0x01 live | 0x02 preview][2B id_len LE][id UTF-8][4B seq LE]
[RGB × leds]. The PC is one light: its frame is every part's LEDs in part order, black
where a part has none (Review Focus 3).
"""

from __future__ import annotations

import struct
from collections.abc import Mapping
from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

if TYPE_CHECKING:
    from dj_ledfx.devices.lights import LightIndex

STREAM_BYTES: Mapping[str, int] = {"live": 0x01, "preview": 0x02}  # zones.frames.STREAMS
_SEQ_MASK = 0xFFFFFFFF


def encode_frame_v1(device_id: str, seq: int, colors: NDArray[np.uint8]) -> bytes:
    name = device_id.encode("utf-8")
    header = struct.pack("<H", len(name)) + name + struct.pack("<I", seq & _SEQ_MASK)
    return header + colors.tobytes()


def encode_frame_v2(stream: str, light_id: str, seq: int, colors: NDArray[np.uint8]) -> bytes:
    """stream is "live" or "preview"."""
    ident = light_id.encode("utf-8")
    head = struct.pack("<BH", STREAM_BYTES[stream], len(ident))
    return head + ident + struct.pack("<I", seq & _SEQ_MASK) + colors.tobytes()


def light_frames(
    index: LightIndex, device_frames: Mapping[str, NDArray[np.uint8]]
) -> dict[str, NDArray[np.uint8]]:
    """Each light's frame from its devices' frames, in the index's order. A light none of
    whose devices has a frame is left out."""
    out: dict[str, NDArray[np.uint8]] = {}
    for entry in index.entries:
        if not any(device in device_frames for device in entry.devices):
            continue
        frame = np.zeros((entry.leds, 3), dtype=np.uint8)
        for part, start, stop in entry.part_slices():
            colors = device_frames.get(part.id)
            if colors is not None:
                count = min(stop - start, colors.shape[0])
                frame[start : start + count] = colors[:count]
        out[entry.id] = frame
    return out
