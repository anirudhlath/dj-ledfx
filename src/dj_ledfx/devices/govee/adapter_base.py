from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.devices.govee.protocol import (
    build_brightness_message,
    build_solid_color_message,
    build_turn_message,
)
from dj_ledfx.devices.govee.state import GoveeDeviceState
from dj_ledfx.devices.govee.types import GoveeDeviceRecord

if TYPE_CHECKING:
    from dj_ledfx.devices.govee.transport import GoveeTransport


class GoveeAdapterBase(DeviceAdapter):
    """Shared base for Govee adapters — connect, disconnect, state capture/restore."""

    supports_latency_probing = False

    def __init__(self, transport: GoveeTransport, record: GoveeDeviceRecord) -> None:
        self._transport = transport
        self._record = record
        self._is_connected = False
        self._original_state: GoveeDeviceState | None = None

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    async def connect(self) -> None:
        status = await self._transport.query_status(self._record.ip)
        if status is None:
            msg = f"Govee device {self._record.ip} ({self._record.sku}) not reachable"
            raise ConnectionError(msg)
        self._original_state = GoveeDeviceState.from_status(status)
        if not status.get("onOff"):
            logger.info("Turning on Govee device {}", self._record.ip)
            await self._transport.send_command(self._record.ip, build_turn_message(on=True))
        await self._transport.send_command(self._record.ip, build_brightness_message(100))
        self._is_connected = True

    async def disconnect(self) -> None:
        self._is_connected = False

    async def capture_state(self) -> bytes:
        if self._original_state is not None:
            return self._original_state.to_bytes()
        return await super().capture_state()

    async def restore_state(self, state: bytes) -> None:
        saved = GoveeDeviceState.from_bytes(state)
        ip = self._record.ip
        await self._transport.send_command(
            ip, build_solid_color_message(saved.r, saved.g, saved.b)
        )
        await self._transport.send_command(ip, build_brightness_message(saved.brightness))
        # Turn off last so color/brightness are set while device is still on
        if not saved.on_off:
            await self._transport.send_command(ip, build_turn_message(on=False))
