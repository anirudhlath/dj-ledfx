from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from loguru import logger
from numpy.typing import NDArray

from dj_ledfx.devices.govee.adapter_base import GoveeAdapterBase
from dj_ledfx.devices.govee.protocol import build_solid_color_message
from dj_ledfx.devices.govee.types import GoveeDeviceRecord
from dj_ledfx.spatial.geometry import DeviceGeometry, PointGeometry
from dj_ledfx.types import DeviceInfo

if TYPE_CHECKING:
    from dj_ledfx.devices.govee.transport import GoveeTransport


class GoveeSolidAdapter(GoveeAdapterBase):
    """DeviceAdapter for Govee devices that support whole-device solid color control."""

    def __init__(self, transport: GoveeTransport, record: GoveeDeviceRecord) -> None:
        super().__init__(transport, record)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            name=f"Govee {self._record.sku} ({self._record.ip})",
            device_type="govee_solid",
            led_count=1,
            address=f"{self._record.ip}:4003",
            stable_id=f"govee:{self._record.device_id}",
            backend="govee",
        )

    @property
    def led_count(self) -> int:
        return 1

    @property
    def geometry(self) -> DeviceGeometry:
        return PointGeometry()

    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        r, g, b = int(colors[0, 0]), int(colors[0, 1]), int(colors[0, 2])
        msg = build_solid_color_message(r, g, b)
        try:
            await self._transport.send_command(self._record.ip, msg)
        except OSError:
            self._is_connected = False
            logger.warning("Govee send_frame failed for {}", self._record.ip)
