import asyncio
import socket
import struct

import pytest
from loguru import logger
from tempo_fakes import beat_packet

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
    PRODJLINK_PORT,
)
from dj_ledfx.prodjlink.listener import (
    BeatEvent,
    Listening,
    ProDJLinkListener,
    hear_pro_dj_link,
    listen_address,
    start_listener,
)


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


async def test_the_listener_tells_the_track_bpm_apart_from_the_pitch() -> None:
    bus = EventBus()
    events: list[BeatEvent] = []
    bus.subscribe(BeatEvent, events.append)

    ProDJLinkListener(event_bus=bus).datagram_received(
        beat_packet(bpm=124.0, pitch_percent=1.2), ("127.0.0.1", 50001)
    )

    [event] = events
    assert event.track_bpm == 124.0
    assert event.pitch_percent == pytest.approx(1.2, abs=0.001)
    assert event.bpm == pytest.approx(124.0 * 1.012, abs=0.01)  # pitch-adjusted


async def test_the_listener_hears_beats_where_it_says_it_listens() -> None:
    bus = EventBus()
    events: list[BeatEvent] = []
    bus.subscribe(BeatEvent, events.append)
    listener = await start_listener(bus, interface="127.0.0.1", port=0)
    try:
        assert listener.address is not None
        host, port = listener.address.rsplit(":", 1)
        assert host == "127.0.0.1" and int(port) > 0
        sender, _ = await asyncio.get_running_loop().create_datagram_endpoint(
            asyncio.DatagramProtocol, remote_addr=(host, int(port))
        )
        sender.sendto(beat_packet(beat=3, deck=2))
        async with asyncio.timeout(2.0):
            while not events:
                await asyncio.sleep(0.01)
        sender.close()
    finally:
        listener.close()

    assert (events[0].beat_position, events[0].device_number) == (3, 2)


def test_the_config_s_interface_says_where_to_listen() -> None:
    assert listen_address("auto") == ("0.0.0.0", PRODJLINK_PORT)  # every interface: as deployed
    assert listen_address("127.0.0.2") == ("127.0.0.2", PRODJLINK_PORT)


async def test_a_listener_says_where_it_listens() -> None:
    listener, listening = await hear_pro_dj_link(EventBus(), "127.0.0.1", 0)
    try:
        assert listener is not None
        assert listening == Listening(address=listener.address)
    finally:
        if listener is not None:
            listener.close()


async def test_a_port_that_can_t_be_bound_leaves_the_tempo_to_the_internal_clock() -> None:
    warnings: list[str] = []
    sink = logger.add(lambda message: warnings.append(str(message)), level="WARNING")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as taken:  # another app has it
            taken.bind(("127.0.0.1", 0))
            port = taken.getsockname()[1]
            listener, listening = await hear_pro_dj_link(EventBus(), "127.0.0.1", port)
    finally:
        logger.remove(sink)

    assert (listener, listening) == (None, Listening(failed=True))
    assert len(warnings) == 1 and f"127.0.0.1:{port}" in warnings[0]
