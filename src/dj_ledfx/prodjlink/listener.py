from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from loguru import logger

from dj_ledfx.events import EventBus
from dj_ledfx.prodjlink.packets import parse_beat_packet


@dataclass(frozen=True, slots=True)
class BeatEvent:
    bpm: float  # pitch-adjusted BPM
    beat_position: int  # 1-4
    next_beat_ms: int
    device_number: int
    device_name: str
    timestamp: float  # time.monotonic()


class ProDJLinkListener(asyncio.DatagramProtocol):
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self._transport = transport  # type: ignore[assignment]
        logger.info("ProDJLink listener started")

    def connection_lost(self, exc: Exception | None) -> None:
        logger.info("ProDJLink listener stopped")

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        packet = parse_beat_packet(data)
        if packet is None:
            return

        event = BeatEvent(
            bpm=packet.pitch_adjusted_bpm,
            beat_position=packet.beat_number,
            next_beat_ms=packet.next_beat_ms,
            device_number=packet.device_number,
            device_name=packet.device_name,
            timestamp=time.monotonic(),
        )
        logger.debug(
            "Beat: {} BPM={:.1f} beat={}/4 from {}",
            event.device_name,
            event.bpm,
            event.beat_position,
            addr[0],
        )
        self._event_bus.emit(event)

    def close(self) -> None:
        if self._transport is not None:
            self._transport.close()


async def start_listener(
    event_bus: EventBus,
    interface: str = "0.0.0.0",
    port: int = 50001,
) -> ProDJLinkListener:
    loop = asyncio.get_running_loop()
    _transport, protocol = await loop.create_datagram_endpoint(
        lambda: ProDJLinkListener(event_bus),
        local_addr=(interface, port),
        allow_broadcast=True,
    )
    logger.info("Listening for Pro DJ Link beats on {}:{}", interface, port)
    assert isinstance(protocol, ProDJLinkListener)
    return protocol
