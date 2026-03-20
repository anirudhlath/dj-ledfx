from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from loguru import logger
from numpy.typing import NDArray

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.devices.govee.protocol import (
    build_brightness_message,
    build_solid_color_message,
    build_turn_message,
)
from dj_ledfx.devices.govee.types import GoveeDeviceRecord
from dj_ledfx.types import DeviceInfo

if TYPE_CHECKING:
    from dj_ledfx.devices.govee.transport import GoveeTransport


class GoveeSolidAdapter(DeviceAdapter):
    """DeviceAdapter for Govee devices that support whole-device solid color control."""

    supports_latency_probing = False

    def __init__(self, transport: GoveeTransport, record: GoveeDeviceRecord) -> None:
        self._transport = transport
        self._record = record
        self._is_connected = False

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            name=f"Govee {self._record.sku} ({self._record.ip})",
            device_type="govee_solid",
            led_count=1,
            address=f"{self._record.ip}:4003",
            stable_id=f"govee:{self._record.device_id}",
        )

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def led_count(self) -> int:
        return 1

    async def connect(self) -> None:
        status = await self._transport.query_status(self._record.ip)
        if status is None:
            msg = f"Govee device {self._record.ip} ({self._record.sku}) not reachable"
            raise ConnectionError(msg)
        # Ensure device is on and at full brightness for LED effects
        if not status.get("onOff"):
            logger.info("Turning on Govee device {}", self._record.ip)
            await self._transport.send_command(self._record.ip, build_turn_message(on=True))
        await self._transport.send_command(self._record.ip, build_brightness_message(100))
        self._is_connected = True

    async def disconnect(self) -> None:
        self._is_connected = False

    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        r, g, b = int(colors[0, 0]), int(colors[0, 1]), int(colors[0, 2])
        msg = build_solid_color_message(r, g, b)
        try:
            await self._transport.send_command(self._record.ip, msg)
        except OSError:
            self._is_connected = False
            logger.warning("Govee send_frame failed for {}", self._record.ip)
