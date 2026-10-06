from __future__ import annotations

import asyncio
import json
import random
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from loguru import logger

from dj_ledfx.devices.govee.protocol import build_scan_message, build_status_query
from dj_ledfx.devices.govee.types import GoveeDeviceRecord

MULTICAST_ADDR = "239.255.255.250"
DISCOVERY_PORT = 4001
RESPONSE_PORT = 4002
COMMAND_PORT = 4003
# Each probe round waits a random share of the interval in this range, so the probes land at
# every phase of a dozing lamp's beacon cycle (light-sync spec §4).
PROBE_SPREAD = (0.75, 1.25)
# How long a probe waits for its reply, asked once: as long as a light monitor's read does
# (adapter_base.STATUS_TIMEOUT_S). A reply that comes later times nothing, unless a newer
# query to the lamp is in flight by then: a status reply carries nothing to match it by, so
# that query takes it as its own and times a round trip too short. A read's second try
# could already do the same.
PROBE_TIMEOUT_S = 1.0


@dataclass
class _StatusQuery:
    """A status query in flight to one lamp. Whoever asks the lamp meanwhile shares it: a
    devStatus reply carries nothing that says which query it answers."""

    reply: asyncio.Future[dict[str, Any]]
    sent_at: float  # on the transport's clock: the reply times the lamp's round trip
    waiting: int = 0  # callers still waiting for the reply


def _log_a_failure(loop: asyncio.Task[None]) -> None:
    """A probe loop that ends with an error logs it, once: nothing else awaits the loop.
    One cancelled at close ends quietly."""
    if not loop.cancelled() and (error := loop.exception()) is not None:
        logger.opt(exception=error).error("The Govee probe loop failed")


