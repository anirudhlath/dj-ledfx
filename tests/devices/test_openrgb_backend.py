from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dj_ledfx.config import AppConfig, DevicesConfig, OpenRGBConfig
from dj_ledfx.devices.openrgb_backend import OpenRGBBackend


def test_is_enabled_checks_config() -> None:
    backend = OpenRGBBackend()
    assert (
        backend.is_enabled(AppConfig(devices=DevicesConfig(openrgb=OpenRGBConfig(enabled=True))))
        is True
    )
    assert (
        backend.is_enabled(AppConfig(devices=DevicesConfig(openrgb=OpenRGBConfig(enabled=False))))
        is False
    )


@pytest.mark.asyncio
async def test_discover_returns_connected_adapters() -> None:
    mock_info = MagicMock(name="TestDevice", led_count=10)
    mock_adapter = MagicMock()
    mock_adapter.is_connected = True
    mock_adapter.device_info = mock_info
    mock_adapter.device_info.name = "TestDevice"
    mock_adapter.led_count = 10
    mock_adapter.connect = AsyncMock()

    with patch("dj_ledfx.devices.openrgb_backend.OpenRGBAdapter") as MockAdapter:
        MockAdapter.discover = AsyncMock(return_value=[mock_info])
        MockAdapter.return_value = mock_adapter
        backend = OpenRGBBackend()
        config = AppConfig()
        devices = await backend.discover(config)
        assert len(devices) == 1
        assert devices[0].adapter is mock_adapter
        assert devices[0].max_fps == config.devices.openrgb.max_fps
