# tests/devices/lifx/test_discovery.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dj_ledfx.config import AppConfig, DevicesConfig, LIFXConfig
from dj_ledfx.devices.lifx.bulb import LifxBulbAdapter
from dj_ledfx.devices.lifx.discovery import (
    LifxBackend,
)
from dj_ledfx.devices.lifx.strip import LifxStripAdapter
from dj_ledfx.devices.lifx.tile_chain import LifxTileChainAdapter
from dj_ledfx.devices.lifx.types import LifxDeviceRecord


def test_is_enabled_checks_config() -> None:
    backend = LifxBackend()
    assert (
        backend.is_enabled(AppConfig(devices=DevicesConfig(lifx=LIFXConfig(enabled=True)))) is True
    )
    assert (
        backend.is_enabled(AppConfig(devices=DevicesConfig(lifx=LIFXConfig(enabled=False))))
        is False
    )


@pytest.mark.asyncio
async def test_classify_tile_product() -> None:
    mock_transport = MagicMock()
    mock_transport.source_id = 12345
    mock_transport.next_sequence = MagicMock(return_value=1)
    mock_transport.request_response = AsyncMock(return_value=None)

    backend = LifxBackend()
    backend._transport = mock_transport
    config = AppConfig()
    record = LifxDeviceRecord(mac=b"\x00" * 6, ip="1.2.3.4", port=56700, vendor=1, product=55)
    adapter = await backend._create_adapter(record, config)
    assert isinstance(adapter, LifxTileChainAdapter)


@pytest.mark.asyncio
async def test_classify_strip_product() -> None:
    mock_transport = MagicMock()
    mock_transport.source_id = 12345
    mock_transport.next_sequence = MagicMock(return_value=1)
    mock_transport.request_response = AsyncMock(return_value=None)

    backend = LifxBackend()
    backend._transport = mock_transport
    config = AppConfig()
    record = LifxDeviceRecord(mac=b"\x00" * 6, ip="1.2.3.4", port=56700, vendor=1, product=31)
    adapter = await backend._create_adapter(record, config)
    assert isinstance(adapter, LifxStripAdapter)


@pytest.mark.asyncio
async def test_classify_bulb_product() -> None:
    mock_transport = MagicMock()
    mock_transport.source_id = 12345
    mock_transport.next_sequence = MagicMock(return_value=1)

    backend = LifxBackend()
    backend._transport = mock_transport
    config = AppConfig()
    record = LifxDeviceRecord(mac=b"\x00" * 6, ip="1.2.3.4", port=56700, vendor=1, product=1)
    adapter = await backend._create_adapter(record, config)
    assert isinstance(adapter, LifxBulbAdapter)


@pytest.mark.asyncio
async def test_discover_returns_discovered_devices() -> None:
    mock_transport = MagicMock()
    mock_transport.open = AsyncMock()
    mock_transport.discover = AsyncMock(
        return_value=[
            LifxDeviceRecord(mac=b"\xaa" * 6, ip="1.2.3.4", port=56700, vendor=1, product=1),
        ]
    )
    mock_transport.register_device = MagicMock()
    mock_transport.start_probing = MagicMock()
    mock_transport.source_id = 12345
    mock_transport.next_sequence = MagicMock(return_value=1)

    with patch("dj_ledfx.devices.lifx.discovery.LifxTransport", return_value=mock_transport):
        backend = LifxBackend()
        config = AppConfig()
        devices = await backend.discover(config)

    assert len(devices) == 1
    assert isinstance(devices[0].adapter, LifxBulbAdapter)
    assert devices[0].max_fps == config.devices.lifx.max_fps
    mock_transport.register_device.assert_called_once()
    mock_transport.start_probing.assert_called_once()
