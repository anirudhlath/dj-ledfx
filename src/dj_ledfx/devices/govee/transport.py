from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Callable
from typing import Any

from loguru import logger

from dj_ledfx.devices.govee.protocol import build_scan_message, build_status_query
from dj_ledfx.devices.govee.types import GoveeDeviceRecord

MULTICAST_ADDR = "239.255.255.250"
DISCOVERY_PORT = 4001
RESPONSE_PORT = 4002
COMMAND_PORT = 4003


class GoveeTransport:
    """Shared UDP transport for all Govee devices on the LAN."""

    def __init__(self) -> None:
        self._send_transport: asyncio.DatagramTransport | None = None
        self._recv_transport: asyncio.DatagramTransport | None = None
        self._is_open = False
        self._probe_task: asyncio.Task[None] | None = None

        # Response routing: cmd → handler
        self._cmd_handlers: dict[str, Callable[[dict[str, Any], tuple[str, int]], None]] = {}
        # Registered devices for probing
        self._devices: dict[str, GoveeDeviceRecord] = {}  # ip → record
        self._rtt_callbacks: dict[str, Callable[[float], None]] = {}  # ip → callback
        # Pending status queries: ip → (event, result_container)
        self._pending_status: dict[str, tuple[asyncio.Event, list[dict[str, Any]]]] = {}
        # Probe RTT tracking: ip → send_time (monotonic)
        self._probe_times: dict[str, float] = {}

    @property
    def is_open(self) -> bool:
        return self._is_open

    async def open(self) -> None:
        loop = asyncio.get_running_loop()

        # Sender socket (for commands to port 4003 and multicast to 4001)
        send_transport, _ = await loop.create_datagram_endpoint(
            lambda: _GoveeUDPProtocol(self),
            local_addr=("0.0.0.0", 0),
        )
        self._send_transport = send_transport

        # Receiver socket (listen on port 4002 for responses)
        recv_transport, _ = await loop.create_datagram_endpoint(
            lambda: _GoveeUDPProtocol(self),
            local_addr=("0.0.0.0", RESPONSE_PORT),
        )
        self._recv_transport = recv_transport

        self._is_open = True
        logger.debug("Govee transport opened")

    async def close(self) -> None:
        self.stop_probing()
        if self._probe_task and not self._probe_task.done():
            self._probe_task.cancel()
            try:
                await self._probe_task
            except asyncio.CancelledError:
                pass
        if self._recv_transport:
            self._recv_transport.close()
        if self._send_transport:
            self._send_transport.close()
        self._is_open = False
        self._devices.clear()
        self._rtt_callbacks.clear()
        self._pending_status.clear()
        self._cmd_handlers.clear()
        logger.debug("Govee transport closed")

    async def send_command(self, ip: str, payload: dict[str, Any]) -> None:
        if self._send_transport:
            data = json.dumps(payload).encode("utf-8")
            self._send_transport.sendto(data, (ip, COMMAND_PORT))
        else:
            logger.warning("Govee send_command called but transport is not open")

    async def discover(self, timeout_s: float = 5.0) -> list[GoveeDeviceRecord]:
        discovered: dict[str, GoveeDeviceRecord] = {}  # device_id → record

        def _scan_handler(msg_data: dict[str, Any], addr: tuple[str, int]) -> None:
            data = msg_data.get("data", {})
            device_id = data.get("device", "")
            if device_id and device_id not in discovered:
                discovered[device_id] = GoveeDeviceRecord(
                    ip=data.get("ip", addr[0]),
                    device_id=device_id,
                    sku=data.get("sku", ""),
                    wifi_version=data.get("wifiVersionSoft", ""),
                    ble_version=data.get("bleVersionSoft", ""),
                )

        self._cmd_handlers["scan"] = _scan_handler

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
        event = asyncio.Event()
        result: list[dict[str, Any]] = []
        self._pending_status[ip] = (event, result)

        try:
            await self.send_command(ip, build_status_query())
            try:
                await asyncio.wait_for(event.wait(), timeout=timeout_s)
            except TimeoutError:
                return None
            return result[0] if result else None
        finally:
            self._pending_status.pop(ip, None)

    def register_device(
        self, record: GoveeDeviceRecord, rtt_callback: Callable[[float], None]
    ) -> None:
        self._devices[record.ip] = record
        self._rtt_callbacks[record.ip] = rtt_callback

    def start_probing(self, interval_s: float = 5.0) -> None:
        if self._probe_task is None or self._probe_task.done():
            self._probe_task = asyncio.create_task(self._probe_loop(interval_s))

    def stop_probing(self) -> None:
        if self._probe_task and not self._probe_task.done():
            self._probe_task.cancel()

    async def _probe_loop(self, interval_s: float) -> None:
        while self._is_open:
            for ip in list(self._devices):
                self._probe_times[ip] = time.monotonic()
                await self.send_command(ip, build_status_query())

            await asyncio.sleep(interval_s)

            # Clean stale entries
            now = time.monotonic()
            stale = [ip for ip, t in self._probe_times.items() if now - t > interval_s]
            for ip in stale:
                self._probe_times.pop(ip, None)

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

        # Handle devStatus responses for query_status and probing
        if cmd == "devStatus":
            self._handle_status_response(inner, addr)

    def _handle_status_response(self, msg: dict[str, Any], addr: tuple[str, int]) -> None:
        ip = addr[0]

        # Check pending query_status calls first
        pending = self._pending_status.get(ip)
        if pending:
            event, result = pending
            result.append(msg.get("data", {}))
            event.set()
            return

        # Otherwise, it's a probe response — measure RTT
        send_time = self._probe_times.pop(ip, None)
        if send_time is not None:
            rtt_ms = (time.monotonic() - send_time) * 1000.0
            callback = self._rtt_callbacks.get(ip)
            if callback:
                callback(rtt_ms)
                logger.trace("Govee RTT for {}: {:.1f}ms", ip, rtt_ms)


class _GoveeUDPProtocol(asyncio.DatagramProtocol):
    def __init__(self, owner: GoveeTransport) -> None:
        self._owner = owner

    def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
        self._owner._on_datagram_received(data, addr)

    def error_received(self, exc: Exception) -> None:
        logger.warning("Govee UDP error: {}", exc)
