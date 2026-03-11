import struct

from dj_ledfx.events import EventBus
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
)
from dj_ledfx.prodjlink.listener import BeatEvent, ProDJLinkListener


def _build_beat_packet(
    bpm_raw: int = 12800,
    beat_number: int = 1,
    device_number: int = 1,
) -> bytes:
    buf = bytearray(BEAT_PACKET_LEN)
    buf[0:10] = MAGIC_HEADER
    buf[OFFSET_PACKET_TYPE] = PACKET_TYPE_BEAT
    name = b"XDJ-AZ".ljust(20, b"\x00")
    buf[OFFSET_DEVICE_NAME : OFFSET_DEVICE_NAME + 20] = name
    buf[OFFSET_DEVICE_NUMBER] = device_number
    struct.pack_into(">I", buf, OFFSET_NEXT_BEAT_MS, 468)
    struct.pack_into(">I", buf, OFFSET_PITCH, PITCH_CENTER)
    struct.pack_into(">H", buf, OFFSET_BPM, bpm_raw)
    buf[OFFSET_BEAT_NUMBER] = beat_number
    buf[OFFSET_CAPABILITY] = CAPABILITY_CDJ3000
    return bytes(buf)


async def test_listener_emits_beat_event() -> None:
    bus = EventBus()
    events: list[BeatEvent] = []
    bus.subscribe(BeatEvent, events.append)

    listener = ProDJLinkListener(event_bus=bus)
    listener.datagram_received(_build_beat_packet(), ("192.168.1.1", 50001))

    assert len(events) == 1
    assert events[0].bpm == 128.0
    assert events[0].beat_position == 1


async def test_listener_ignores_invalid_packets() -> None:
    bus = EventBus()
    events: list[BeatEvent] = []
    bus.subscribe(BeatEvent, events.append)

    listener = ProDJLinkListener(event_bus=bus)
    listener.datagram_received(b"\x00" * 50, ("192.168.1.1", 50001))

    assert len(events) == 0
