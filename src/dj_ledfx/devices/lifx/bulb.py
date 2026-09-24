from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.devices.lifx.base import LifxAdapterBase
from dj_ledfx.devices.lifx.packet import SET_COLOR, build_set_color, rgb_to_hsbk
from dj_ledfx.spatial.geometry import DeviceGeometry, PointGeometry
from dj_ledfx.types import DeviceInfo

if TYPE_CHECKING:
    from dj_ledfx.devices.lifx.transport import LifxTransport


class LifxBulbAdapter(LifxAdapterBase):
    def __init__(
        self,
        transport: LifxTransport,
        device_info: DeviceInfo,
        target_mac: bytes,
        kelvin: int = 3500,
        *,
        caps: DeviceCapabilities | None = None,
    ) -> None:
        super().__init__(
            transport,
            device_info,
            target_mac,
            kelvin=kelvin,
            caps=caps or DeviceCapabilities(protocol="LIFX"),
        )

    @property
    def led_count(self) -> int:
        return 1

    @property
    def geometry(self) -> DeviceGeometry:
        return PointGeometry()

    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        r, g, b = int(colors[0, 0]), int(colors[0, 1]), int(colors[0, 2])
        self._send(SET_COLOR, build_set_color(rgb_to_hsbk(r, g, b, kelvin=self._kelvin)))
