from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import ClassVar

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.devices.capabilities import DeviceCapabilities, LightReading, protocol_of
from dj_ledfx.spatial.geometry import DeviceGeometry
from dj_ledfx.types import DeviceInfo


class DeviceAdapter(ABC):
    """Abstract base class for LED device adapters.

    Each adapter must implement connect/disconnect/send_frame and device properties.
    discover() is deliberately excluded — discovery mechanisms differ fundamentally
    between device types (TCP for OpenRGB, UDP broadcast for Govee/LIFX).
    """

    _send_lock: asyncio.Lock | None = None
    # The most frames a second this kind of light takes; None: no cap of its own.
    stream_fps_cap: ClassVar[float | None] = None
    _max_fps: float | None = None  # the configured rate it was built with, if any

    @property
    def send_lock(self) -> asyncio.Lock:
        """Held while a frame is sent and while the light is changed back: the scheduler
        checks the route again once it holds it, so no frame lands after a restore."""
        if self._send_lock is None:
            self._send_lock = asyncio.Lock()
        return self._send_lock

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
    def stream_fps(self) -> float | None:
        """The most frames a second it streams: the configured rate it was built with,
        within its kind's cap. None: the scheduler's rate."""
        rates = [rate for rate in (self._max_fps, self.stream_fps_cap) if rate is not None]
        return min(rates, default=None)

    @property
    def display_ms(self) -> float:
        """How long after a frame lands the light shows it. Default: at once."""
        return 0.0

    @property
    def last_heard(self) -> float | None:
        """When the light last answered anything, on time.monotonic's clock. None: never
        heard, or the protocol can't tell (the default)."""
        return None

    @property
    def geometry(self) -> DeviceGeometry | None:
        """Optional: report device's physical geometry for spatial mapping."""
        return None

    @property
    def capabilities(self) -> DeviceCapabilities:
        """What the light can do. Default: a streamed-only colour light."""
        info = self.device_info
        return DeviceCapabilities(protocol=protocol_of(info.backend or info.device_type))

    async def read_light(self) -> LightReading:
        """Read power and colour without changing anything. Raises when the light doesn't
        answer. Default: unknown."""
        return LightReading.UNKNOWN

    async def set_power(self, on: bool) -> None:  # noqa: B027
        """Switch the light on or off. Default: the protocol can't, so do nothing."""

    async def prepare_stream(self) -> None:  # noqa: B027
        """Get the light ready for streamed frames (stop its own effects, pick direct mode)."""

    @abstractmethod
    async def connect(self) -> None: ...

    @abstractmethod
    async def disconnect(self) -> None: ...

    @abstractmethod
    async def send_frame(self, colors: NDArray[np.uint8]) -> None: ...

    async def capture_state(self) -> bytes | None:
        """Capture how the light looks now, to put it back on Off. None: can't capture."""
        return None

    async def restore_state(self, state: bytes, *, power: bool = True) -> None:
        """Put the light back as captured. power=False: it reads off now, so restore only
        what doesn't switch it on (spec §6.4). Default: send the bytes as an RGB frame,
        and nothing without power, since a frame may switch a light on."""
        if not power:
            return
        colors = np.frombuffer(state, dtype=np.uint8).reshape(-1, 3)
        await self.send_frame(colors)
