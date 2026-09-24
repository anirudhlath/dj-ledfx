"""GhostAdapter — placeholder for offline devices."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.spatial.geometry import DeviceGeometry
from dj_ledfx.types import DeviceInfo


class GhostAdapter(DeviceAdapter):
    """Placeholder adapter for offline devices.

    Retains device metadata (name, LED count, stable_id) without any real
    connection. Used to represent known devices that are currently unreachable.
    All frame sends raise ConnectionError to prevent silent drops.
    """

    supports_latency_probing = False

    def __init__(
        self,
        device_info: DeviceInfo,
        led_count: int,
        *,
        caps: DeviceCapabilities | None = None,
        geometry: DeviceGeometry | None = None,
    ) -> None:
        self._device_info = device_info
        self._led_count = led_count
        self._caps = caps
        self._geometry = geometry

    @property
    def capabilities(self) -> DeviceCapabilities:
        """What the light could do when it was last seen, else a guess from its type."""
        return self._caps if self._caps is not None else super().capabilities

    @property
    def geometry(self) -> DeviceGeometry | None:
        return self._geometry

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
        raise ConnectionError(f"Device '{self._device_info.name}' is offline — cannot send frames")
