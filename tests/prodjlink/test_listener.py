import asyncio
import socket

import pytest
from conftest import events
from loguru import logger
from tempo_fakes import beat_packet

from dj_ledfx.events import EventBus
from dj_ledfx.prodjlink.constants import PRODJLINK_PORT
from dj_ledfx.prodjlink.listener import (
    BeatEvent,
    Listening,
    ProDJLinkListener,
    hear_pro_dj_link,
    listen_address,
    start_listener,
)


async def test_listener_emits_beat_event() -> None:
    bus = EventBus()
    heard = events(bus, BeatEvent)

    listener = ProDJLinkListener(event_bus=bus)
    listener.datagram_received(beat_packet(), ("127.0.0.1", 50001))

    assert len(heard) == 1
    assert heard[0].bpm == 128.0
    assert heard[0].beat_position == 1


async def test_listener_ignores_invalid_packets() -> None:
    bus = EventBus()
    heard = events(bus, BeatEvent)

    listener = ProDJLinkListener(event_bus=bus)
    listener.datagram_received(b"\x00" * 50, ("127.0.0.1", 50001))

    assert len(heard) == 0


async def test_the_listener_tells_the_track_bpm_apart_from_the_pitch() -> None:
    bus = EventBus()
    heard = events(bus, BeatEvent)

    ProDJLinkListener(event_bus=bus).datagram_received(
        beat_packet(bpm=124.0, pitch_percent=1.2), ("127.0.0.1", 50001)
    )

    [event] = heard
    assert event.track_bpm == 124.0
    assert event.pitch_percent == pytest.approx(1.2, abs=0.001)
    assert event.bpm == pytest.approx(124.0 * 1.012, abs=0.01)  # pitch-adjusted


async def test_the_listener_hears_beats_where_it_says_it_listens() -> None:
    bus = EventBus()
    heard = events(bus, BeatEvent)
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
            while not heard:
                await asyncio.sleep(0.01)
        sender.close()
    finally:
        listener.close()

    assert (heard[0].beat_position, heard[0].device_number) == (3, 2)


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
