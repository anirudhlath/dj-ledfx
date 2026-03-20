from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Callable

from loguru import logger

from dj_ledfx.devices.lifx.packet import LifxPacket
from dj_ledfx.devices.lifx.types import LifxDeviceRecord


class LifxTransport:
    """Shared UDP transport for all LIFX devices on the network."""

    def __init__(self) -> None:
        self._source_id = random.randint(2, 0xFFFFFFFF)
        self._sequence_counter = 0
        self._socket: asyncio.DatagramTransport | None = None
        self._protocol: _LifxUDPProtocol | None = None
        self._probe_task: asyncio.Task[None] | None = None
        self._is_open = False

        # Device registry: (ip, port) → device record
        self._devices: dict[tuple[str, int], LifxDeviceRecord] = {}
        # RTT callbacks: ip → callback(rtt_ms)
        self._rtt_callbacks: dict[str, Callable[[float], None]] = {}
        # Pending echo probes: sequence_counter → (device_ip, send_time)
        self._pending_probes: dict[int, tuple[str, float]] = {}

    @property
    def source_id(self) -> int:
        return self._source_id

    @property
    def is_open(self) -> bool:
        return self._is_open

    def next_sequence(self) -> int:
        self._sequence_counter += 1
        return self._sequence_counter

    async def open(self) -> None:
        loop = asyncio.get_running_loop()
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: _LifxUDPProtocol(self),
            local_addr=("0.0.0.0", 0),
            allow_broadcast=True,
        )
        self._socket = transport
        self._protocol = protocol
        self._is_open = True
        logger.debug("LIFX transport opened on port {}", self._socket.get_extra_info("sockname"))

    async def close(self) -> None:
        if self._probe_task and not self._probe_task.done():
            self._probe_task.cancel()
            try:
                await self._probe_task
            except asyncio.CancelledError:
                pass
        if self._socket:
            self._socket.close()
        self._is_open = False
        self._devices.clear()
        self._rtt_callbacks.clear()
        self._pending_probes.clear()
        logger.debug("LIFX transport closed")

    def send_packet(self, packet: LifxPacket, addr: tuple[str, int]) -> None:
        if self._socket:
            self._socket.sendto(packet.pack(), addr)

    def register_device(
        self,
        record: LifxDeviceRecord,
        rtt_callback: Callable[[float], None] | None = None,
    ) -> None:
        key = (record.ip, record.port)
        self._devices[key] = record
        if rtt_callback:
            self._rtt_callbacks[record.ip] = rtt_callback

    async def request_response(
        self,
        packet: LifxPacket,
        addr: tuple[str, int],
        response_type: int,
        timeout: float = 1.0,
    ) -> LifxPacket | None:
        """Send a packet and wait for a specific response type. Returns None on timeout."""
        result: list[LifxPacket] = []
        original = self._on_packet_received

        def _response_handler(data: bytes, recv_addr: tuple[str, int]) -> None:
            try:
                pkt = LifxPacket.unpack(data)
            except Exception:
                return
            if pkt.msg_type == response_type:
                result.append(pkt)

        self._on_packet_received = _response_handler  # type: ignore[assignment]
        try:
            self.send_packet(packet, addr)
            deadline = time.monotonic() + timeout
            while not result and time.monotonic() < deadline:
                await asyncio.sleep(0.01)
        finally:
            self._on_packet_received = original  # type: ignore[method-assign]

        return result[0] if result else None

    def start_probing(self, interval_s: float = 2.0) -> None:
        if self._probe_task is None or self._probe_task.done():
            self._probe_task = asyncio.create_task(self._probe_loop(interval_s))

    async def _probe_loop(self, interval_s: float) -> None:
        from dj_ledfx.devices.lifx.packet import build_echo_request

        while self._is_open:
            now = time.monotonic()
            # Clean stale entries
            stale = [k for k, (_, t) in self._pending_probes.items() if now - t > interval_s]
            for k in stale:
                del self._pending_probes[k]

            # Send echo to each registered device
            for (ip, port), record in self._devices.items():
                seq = self.next_sequence()
                self._pending_probes[seq] = (record.ip, now)
                pkt = LifxPacket(
                    tagged=False,
                    source=self._source_id,
                    target=record.mac + b"\x00\x00",
                    ack_required=False,
                    res_required=False,
                    sequence=seq % 256,
                    msg_type=58,
                    payload=build_echo_request(seq.to_bytes(8, "little")),
                )
                self.send_packet(pkt, (ip, port))

            await asyncio.sleep(interval_s)

    async def discover(self, timeout_s: float = 1.0) -> list[LifxDeviceRecord]:
        """Broadcast GetService, collect responses, query versions."""
        from dj_ledfx.devices.lifx.packet import (
            parse_state_service,
            parse_state_version,
        )

        discovered: dict[str, tuple[bytes, str, int]] = {}  # mac_hex → (mac, ip, port)
        original_handler = self._on_packet_received

        def _discovery_handler(data: bytes, addr: tuple[str, int]) -> None:
            try:
                pkt = LifxPacket.unpack(data)
            except Exception:
                return
            if pkt.msg_type == 3:  # StateService
                service, port = parse_state_service(pkt.payload)
                if service == 1:  # UDP
                    mac = pkt.target[:6]
                    discovered[mac.hex()] = (mac, addr[0], port)

        self._on_packet_received = _discovery_handler  # type: ignore[method-assign]

        try:
            # Broadcast GetService 3 times, 1 second apart; dedup by MAC
            for i in range(3):
                broadcast_pkt = LifxPacket(
                    tagged=True,
                    source=self._source_id,
                    target=b"\x00" * 8,
                    ack_required=False,
                    res_required=False,
                    sequence=self.next_sequence() % 256,
                    msg_type=2,
                    payload=b"",
                )
                self.send_packet(broadcast_pkt, ("255.255.255.255", 56700))
                if i < 2:
                    await asyncio.sleep(1.0)

            # Wait remaining time for stragglers
            remaining = timeout_s - 2.0
            if remaining > 0:
                await asyncio.sleep(remaining)
        finally:
            self._on_packet_received = original_handler  # type: ignore[method-assign]

        # Query version for each discovered device
        results: list[LifxDeviceRecord] = []
        for _mac_hex, (mac, ip, port) in discovered.items():
            version_responses: list[tuple[int, int, int]] = []

            def _version_handler(
                data: bytes,
                addr: tuple[str, int],
                _responses: list[tuple[int, int, int]] = version_responses,
            ) -> None:
                try:
                    pkt = LifxPacket.unpack(data)
                except Exception:
                    return
                if pkt.msg_type == 33:  # StateVersion
                    _responses.append(parse_state_version(pkt.payload))

            self._on_packet_received = _version_handler  # type: ignore[method-assign]
            try:
                version_pkt = LifxPacket(
                    tagged=False,
                    source=self._source_id,
                    target=mac + b"\x00\x00",
                    ack_required=False,
                    res_required=True,
                    sequence=self.next_sequence() % 256,
                    msg_type=32,
                    payload=b"",
                )
                self.send_packet(version_pkt, (ip, port))
                await asyncio.sleep(0.5)
                # Retry once if no response yet
                if not version_responses:
                    self.send_packet(version_pkt, (ip, port))
                    await asyncio.sleep(0.5)
            finally:
                self._on_packet_received = original_handler  # type: ignore[method-assign]

            if version_responses:
                vendor, product, _version = version_responses[0]
            else:
                logger.warning(
                    "LIFX device {} did not respond to GetVersion, defaulting to bulb", ip
                )
                vendor, product, _version = 1, 0, 0
            results.append(
                LifxDeviceRecord(
                    mac=mac,
                    ip=ip,
                    port=port,
                    vendor=vendor,
                    product=product,
                )
            )

        logger.info("LIFX discovery found {} devices", len(results))
        return results

    async def unicast_sweep(
        self,
        subnet_hosts: list[str],
        concurrency: int = 50,
        timeout_s: float = 0.5,
    ) -> list[LifxDeviceRecord]:
        """Send GetService to every IP in the list. Rate-limited."""
        discovered: dict[str, tuple[bytes, str, int]] = {}  # mac_hex → (mac, ip, port)
        original_handler = self._on_packet_received

        from dj_ledfx.devices.lifx.packet import (
            parse_state_service,
            parse_state_version,
        )

        def _sweep_handler(data: bytes, addr: tuple[str, int]) -> None:
            try:
                pkt = LifxPacket.unpack(data)
            except Exception:
                return
            if pkt.msg_type == 3:  # StateService
                service, port = parse_state_service(pkt.payload)
                if service == 1:  # UDP
                    mac = pkt.target[:6]
                    discovered[mac.hex()] = (mac, addr[0], port)

        self._on_packet_received = _sweep_handler  # type: ignore[method-assign]

        try:
            sem = asyncio.Semaphore(concurrency)

            async def _probe_host(ip: str) -> None:
                async with sem:
                    pkt = LifxPacket(
                        tagged=True,
                        source=self._source_id,
                        target=b"\x00" * 8,
                        ack_required=False,
                        res_required=False,
                        sequence=self.next_sequence() % 256,
                        msg_type=2,
                        payload=b"",
                    )
                    self.send_packet(pkt, (ip, 56700))

            await asyncio.gather(*[_probe_host(ip) for ip in subnet_hosts])
            await asyncio.sleep(timeout_s)
        finally:
            self._on_packet_received = original_handler  # type: ignore[method-assign]

        # Query version for each responder (reuse discover logic)
        results: list[LifxDeviceRecord] = []
        for _mac_hex, (mac, ip, port) in discovered.items():
            version_responses: list[tuple[int, int, int]] = []

            def _version_handler(
                data: bytes,
                addr: tuple[str, int],
                _responses: list[tuple[int, int, int]] = version_responses,
            ) -> None:
                try:
                    pkt = LifxPacket.unpack(data)
                except Exception:
                    return
                if pkt.msg_type == 33:  # StateVersion
                    _responses.append(parse_state_version(pkt.payload))

            self._on_packet_received = _version_handler  # type: ignore[method-assign]
            try:
                version_pkt = LifxPacket(
                    tagged=False,
                    source=self._source_id,
                    target=mac + b"\x00\x00",
                    ack_required=False,
                    res_required=True,
                    sequence=self.next_sequence() % 256,
                    msg_type=32,
                    payload=b"",
                )
                self.send_packet(version_pkt, (ip, port))
                await asyncio.sleep(0.5)
                if not version_responses:
                    self.send_packet(version_pkt, (ip, port))
                    await asyncio.sleep(0.5)
            finally:
                self._on_packet_received = original_handler  # type: ignore[method-assign]

            if version_responses:
                vendor, product, _version = version_responses[0]
            else:
                logger.warning(
                    "LIFX device {} did not respond to GetVersion in unicast sweep,"
                    " defaulting to bulb",
                    ip,
                )
                vendor, product, _version = 1, 0, 0
            results.append(
                LifxDeviceRecord(
                    mac=mac,
                    ip=ip,
                    port=port,
                    vendor=vendor,
                    product=product,
                )
            )

        logger.info("LIFX unicast sweep found {} devices", len(results))
        return results

    def _on_packet_received(self, data: bytes, addr: tuple[str, int]) -> None:
        try:
            pkt = LifxPacket.unpack(data)
        except Exception:
            return

        if pkt.msg_type == 59:  # EchoResponse
            self._handle_echo_response(pkt, addr)

    def _handle_echo_response(self, pkt: LifxPacket, addr: tuple[str, int]) -> None:
        if len(pkt.payload) >= 8:
            seq = int.from_bytes(pkt.payload[:8], "little")
        else:
            return

        probe = self._pending_probes.pop(seq, None)
        if probe is None:
            return

        device_ip, send_time = probe
        rtt_ms = (time.monotonic() - send_time) * 1000.0
        callback = self._rtt_callbacks.get(device_ip)
        if callback:
            callback(rtt_ms)
            logger.trace("RTT for {}: {:.1f}ms", device_ip, rtt_ms)


class _LifxUDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, transport_owner: LifxTransport) -> None:
        self._owner = transport_owner

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self._owner._on_packet_received(data, addr)

    def error_received(self, exc: Exception) -> None:
        logger.warning("LIFX UDP error: {}", exc)
