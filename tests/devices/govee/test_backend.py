# tests/devices/govee/test_backend.py
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dj_ledfx.config import (
    GOVEE_COLOUR_FPS,
    GOVEE_RAZER_FPS,
    AppConfig,
    DevicesConfig,
    GoveeConfig,
)
from dj_ledfx.devices.backend import DiscoveredDevice
from dj_ledfx.devices.govee.backend import GoveeBackend
from dj_ledfx.devices.govee.segment import UPRIGHT_HEIGHT_M, GoveeSegmentAdapter
from dj_ledfx.devices.govee.sku_registry import SKU_REGISTRY
from dj_ledfx.devices.govee.solid import GoveeSolidAdapter
from dj_ledfx.devices.govee.types import GoveeDeviceCapability, GoveeDeviceRecord
from dj_ledfx.spatial.geometry import StripGeometry


@pytest.fixture
def config() -> AppConfig:
    return AppConfig()


@pytest.fixture
def rgbic_record() -> GoveeDeviceRecord:
    return GoveeDeviceRecord(
        ip="192.168.1.10",
        device_id="AA:BB:CC:DD:EE:FF:00:11",
        sku="H6076",
        wifi_version="1.00.00",
        ble_version="1.00.00",
    )


@pytest.fixture
def unknown_record() -> GoveeDeviceRecord:
    return GoveeDeviceRecord(
        ip="192.168.1.20",
        device_id="11:22:33:44:55:66:77:88",
        sku="H9999",
        wifi_version="1.00.00",
        ble_version="1.00.00",
    )


class TestGoveeBackend:
    def test_is_enabled_default(self, config: AppConfig) -> None:
        backend = GoveeBackend()
        assert backend.is_enabled(config) is True

    def test_is_enabled_disabled(self) -> None:
        config = AppConfig(devices=DevicesConfig(govee=GoveeConfig(enabled=False)))
        backend = GoveeBackend()
        assert backend.is_enabled(config) is False

    @pytest.mark.asyncio
    async def test_discover_creates_segment_adapter_for_rgbic(
        self, config: AppConfig, rgbic_record: GoveeDeviceRecord
    ) -> None:
        backend = GoveeBackend()
        with patch("dj_ledfx.devices.govee.backend.GoveeTransport") as MockTransport:
            mock_transport = MagicMock()
            mock_transport.open = AsyncMock()
            mock_transport.is_open = True

            async def _fake_discover(
                timeout_s: float = 10.0, on_record: object = None
            ) -> list[GoveeDeviceRecord]:
                if callable(on_record):
                    on_record(rgbic_record)
                return [rgbic_record]

            mock_transport.discover = _fake_discover
            mock_transport.query_status = AsyncMock(return_value={"onOff": 1})
            mock_transport.send_command = AsyncMock()
            mock_transport.register_device = MagicMock()
            mock_transport.start_probing = MagicMock()
            MockTransport.return_value = mock_transport

            results = await backend.discover(config)

        assert len(results) == 1
        assert isinstance(results[0].adapter, GoveeSegmentAdapter)
        assert results[0].adapter.razer  # the first entry plays razer (ruling 12)
        assert results[0].max_fps == config.devices.govee.max_fps

    @pytest.mark.asyncio
    async def test_discover_creates_solid_adapter_for_unknown(
        self, config: AppConfig, unknown_record: GoveeDeviceRecord
    ) -> None:
        backend = GoveeBackend()
        with patch("dj_ledfx.devices.govee.backend.GoveeTransport") as MockTransport:
            mock_transport = MagicMock()
            mock_transport.open = AsyncMock()
            mock_transport.is_open = True

            async def _fake_discover(
                timeout_s: float = 10.0, on_record: object = None
            ) -> list[GoveeDeviceRecord]:
                if callable(on_record):
                    on_record(unknown_record)
                return [unknown_record]

            mock_transport.discover = _fake_discover
            mock_transport.query_status = AsyncMock(return_value={"onOff": 1})
            mock_transport.send_command = AsyncMock()
            mock_transport.register_device = MagicMock()
            mock_transport.start_probing = MagicMock()
            MockTransport.return_value = mock_transport

            results = await backend.discover(config)

        assert len(results) == 1
        assert isinstance(results[0].adapter, GoveeSolidAdapter)
        assert results[0].max_fps == GOVEE_COLOUR_FPS

    @pytest.mark.asyncio
    async def test_shutdown_stops_probing_and_closes(self) -> None:
        backend = GoveeBackend()
        mock_transport = MagicMock()
        mock_transport.stop_probing = MagicMock()
        mock_transport.close = AsyncMock()
        backend._transport = mock_transport

        await backend.shutdown()

        mock_transport.stop_probing.assert_called_once()
        mock_transport.close.assert_awaited_once()


TEST_MODEL = "test-model"


def _lamp_row(sku: str = TEST_MODEL) -> dict[str, Any]:
    return {
        "id": "govee:test-lamp",
        "name": "Test lamp",
        "backend": "govee",
        "ip": "127.0.0.1",
        "device_id": "test-lamp",
        "sku": sku,
    }


async def _connect(config: AppConfig, sku: str = TEST_MODEL) -> DiscoveredDevice:
    transport = MagicMock()
    transport.is_open = True
    transport.can_receive = True
    transport.query_status = AsyncMock(return_value={"onOff": 1})
    transport.send_command = AsyncMock()
    backend = GoveeBackend()
    backend._transport = transport
    (device,) = await backend.connect_known([_lamp_row(sku)], config)
    return device


async def test_an_upright_razer_lamp_streams_each_segment_standing(
    monkeypatch: pytest.MonkeyPatch, config: AppConfig
) -> None:
    upright = GoveeDeviceCapability(is_rgbic=True, segment_count=15, razer=True, form="upright")
    monkeypatch.setitem(SKU_REGISTRY, TEST_MODEL, upright)
    device = await _connect(config)
    assert isinstance(device.adapter, GoveeSegmentAdapter) and device.adapter.razer
    assert device.adapter.led_count == 15
    assert device.adapter.geometry == StripGeometry((0, 1, 0), UPRIGHT_HEIGHT_M)
    assert device.max_fps == config.devices.govee.max_fps == GOVEE_RAZER_FPS


async def test_a_lamp_without_razer_plays_one_colour_at_the_colour_rate(
    monkeypatch: pytest.MonkeyPatch, config: AppConfig
) -> None:
    no_razer = GoveeDeviceCapability(is_rgbic=True, segment_count=15)
    monkeypatch.setitem(SKU_REGISTRY, TEST_MODEL, no_razer)
    device = await _connect(config)
    assert isinstance(device.adapter, GoveeSegmentAdapter) and not device.adapter.razer
    assert device.max_fps == GOVEE_COLOUR_FPS


async def test_an_unknown_model_is_one_colour_at_the_colour_rate(config: AppConfig) -> None:
    device = await _connect(config, sku="not-a-model")
    assert isinstance(device.adapter, GoveeSolidAdapter)
    assert device.max_fps == GOVEE_COLOUR_FPS


async def test_the_config_s_segment_count_applies_to_an_rgbic_lamp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capability = GoveeDeviceCapability(is_rgbic=True, segment_count=15, razer=True)
    monkeypatch.setitem(SKU_REGISTRY, TEST_MODEL, capability)
    config = AppConfig(devices=DevicesConfig(govee=GoveeConfig(segment_override=10)))
    device = await _connect(config)
    assert device.adapter.led_count == 10
