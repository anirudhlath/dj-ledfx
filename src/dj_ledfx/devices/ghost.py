"""GhostAdapter — placeholder for offline devices."""
from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.types import DeviceInfo


class GhostAdapter(DeviceAdapter):
    """Placeholder adapter for offline devices.

    Retains device metadata (name, LED count, stable_id) without any real
    connection. Used to represent known devices that are currently unreachable.
    All frame sends raise ConnectionError to prevent silent drops.
    """

    supports_latency_probing = False

    def __init__(self, device_info: DeviceInfo, led_count: int) -> None:
        self._device_info = device_info
        self._led_count = led_count

    @property
    def device_info(self) -> DeviceInfo:
        return self._device_info

    @property
    def is_connected(self) -> bool:
        return False

    @property
    def led_count(self) -> int:
        return self._led_count

    async def connect(self) -> None:
        pass

    async def disconnect(self) -> None:
        pass

    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        raise ConnectionError(
            f"Device '{self._device_info.name}' is offline — cannot send frames"
        )