class GoveeTransport:
    """Shared UDP transport for all Govee devices on the LAN. A lamp's round trips come from
    its status queries, the probe loop's and the light monitor's reads alike: each query
    that gets its reply times one."""

    def __init__(
        self,
        clock: Callable[[], float] = time.monotonic,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        rng: random.Random | None = None,
    ) -> None:
        self._send_transport: asyncio.DatagramTransport | None = None
        self._recv_transport: asyncio.DatagramTransport | None = None
        self._is_open = False
        self._clock = clock
        self._sleep = sleep  # the probe loop's waits
        self._rng = rng or random.Random()

        # Response routing: cmd → handler
        self._cmd_handlers: dict[str, Callable[[dict[str, Any], tuple[str, int]], None]] = {}
        self._rtt_callbacks: dict[str, Callable[[float], None]] = {}  # ip → callback
        # Status queries in flight, one per lamp: ip → query
        self._pending_status: dict[str, _StatusQuery] = {}
        self._heard: dict[str, float] = {}  # ip → when its last status reply came
        self._streaming: dict[str, Callable[[], bool]] = {}  # ip → whether it streams now
        self._probe_task: asyncio.Task[None] | None = None
        self._probes: set[asyncio.Task[dict[str, Any] | None]] = set()  # probes in flight

    @property
    def is_open(self) -> bool:
        return self._is_open

    @property
    def can_receive(self) -> bool:
        """False when another program holds UDP 4002, so the lamps' replies never reach us."""
        return self._recv_transport is not None

    async def open(self) -> None:
        loop = asyncio.get_running_loop()

        # Sender socket (for commands to port 4003 and multicast to 4001)
        send_transport, _ = await loop.create_datagram_endpoint(
            lambda: _GoveeUDPProtocol(self),
            local_addr=("0.0.0.0", 0),
        )
        self._send_transport = send_transport

        # Receiver socket (listen on port 4002 for responses)
        # Retry with exponential backoff in case port is briefly occupied
        _backoff_delays = [1.0, 2.0, 4.0]
        for _attempt, _delay in enumerate(_backoff_delays):
            try:
                recv_transport, _ = await loop.create_datagram_endpoint(
                    lambda: _GoveeUDPProtocol(self),
                    local_addr=("0.0.0.0", RESPONSE_PORT),
                )
                self._recv_transport = recv_transport
                break
            except OSError as exc:
                if _attempt < len(_backoff_delays) - 1:
                    logger.warning(
                        "Govee: failed to bind port {} (attempt {}): {}. Retrying in {}s…",
                        RESPONSE_PORT,
                        _attempt + 1,
                        exc,
                        _delay,
                    )
                    await asyncio.sleep(_delay)
                else:
                    logger.warning(
                        "Govee: could not bind port {} after {} attempts: {}. "
                        "Discovery responses will not be received.",
                        RESPONSE_PORT,
                        len(_backoff_delays),
                        exc,
                    )

        self._is_open = True
        logger.debug("Govee transport opened")

    async def close(self) -> None:
        stopping: list[asyncio.Task[Any]] = [*self._probes]  # the loop, and its probes
        if self._probe_task is not None:
            stopping.append(self._probe_task)
        for task in stopping:
            task.cancel()
        if stopping:
            await asyncio.wait(stopping)
        self._probe_task = None
        if self._recv_transport:
            self._recv_transport.close()
        if self._send_transport:
            self._send_transport.close()
        self._is_open = False
        self._rtt_callbacks.clear()
        self._streaming.clear()
        self._pending_status.clear()
        self._cmd_handlers.clear()
        logger.debug("Govee transport closed")

    async def send_command(self, ip: str, payload: dict[str, Any]) -> None:
        if self._send_transport:
            data = json.dumps(payload).encode("utf-8")
            self._send_transport.sendto(data, (ip, COMMAND_PORT))
        else:
            logger.warning("Govee send_command called but transport is not open")

    async def discover(
        self,
        timeout_s: float = 10.0,
        on_record: Callable[[GoveeDeviceRecord], None] | None = None,
    ) -> list[GoveeDeviceRecord]:
        discovered: dict[str, GoveeDeviceRecord] = {}  # device_id → record

        self._cmd_handlers["scan"] = self._make_scan_handler(discovered, on_record)

        try:
            scan_msg = build_scan_message()
            scan_data = json.dumps(scan_msg).encode("utf-8")

            # Send scan 3 times at 1s intervals
            for i in range(3):
                if self._send_transport:
                    self._send_transport.sendto(scan_data, (MULTICAST_ADDR, DISCOVERY_PORT))
                if i < 2:
                    await asyncio.sleep(1.0)

            # Wait remaining time for stragglers
            remaining = timeout_s - 2.0
            if remaining > 0:
                await asyncio.sleep(remaining)
        finally:
            self._cmd_handlers.pop("scan", None)

        logger.info("Govee discovery found {} devices", len(discovered))
        return list(discovered.values())

    async def query_status(self, ip: str, timeout_s: float = 2.0) -> dict[str, Any] | None:
        """The lamp's status, or None when no reply comes within timeout_s. A query to the
        lamp already in flight is shared, not sent again: each caller gets its one reply."""
        query = self._pending_status.get(ip)
        ask = query is None
        if query is None:
            reply: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
            query = self._pending_status[ip] = _StatusQuery(reply, self._clock())
        query.waiting += 1
        try:
            if ask:
                await self.send_command(ip, build_status_query())
            return await asyncio.wait_for(asyncio.shield(query.reply), timeout=timeout_s)
        except TimeoutError:
            return None
        finally:
            query.waiting -= 1
            if query.waiting == 0 and self._pending_status.get(ip) is query:
                del self._pending_status[ip]  # nobody waits for it any more

    def last_heard(self, ip: str) -> float | None:
        """When the lamp at ip last sent a status reply, on the transport's clock, or None."""
        return self._heard.get(ip)

    def register_device(
        self,
        record: GoveeDeviceRecord,
        rtt_callback: Callable[[float], None],
        *,
        streaming: Callable[[], bool],
    ) -> None:
        """Send the lamp's round trips, in ms, to rtt_callback. The probe loop asks the lamp
        for its status only while streaming() says it streams: an idle lamp's round trip
        wouldn't count."""
        self._rtt_callbacks[record.ip] = rtt_callback
        self._streaming[record.ip] = streaming

    def start_probing(self, interval_s: float) -> None:
        """Probe each lamp that streams about every interval_s, until the transport closes.
        Called again while the loop runs, it changes nothing. A loop that fails logs why."""
        if self._probe_task is None or self._probe_task.done():
            self._probe_task = asyncio.create_task(self._probe_loop(interval_s))
            self._probe_task.add_done_callback(_log_a_failure)

    async def _probe_loop(self, interval_s: float) -> None:
        """Each round waits a random 75–125% of interval_s, then asks each lamp that streams
        for its status, unless a query to it is in flight already. A probe's reply times a
        round trip as a read's does. Nothing is asked while another program holds UDP 4002:
        no reply could reach us."""
        while self._is_open:
            await self._sleep(interval_s * self._rng.uniform(*PROBE_SPREAD))
            if not self.can_receive:
                continue
            for ip, streaming in self._streaming.items():
                if ip in self._pending_status or not streaming():
                    continue
                probe = asyncio.create_task(self.query_status(ip, timeout_s=PROBE_TIMEOUT_S))
                self._probes.add(probe)
                probe.add_done_callback(self._probes.discard)

    def _make_scan_handler(
        self,
        discovered: dict[str, GoveeDeviceRecord],
        on_record: Callable[[GoveeDeviceRecord], None] | None = None,
    ) -> Callable[[dict[str, Any], tuple[str, int]], None]:
        def _handler(msg_data: dict[str, Any], addr: tuple[str, int]) -> None:
            data = msg_data.get("data", {})
            device_id = data.get("device", "")
            if device_id and device_id not in discovered:
                record = GoveeDeviceRecord(
                    ip=data.get("ip", addr[0]),
                    device_id=device_id,
                    sku=data.get("sku", ""),
                    wifi_version=data.get("wifiVersionSoft", ""),
                    ble_version=data.get("bleVersionSoft", ""),
                )
                discovered[device_id] = record
                if on_record is not None:
                    on_record(record)

        return _handler

    def _on_datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        try:
            msg = json.loads(data)
        except (json.JSONDecodeError, UnicodeDecodeError):
            return

        inner = msg.get("msg", {})
        cmd = inner.get("cmd", "")

        # Route to registered handler
        handler = self._cmd_handlers.get(cmd)
        if handler:
            handler(inner, addr)

        if cmd == "devStatus":
            self._handle_status_response(inner, addr)

    def _handle_status_response(self, msg: dict[str, Any], addr: tuple[str, int]) -> None:
        """A status reply says the lamp was heard, answers the query in flight to it and
        times its round trip. One that no query waits for (late, or another program's)
        times nothing."""
        ip = addr[0]
        self._heard[ip] = self._clock()
        query = self._pending_status.pop(ip, None)
        if query is None:
            return
        if not query.reply.done():
            query.reply.set_result(msg.get("data", {}))
        rtt_ms = (self._clock() - query.sent_at) * 1000.0
        callback = self._rtt_callbacks.get(ip)
        if callback is not None:
            callback(rtt_ms)
            logger.trace("Govee RTT for {}: {:.1f}ms", ip, rtt_ms)


class _GoveeUDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, owner: GoveeTransport) -> None:
        self._owner = owner

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self._owner._on_datagram_received(data, addr)

    def error_received(self, exc: Exception) -> None:
        logger.warning("Govee UDP error: {}", exc)
