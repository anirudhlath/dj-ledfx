from __future__ import annotations

import struct
from dataclasses import dataclass

from loguru import logger

from dj_ledfx.prodjlink.constants import (
    BEAT_PACKET_LEN,
    CAPABILITY_CDJ3000,
    MAGIC_HEADER,
    OFFSET_BEAT_NUMBER,
    OFFSET_BPM,
    OFFSET_CAPABILITY,
    OFFSET_DEVICE_NAME,
    OFFSET_DEVICE_NUMBER,
    OFFSET_NEXT_BEAT_MS,
    OFFSET_PACKET_TYPE,
    OFFSET_PITCH,
    PACKET_TYPE_BEAT,
    PITCH_CENTER,
    PITCH_SCALE,
)


@dataclass(frozen=True, slots=True)
class BeatPacket:
    device_name: str
    device_number: int
    bpm: float  # raw BPM from packet (not pitch-adjusted)
    pitch_percent: float  # pitch adjustment as percentage (-100 to +100)
    beat_number: int  # 1-4 within bar
    next_beat_ms: int  # ms until next beat

    @property
    def pitch_adjusted_bpm(self) -> float:
        return self.bpm * (1.0 + self.pitch_percent / 100.0)


def parse_beat_packet(data: bytes) -> BeatPacket | None:
    if len(data) < BEAT_PACKET_LEN:
        return None

    if data[: len(MAGIC_HEADER)] != MAGIC_HEADER:
        return None

    if data[OFFSET_PACKET_TYPE] != PACKET_TYPE_BEAT:
        return None

    capability = data[OFFSET_CAPABILITY]
    if capability != CAPABILITY_CDJ3000:
        logger.debug(
            "Ignoring packet from non-CDJ3000 hardware (capability=0x{:02X})", capability
        )
        return None

    device_name = (
        data[OFFSET_DEVICE_NAME : OFFSET_DEVICE_NAME + 20]
        .split(b"\x00")[0]
        .decode("ascii", errors="replace")
    )
    device_number = data[OFFSET_DEVICE_NUMBER]
    (next_beat_ms,) = struct.unpack_from(">I", data, OFFSET_NEXT_BEAT_MS)
    (pitch_raw,) = struct.unpack_from(">I", data, OFFSET_PITCH)
    (bpm_raw,) = struct.unpack_from(">H", data, OFFSET_BPM)
    beat_number = data[OFFSET_BEAT_NUMBER]

    bpm = bpm_raw / 100.0
    pitch_percent = (pitch_raw - PITCH_CENTER) / PITCH_SCALE

    return BeatPacket(
        device_name=device_name,
        device_number=device_number,
        bpm=bpm,
        pitch_percent=pitch_percent,
        beat_number=beat_number,
        next_beat_ms=next_beat_ms,
    )
