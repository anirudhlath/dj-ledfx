from __future__ import annotations

import asyncio
import dataclasses
import random
import time
from collections.abc import Callable, Collection

from loguru import logger

from dj_ledfx.devices.lifx.packet import (
    GET_HOST_FIRMWARE,
    GET_VERSION,
    STATE_HOST_FIRMWARE,
    STATE_UNHANDLED,
    STATE_VERSION,
    LifxPacket,
    build_echo_request,
    parse_state_host_firmware,
    parse_state_service,
    parse_state_version,
)
from dj_ledfx.devices.lifx.types import LifxDeviceRecord

PacketListener = Callable[[LifxPacket, tuple[str, int]], None]
_Waiter = tuple[frozenset[int], "asyncio.Future[LifxPacket]"]


class LifxTransport:
    """Shared UDP transport for all LIFX devices on the network.

    Replies are matched to their request by (device IP, sequence number), so any
    number of requests can be in flight at once. Discovery listens through
    add_listener() instead of replacing the packet handler.
    """

    def __init__(self) -> None:
        self._source_id = random.randint(2, 0xFFFFFFFF)
        self._sequence_counter = 0
        self._socket: asyncio.DatagramTransport | None = None
        self._protocol: _LifxUDPProtocol | None = None
        self._probe_task: asyncio.Task[None] | None = None
        self._is_open = False

        # Device registry: (ip, port) -> device record
        self._devices: dict[tuple[str, int], LifxDeviceRecord] = {}
        # RTT callbacks: ip -> callback(rtt_ms)
        self._rtt_callbacks: dict[str, Callable[[float], None]] = {}
        # Pending echo probes: sequence_counter -> (device_ip, send_time)
        self._pending_probes: dict[int, tuple[str, float]] = {}
        # Requests waiting for a reply: (ip, wire sequence) -> (accepted types, future)
        self._waiters: dict[tuple[str, int], _Waiter] = {}
        self._listeners: list[PacketListener] = []

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
        for _types, future in self._waiters.values():
            future.cancel()
        self._waiters.clear()
        self._listeners.clear()
        logger.debug("LIFX transport closed")

    def send_packet(self, packet: LifxPacket, addr: tuple[str, int]) -> None:
        if self._socket:
            self._socket.sendto(packet.pack(), addr)

    def make_request(self, mac: bytes, msg_type: int, payload: bytes = b"") -> LifxPacket:
        """A unicast packet that asks for a reply. request_response() sets the sequence."""
        return LifxPacket(
            tagged=False,
            source=self._source_id,
            target=mac + b"\x00\x00",
            ack_required=False,
            res_required=True,
            sequence=0,
            msg_type=msg_type,
            payload=payload,
        )

    def register_device(
        self,
        record: LifxDeviceRecord,
        rtt_callback: Callable[[float], None] | None = None,
    ) -> None:
        key = (record.ip, record.port)
        self._devices[key] = record
        if rtt_callback:
            self._rtt_callbacks[record.ip] = rtt_callback

    def add_listener(self, listener: PacketListener) -> None:
        self._listeners.append(listener)

    def remove_listener(self, listener: PacketListener) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    async def request_response(
        self,
        packet: LifxPacket,
        addr: tuple[str, int],
        response_type: int | Collection[int],
        timeout: float = 1.0,
    ) -> LifxPacket | None:
        """Send `packet` and wait for its reply.

        The reply is one of `response_type`, or StateUnhandled (223) when the light
        doesn't support the message. Returns None on timeout.
        """
        accepted = {response_type} if isinstance(response_type, int) else set(response_type)
        seq = self.next_sequence() % 256
        key = (addr[0], seq)
        future: asyncio.Future[LifxPacket] = asyncio.get_running_loop().create_future()
        self._waiters[key] = (frozenset(accepted | {STATE_UNHANDLED}), future)
        try:
            self.send_packet(dataclasses.replace(packet, sequence=seq), addr)
            return await asyncio.wait_for(future, timeout)
        except TimeoutError:
            return None
        finally:
            self._waiters.pop(key, None)

    def start_probing(self, interval_s: float = 2.0) -> None:
        if self._probe_task is None or self._probe_task.done():
            self._probe_task = asyncio.create_task(self._probe_loop(interval_s))

    async def _probe_loop(self, interval_s: float) -> None:
        while self._is_open:
            now = time.monotonic()
            stale = [k for k, (_, t) in self._pending_probes.items() if now - t > interval_s]
            for k in stale:
                del self._pending_probes[k]

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

    def _broadcast_get_service(self, addr: tuple[str, int]) -> None:
        self.send_packet(
            LifxPacket(
                tagged=True,
                source=self._source_id,
                target=b"\x00" * 8,
                ack_required=False,
                res_required=False,
                sequence=self.next_sequence() % 256,
                msg_type=2,
                payload=b"",
            ),
            addr,
        )

    async def discover(
        self,
        timeout_s: float = 1.0,
        on_record: Callable[[LifxDeviceRecord], None] | None = None,
    ) -> list[LifxDeviceRecord]:
        """Broadcast GetService, collect responses, query versions.

        If *on_record* is provided it is called as soon as each device's
        version query completes, rather than waiting for all devices.
        """
        discovered: dict[str, tuple[bytes, str, int]] = {}  # mac_hex -> (mac, ip, port)
        version_tasks: list[asyncio.Task[LifxDeviceRecord | None]] = []
        results: list[LifxDeviceRecord] = []

        async def _query_version_and_record(
            mac: bytes, ip: str, port: int
        ) -> LifxDeviceRecord | None:
            vendor, product = await self._query_version(mac, ip, port)
            record = LifxDeviceRecord(mac=mac, ip=ip, port=port, vendor=vendor, product=product)
            results.append(record)
            if on_record is not None:
                on_record(record)
            return record

        def _on_state_service(pkt: LifxPacket, addr: tuple[str, int]) -> None:
            if pkt.msg_type != 3:
                return
            service, port = parse_state_service(pkt.payload)
            if service != 1:  # UDP
                return
            mac = pkt.target[:6]
            if mac.hex() not in discovered:
                discovered[mac.hex()] = (mac, addr[0], port)
                version_tasks.append(
                    asyncio.create_task(_query_version_and_record(mac, addr[0], port))
                )

        self.add_listener(_on_state_service)
        try:
            # Broadcast GetService 3 times, 1 second apart; dedup by MAC
            for i in range(3):
                self._broadcast_get_service(("255.255.255.255", 56700))
                if i < 2:
                    await asyncio.sleep(1.0)
            remaining = timeout_s - 2.0
            if remaining > 0:
                await asyncio.sleep(remaining)
        finally:
            self.remove_listener(_on_state_service)

        if version_tasks:
            await asyncio.gather(*version_tasks, return_exceptions=True)

        logger.info("LIFX discovery found {} devices", len(results))
        return results

    async def unicast_sweep(
        self,
        subnet_hosts: list[str],
        concurrency: int = 50,
        timeout_s: float = 0.5,
    ) -> list[LifxDeviceRecord]:
        """Send GetService to every IP in the list. Rate-limited."""
        discovered: dict[str, tuple[bytes, str, int]] = {}  # mac_hex -> (mac, ip, port)

        def _on_state_service(pkt: LifxPacket, addr: tuple[str, int]) -> None:
            if pkt.msg_type != 3:
                return
            service, port = parse_state_service(pkt.payload)
            if service == 1:  # UDP
                mac = pkt.target[:6]
                discovered[mac.hex()] = (mac, addr[0], port)

        self.add_listener(_on_state_service)
        try:
            sem = asyncio.Semaphore(concurrency)

            async def _probe_host(ip: str) -> None:
                async with sem:
                    self._broadcast_get_service((ip, 56700))

            await asyncio.gather(*[_probe_host(ip) for ip in subnet_hosts])
            await asyncio.sleep(timeout_s)
        finally:
            self.remove_listener(_on_state_service)

        results: list[LifxDeviceRecord] = []
        for mac, ip, port in discovered.values():
            vendor, product = await self._query_version(mac, ip, port)
            results.append(
                LifxDeviceRecord(mac=mac, ip=ip, port=port, vendor=vendor, product=product)
            )

        logger.info("LIFX unicast sweep found {} devices", len(results))
        return results

    async def query_version(self, mac: bytes, ip: str, port: int) -> tuple[int, int] | None:
        """(vendor, product), or None if the light doesn't answer two tries."""
        request = self.make_request(mac, GET_VERSION)
        for _attempt in range(2):
            reply = await self.request_response(request, (ip, port), STATE_VERSION, timeout=0.5)
            if reply is not None and reply.msg_type == STATE_VERSION:
                vendor, product, _version = parse_state_version(reply.payload)
                return int(vendor), int(product)
        return None

    async def _query_version(self, mac: bytes, ip: str, port: int) -> tuple[int, int]:
        """Query a device's vendor and product. Returns (1, 0) if it never answers."""
        version = await self.query_version(mac, ip, port)
        if version is None:
            logger.warning("LIFX device {} did not respond to GetVersion, defaulting to bulb", ip)
            return 1, 0
        return version

    async def query_host_firmware(self, mac: bytes, ip: str, port: int) -> tuple[int, int] | None:
        """(major, minor) of the light's firmware, or None if it doesn't answer."""
        reply = await self.request_response(
            self.make_request(mac, GET_HOST_FIRMWARE), (ip, port), STATE_HOST_FIRMWARE, 0.5
        )
        if reply is None or reply.msg_type != STATE_HOST_FIRMWARE:
            return None
        return parse_state_host_firmware(reply.payload)

    def _on_packet_received(self, data: bytes, addr: tuple[str, int]) -> None:
        try:
            pkt = LifxPacket.unpack(data)
        except Exception:
            return

        if pkt.msg_type == 59:  # EchoResponse
            self._handle_echo_response(pkt, addr)
            return

        waiter = self._waiters.get((addr[0], pkt.sequence))
        if waiter is not None:
            accepted, future = waiter
            if pkt.msg_type in accepted and not future.done():
                future.set_result(pkt)

        for listener in tuple(self._listeners):
            listener(pkt, addr)

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
