"""Fakes for the tempo clock's tests: a time they move, and beat events and beat packets
as players send them."""

from __future__ import annotations

import struct

from dj_ledfx.events import BeatEvent
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

PLAYER = "CDJ-3000"


def beat_event(
    at: float,
    *,
    beat: int = 1,
    bpm: float = 128.0,
    deck: int = 1,
    player: str = PLAYER,
    pitch_percent: float = 0.0,
) -> BeatEvent:
    """A beat heard at `at`, as the listener makes one: `bpm` is the track's, and the
    event's own BPM is pitch-adjusted."""
    return BeatEvent(
        bpm=bpm * (1.0 + pitch_percent / 100.0),
        beat_position=beat,
        next_beat_ms=round(60_000 / bpm),
        device_number=deck,
        device_name=player,
        timestamp=at,
        pitch_percent=pitch_percent,
        track_bpm=bpm,
    )


def beat_packet(
    *,
    beat: int = 1,
    bpm: float = 128.0,
    deck: int = 1,
    player: str = PLAYER,
    pitch_percent: float = 0.0,
) -> bytes:
    """A beat packet from a current-generation player."""
    packet = bytearray(BEAT_PACKET_LEN)
    packet[0 : len(MAGIC_HEADER)] = MAGIC_HEADER
    packet[OFFSET_PACKET_TYPE] = PACKET_TYPE_BEAT
    packet[OFFSET_DEVICE_NAME : OFFSET_DEVICE_NAME + 20] = player.encode().ljust(20, b"\x00")
    packet[OFFSET_DEVICE_NUMBER] = deck
    struct.pack_into(">I", packet, OFFSET_NEXT_BEAT_MS, round(60_000 / bpm))
    struct.pack_into(">I", packet, OFFSET_PITCH, round(PITCH_CENTER + pitch_percent * PITCH_SCALE))
    struct.pack_into(">H", packet, OFFSET_BPM, round(bpm * 100))
    packet[OFFSET_BEAT_NUMBER] = beat
    packet[OFFSET_CAPABILITY] = CAPABILITY_CDJ3000
    return bytes(packet)
