from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from dj_ledfx.devices.capabilities import FirmwareRejected, LightReading
from dj_ledfx.devices.openrgb import HAS_BRIGHTNESS, HAS_PER_LED_COLOR, OpenRGBAdapter


def _mode(name: str, *, brightness: bool = False, per_led: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        flags=(HAS_BRIGHTNESS if brightness else 0) | (HAS_PER_LED_COLOR if per_led else 0),
        brightness=100 if brightness else None,
        brightness_min=0 if brightness else None,
        brightness_max=100 if brightness else None,
    )


def _device() -> MagicMock:
    device = MagicMock()
    device.name = "SteelSeries Apex Pro TKL"
    device.modes = [
        _mode("Direct", per_led=True),
        _mode("Static", per_led=True),
        _mode("Rainbow Wave", brightness=True),
    ]
    device.active_mode = 1
    device.colors = [
        SimpleNamespace(red=10, green=20, blue=30),
        SimpleNamespace(red=0, green=0, blue=0),
    ]
    return device


async def _connected(device: MagicMock) -> OpenRGBAdapter:
    with patch("dj_ledfx.devices.openrgb.OpenRGBClient") as client_cls:
        client_cls.return_value = MagicMock(devices=[device])
        adapter = OpenRGBAdapter(device_index=0)
        await adapter.connect()
    return adapter


async def test_connect_leaves_the_mode_alone() -> None:
    device = _device()
    await _connected(device)
    device.set_mode.assert_not_called()


async def test_prepare_stream_picks_direct_and_frames_leave_the_mode_alone() -> None:
    device = _device()
    adapter = await _connected(device)
    await adapter.send_frame(np.zeros((2, 3), dtype=np.uint8))
    device.set_mode.assert_not_called()  # the zone manager prepares it before any frame
    await adapter.prepare_stream()
    await adapter.send_frame(np.zeros((2, 3), dtype=np.uint8))
    device.set_mode.assert_called_once_with("Direct")
    assert device.set_colors.call_count == 2


async def test_capabilities_list_the_modes() -> None:
    caps = (await _connected(_device())).capabilities
    assert caps.protocol == "OpenRGB"
    assert caps.model == "SteelSeries Apex Pro TKL"
    assert caps.openrgb_modes == ("Direct", "Static", "Rainbow Wave")


async def test_set_mode_scales_brightness_on_a_copy() -> None:
    device = _device()
    adapter = await _connected(device)
    await adapter.set_mode("rainbow wave", brightness=0.5)
    (sent,) = device.set_mode.call_args.args
    assert sent.name == "Rainbow Wave"
    assert sent.brightness == 50
    assert device.modes[2].brightness == 100


async def test_unknown_mode_is_rejected() -> None:
    adapter = await _connected(_device())
    with pytest.raises(FirmwareRejected):
        await adapter.set_mode("Plasma", brightness=1.0)


async def test_active_mode_name_reads_the_device() -> None:
    device = _device()
    adapter = await _connected(device)
    assert await adapter.active_mode_name() == "Static"
    device.update.assert_called()


async def test_capture_and_restore_mode_and_colours() -> None:
    device = _device()
    adapter = await _connected(device)
    captured = await adapter.capture_state()
    assert captured is not None
    assert json.loads(captured) == {"mode": "Static", "colors": [[10, 20, 30], [0, 0, 0]]}

    await adapter.restore_state(captured)
    device.set_mode.assert_called_once_with("Static")
    (colours,) = device.set_colors.call_args.args
    assert [(c.red, c.green, c.blue) for c in colours] == [(10, 20, 30), (0, 0, 0)]


async def test_read_light_reports_the_first_colour() -> None:
    adapter = await _connected(_device())
    assert await adapter.read_light() == LightReading(power=None, colour=(10, 20, 30))
