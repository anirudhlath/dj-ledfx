"""Fakes for the tempo clock's tests: a time they move, and beat events and beat packets
as players send them."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from dj_ledfx.events import BeatEvent, EventBus
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
from dj_ledfx.tempo.clock import TempoClock

PLAYER = "CDJ-3000"
START = 1000.0  # FakeTime's first time.monotonic()
START_WALL = datetime(2026, 10, 1, 19, 0, tzinfo=UTC)


@dataclass
class FakeTime:
    """The clock's two times, moved together: time.monotonic() and the wall clock."""

    now: float = START

    def monotonic(self) -> float:
        return self.now

    def wall(self) -> datetime:
        return START_WALL + timedelta(seconds=self.now - START)


def tempo_clock(time: FakeTime, **kwargs: Any) -> TempoClock:
    """A TempoClock on fake time."""
    return TempoClock(now=time.monotonic, wall=time.wall, **kwargs)


def events(bus: EventBus, event_type: type) -> list[Any]:
    """Every event of this type the bus emits from now on."""
    seen: list[Any] = []
    bus.subscribe(event_type, seen.append)
    return seen


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
        device_number=deck,
        device_name=player,
        timestamp=at,
        pitch_percent=pitch_percent,
        track_bpm=bpm,
    )


def play(
    clock: TempoClock,
    time: FakeTime,
    beats: int,
    *,
    first: int = 1,
    bpm: float = 128.0,
    deck: int = 1,
    pitch_percent: float = 0.0,
) -> list[float]:
    """A deck playing `beats` beats from now, the first `first` (1–4) into its bar: time
    moves to each beat and the clock hears it. The times of the beats."""
    period = 60.0 / (bpm * (1.0 + pitch_percent / 100.0))
    start, times = time.now, []
    for k in range(beats):
        time.now = start + k * period
        clock.on_beat(
            beat_event(
                time.now,
                beat=(first - 1 + k) % 4 + 1,
                bpm=bpm,
                deck=deck,
                pitch_percent=pitch_percent,
            )
        )
        times.append(time.now)
    return times


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
