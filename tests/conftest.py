from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.devices.capabilities import DeviceCapabilities, LightReading
from dj_ledfx.spatial.geometry import DeviceGeometry
from dj_ledfx.types import DeviceInfo


class MockDeviceAdapter(DeviceAdapter):
    """Concrete DeviceAdapter for tests. Tracks all calls for assertions."""

    def __init__(
        self,
        name: str = "TestDevice",
        led_count: int = 10,
        connected: bool = True,
        supports_probing: bool = True,
        geometry: DeviceGeometry | None = None,
    ) -> None:
        self._name = name
        self._led_count = led_count
        self._connected = connected
        self.supports_latency_probing = supports_probing
        self._geometry = geometry
        self.send_frame_calls: list[NDArray[np.uint8]] = []
        self.connect_count = 0
        self.disconnect_count = 0

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            name=self._name,
            device_type="mock",
            led_count=self._led_count,
            address="mock",
        )

    @property
    def is_connected(self) -> bool:
        return self._connected

    @is_connected.setter
    def is_connected(self, value: bool) -> None:
        self._connected = value

    @property
    def led_count(self) -> int:
        return self._led_count

    @property
    def geometry(self) -> DeviceGeometry | None:
        return self._geometry

    async def connect(self) -> None:
        self.connect_count += 1
        self._connected = True

    async def disconnect(self) -> None:
        self.disconnect_count += 1
        self._connected = False

    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        self.send_frame_calls.append(colors.copy())


class FakeLight(DeviceAdapter):
    """A light that records what the app asks of it. Power and colour are readable."""

    supports_latency_probing = False

    def __init__(
        self,
        stable_id: str,
        *,
        name: str | None = None,
        led_count: int = 4,
        caps: DeviceCapabilities | None = None,
        power: bool | None = True,
        colour: tuple[int, int, int] | None = (255, 200, 150),
        captured: bytes | None = b"before",
        connected: bool = True,
        geometry: DeviceGeometry | None = None,
    ) -> None:
        self.stable_id = stable_id
        self.name = name or stable_id
        self._led_count = led_count
        self._caps = caps or DeviceCapabilities(protocol="LIFX")
        self.power = power
        self.colour = colour
        self.captured = captured
        self.connected = connected
        self._geometry = geometry
        self.firmware_running = False
        self.reject_firmware = False
        self.calls: list[tuple[str, object]] = []
        self.frames: list[NDArray[np.uint8]] = []

    @property
    def device_info(self) -> DeviceInfo:
        backend = self._caps.protocol.lower()
        return DeviceInfo(
            name=self.name,
            device_type=backend,
            led_count=self._led_count,
            address=f"fake://{self.stable_id}",
            stable_id=self.stable_id,
            backend=backend,
        )

    @property
    def is_connected(self) -> bool:
        return self.connected

    @property
    def led_count(self) -> int:
        return self._led_count

    @property
    def geometry(self) -> DeviceGeometry | None:
        return self._geometry

    @property
    def capabilities(self) -> DeviceCapabilities:
        return self._caps

    async def connect(self) -> None:
        self.connected = True

    async def disconnect(self) -> None:
        self.connected = False

    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        self.frames.append(colors.copy())

    async def capture_state(self) -> bytes | None:
        self.calls.append(("capture", None))
        return self.captured

    async def restore_state(self, state: bytes) -> None:
        self.calls.append(("restore", state))

    async def read_light(self) -> LightReading:
        return LightReading(power=self.power, colour=self.colour)

    async def set_power(self, on: bool) -> None:
        self.calls.append(("power", on))
        self.power = on

    async def prepare_stream(self) -> None:
        self.calls.append(("prepare_stream", None))

    def names(self) -> list[str]:
        return [name for name, _ in self.calls]
