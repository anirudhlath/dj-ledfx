from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

from loguru import logger

from dj_ledfx.events import BeatEvent, EventBus
from dj_ledfx.prodjlink.constants import PRODJLINK_PORT
from dj_ledfx.prodjlink.packets import parse_beat_packet

# Re-export BeatEvent for backward compatibility
__all__ = [
    "BeatEvent",
    "Listening",
    "ProDJLinkListener",
    "hear_pro_dj_link",
    "listen_address",
    "start_listener",
]


@dataclass(frozen=True, slots=True)
class Listening:
    """Where the app hears Pro DJ Link, for GET /inputs: the bound host:port. None with
    --demo, or after a bind that failed (`failed`), when the internal clock keeps the
    tempo."""

    address: str | None = None
    failed: bool = False


class ProDJLinkListener(asyncio.DatagramProtocol):
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._transport: asyncio.DatagramTransport | None = None
        self.address: str | None = None  # host:port it listens on, once bound

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self._transport = transport  # type: ignore[assignment]
        sockname = transport.get_extra_info("sockname")
        if sockname:
            self.address = f"{sockname[0]}:{sockname[1]}"
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
            pitch_percent=packet.pitch_percent,
            track_bpm=packet.bpm,
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


def listen_address(interface: str) -> tuple[str, int]:
    """Where to hear Pro DJ Link for the config's network.interface: "auto" is every
    interface. The port is Pro DJ Link's beat port."""
    return ("0.0.0.0" if interface == "auto" else interface), PRODJLINK_PORT


async def start_listener(
    event_bus: EventBus,
    interface: str = "0.0.0.0",
    port: int = PRODJLINK_PORT,
) -> ProDJLinkListener:
    loop = asyncio.get_running_loop()
    _transport, protocol = await loop.create_datagram_endpoint(
        lambda: ProDJLinkListener(event_bus),
        local_addr=(interface, port),
        allow_broadcast=True,
    )
    assert isinstance(protocol, ProDJLinkListener)
    logger.info("Listening for Pro DJ Link beats on {}", protocol.address)
    return protocol


async def hear_pro_dj_link(
    event_bus: EventBus, host: str, port: int
) -> tuple[ProDJLinkListener | None, Listening]:
    """The listener on host:port, and where it listens. A port it can't bind (another app
    holds it, or no such address) only warns: the internal clock keeps the tempo."""
    try:
        listener = await start_listener(event_bus, interface=host, port=port)
    except OSError as exc:
        logger.warning(
            "Pro DJ Link isn't heard: can't listen on {}:{} ({}); the internal clock keeps "
            "the tempo",
            host,
            port,
            exc,
        )
        return None, Listening(failed=True)
    return listener, Listening(address=listener.address)
