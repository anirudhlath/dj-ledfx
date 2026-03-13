from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np
from numpy.typing import NDArray

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

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def send_frame(self, colors: NDArray[np.uint8]) -> None: ...
