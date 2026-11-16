"""Default DeviceAdapter state and control hooks."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import numpy as np
import pytest
from govee_fakes import lamp_record, lamp_transport, sent
from lifx_fakes import FakeLifxTransport, lifx_bulb
from numpy.typing import NDArray
from openrgb_fakes import adapter_of

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.devices.capabilities import LightReading
from dj_ledfx.devices.govee.protocol import build_turn_message
from dj_ledfx.devices.govee.razer import GoveeRazerAdapter
from dj_ledfx.devices.openrgb import HAS_PER_LED_COLOR
from dj_ledfx.types import DeviceInfo


class FakeAdapter(DeviceAdapter):
    """Minimal concrete DeviceAdapter for testing the default hooks."""

    def __init__(self, led_count: int = 10, device_type: str = "fake") -> None:
        self._led_count = led_count
        self._device_type = device_type
        self._connected = True
        self.sent_frames: list[NDArray[np.uint8]] = []

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            name="FakeDevice",
            device_type=self._device_type,
            led_count=self._led_count,
            address="fake",
        )

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def led_count(self) -> int:
        return self._led_count

    async def connect(self) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False

    async def send_frame(self, colors: NDArray[np.uint8]) -> None:
        self.sent_frames.append(colors.copy())


@pytest.mark.asyncio
async def test_capture_state_default_is_none() -> None:
    """A light that can't be captured says so, so Off leaves it alone."""
    assert await FakeAdapter().capture_state() is None


@pytest.mark.asyncio
async def test_restore_state_default_sends_the_bytes_as_a_frame() -> None:
    adapter = FakeAdapter(led_count=3)
    state = np.array([[255, 0, 0]] * 3, dtype=np.uint8).tobytes()

    await adapter.restore_state(state)

    assert len(adapter.sent_frames) == 1
    sent = adapter.sent_frames[0]
    assert sent.shape == (3, 3)
    assert np.all(sent[:, 0] == 255) and np.all(sent[:, 1:] == 0)


@pytest.mark.asyncio
async def test_restore_state_default_without_power_sends_nothing() -> None:
    adapter = FakeAdapter(led_count=3)  # a frame could switch a switched-off light on
    await adapter.restore_state(bytes(9), power=False)
    assert adapter.sent_frames == []


def test_default_capabilities_follow_the_device_type() -> None:
    assert FakeAdapter(device_type="govee_segment").capabilities.protocol == "Govee"
    assert FakeAdapter(device_type="lifx").capabilities.protocol == "LIFX"
    assert FakeAdapter().capabilities.protocol == "OpenRGB"


@pytest.mark.asyncio
async def test_default_read_light_is_unknown() -> None:
    assert await FakeAdapter().read_light() == LightReading(power=None, colour=None)


@pytest.mark.asyncio
async def test_default_power_and_stream_hooks_do_nothing() -> None:
    adapter = FakeAdapter()
    await adapter.set_power(True)
    await adapter.prepare_stream()
    assert adapter.sent_frames == []


def test_a_light_is_never_heard_from_by_default() -> None:
    """A protocol that can't tell when a light last answered says it never has."""
    assert FakeAdapter().last_heard is None


async def test_which_lights_switch_power() -> None:
    """LIFX and Govee lights switch power on a command; the rest of the lights, OpenRGB's
    and a bare adapter, can't, so a look that has one dark for good leaves it streaming."""
    assert lifx_bulb(FakeLifxTransport()).switches_power is True
    transport = lamp_transport(can_receive=False)  # another program holds the reply port
    lamp = GoveeRazerAdapter(transport, lamp_record(), 15)
    assert lamp.switches_power is True
    await lamp.set_power(False)  # sent though the lamp can't be heard: no status needed
    assert sent(transport) == [build_turn_message(on=False)]

    device = MagicMock()
    device.name = "Test keyboard"
    device.modes = [
        SimpleNamespace(
            name="Direct",
            flags=HAS_PER_LED_COLOR,
            brightness=None,
            brightness_min=None,
            brightness_max=None,
        )
    ]
    device.active_mode = 0
    device.colors = [SimpleNamespace(red=0, green=0, blue=0)]
    assert (await adapter_of(device)).switches_power is False
    assert FakeAdapter().switches_power is False
