from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.spatial.geometry import DeviceGeometry
from dj_ledfx.types import DeviceInfo


class DeviceAdapter(ABC):
    """Abstract base class for LED device adapters.

    Each adapter must implement connect/disconnect/send_frame and device properties.
    discover() is deliberately excluded — discovery mechanisms differ fundamentally
    between device types (TCP for OpenRGB, UDP broadcast for Govee/LIFX).
    """

    supports_latency_probing: bool = True

    @property
    @abstractmethod
    def device_info(self) -> DeviceInfo: ...

    @property
    @abstractmethod
    def is_connected(self) -> bool: ...

    @property
    @abstractmethod
    def led_count(self) -> int: ...

    @property
    def geometry(self) -> DeviceGeometry | None:
        """Optional: report device's physical geometry for spatial mapping."""
        return None

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def send_frame(self, colors: NDArray[np.uint8]) -> None: ...

    async def capture_state(self) -> bytes:
        """Capture current device state. Default: 50% white."""
        return np.full((self.led_count, 3), 128, dtype=np.uint8).tobytes()

    async def restore_state(self, state: bytes) -> None:
        """Restore device to a previously captured state. Default: send as RGB frame."""
        colors = np.frombuffer(state, dtype=np.uint8).reshape(-1, 3)
        await self.send_frame(colors)
