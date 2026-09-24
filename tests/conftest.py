from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.devices.capabilities import (
    DeviceCapabilities,
    FirmwareRejected,
    LightReading,
    NoAnswer,
)
from dj_ledfx.effects.context import RenderContext
from dj_ledfx.effects.firmware import FirmwareEffect, Params
from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.spatial.geometry import DeviceGeometry
from dj_ledfx.types import DeviceInfo, FloatRGB


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


@dataclass
class Hold:
    """A call held part-way: entered is set when it starts, and it ends on release."""

    entered: asyncio.Event = field(default_factory=asyncio.Event)
    release: asyncio.Event = field(default_factory=asyncio.Event)


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
        self.silent_firmware = False  # firmware commands get no answer
        self.silent = False  # reads get no answer (it's unplugged, or cut at the wall)
        self.firmware_checks = 0  # how often the app asked whether its effect still runs
        self._holds: dict[str, Hold] = {}
        self._power_at_capture: bool | None = None
        self.calls: list[tuple[str, object]] = []
        self.frames: list[NDArray[np.uint8]] = []
        self.record_frames = False  # log frames in calls too, to check what came first
        # Called whenever the app asks the light something: the fake scheduler sends
        # frames down the streaming routes then, as the real one does meanwhile.
        self.on_io: Callable[[], None] | None = None

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
        self.receive_frame(colors)

    def receive_frame(self, colors: NDArray[np.uint8]) -> None:
        self.frames.append(colors.copy())
        if self.record_frames:
            self.calls.append(("frame", None))

    def io(self) -> None:
        if self.on_io is not None:
            self.on_io()

    def hold(self, call: str) -> Hold:
        """Hold the next read_light or is_running part-way, with what it saw already."""
        self._holds[call] = Hold()
        return self._holds[call]

    async def wait_if_held(self, call: str) -> None:
        hold = self._holds.pop(call, None)
        if hold is not None:
            hold.entered.set()
            await hold.release.wait()

    async def capture_state(self) -> bytes | None:
        self.io()
        self.calls.append(("capture", None))
        self._power_at_capture = self.power
        return self.captured

    async def restore_state(self, state: bytes, *, power: bool = True) -> None:
        self.io()
        self.calls.append(("restore" if power else "restore_off", state))
        if power and self._power_at_capture is not None:
            self.power = self._power_at_capture  # a restore puts power back too

    async def read_light(self) -> LightReading:
        self.io()
        if self.silent:
            raise NoAnswer(f"{self.name} didn't answer")
        reading = LightReading(power=self.power, colour=self.colour)
        await self.wait_if_held("read_light")
        return reading

    async def set_power(self, on: bool) -> None:
        self.io()
        self.calls.append(("power", on))
        self.power = on

    async def prepare_stream(self) -> None:
        self.io()
        self.calls.append(("prepare_stream", None))

    def names(self) -> list[str]:
        return [name for name, _ in self.calls]


class GlowFirmware(FirmwareEffect):
    """A firmware effect for FakeLights whose capabilities have matrix=True."""

    display_name = "Glow"

    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {"level": EffectParam(type="float", default=0.5, min=0.0, max=1.0)}

    def __init__(self, level: float = 0.5) -> None:
        self.level = level

    def get_params(self) -> dict[str, Any]:
        return {"level": self.level}

    def _apply_params(self, **kwargs: Any) -> None:
        self.level = float(kwargs.get("level", self.level))

    def supports(self, caps: DeviceCapabilities) -> bool:
        return caps.matrix

    # cast, not isinstance: pytest imports this file twice (as tests.conftest and as
    # conftest), so a FakeLight may come from either copy.
    async def start(self, adapter: DeviceAdapter, params: Params) -> None:
        light = cast(FakeLight, adapter)
        light.io()
        if light.silent_firmware:
            raise NoAnswer(f"{light.name} didn't answer")
        if light.reject_firmware:
            raise FirmwareRejected(f"{light.name} refused Glow")
        light.calls.append(("firmware", dict(params)))
        light.firmware_running = True

    async def stop(self, adapter: DeviceAdapter) -> None:
        light = cast(FakeLight, adapter)
        light.calls.append(("firmware_stop", None))
        light.firmware_running = False

    async def is_running(self, adapter: DeviceAdapter) -> bool | None:
        light = cast(FakeLight, adapter)
        light.firmware_checks += 1
        running = light.firmware_running
        await light.wait_if_held("is_running")
        return running

    def emulate(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        return np.full((leds.count, 3), self.level, dtype=np.float32)
