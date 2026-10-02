# tests/devices/govee/test_backend.py
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from govee_fakes import NO_RAZER, TEST_MODEL, UPRIGHT, lamp_row, lamp_transport

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
from dj_ledfx.devices.govee.types import GoveeDeviceCapability
from dj_ledfx.spatial.geometry import StripGeometry


@pytest.fixture
def config() -> AppConfig:
    return AppConfig()


class TestGoveeBackend:
    def test_is_enabled_default(self, config: AppConfig) -> None:
        backend = GoveeBackend()
        assert backend.is_enabled(config) is True

    def test_is_enabled_disabled(self) -> None:
        config = AppConfig(devices=DevicesConfig(govee=GoveeConfig(enabled=False)))
        backend = GoveeBackend()
        assert backend.is_enabled(config) is False

    async def test_discover_creates_segment_adapter_for_rgbic(
        self, monkeypatch: pytest.MonkeyPatch, config: AppConfig
    ) -> None:
        monkeypatch.setitem(SKU_REGISTRY, TEST_MODEL, NO_RAZER)
        backend = GoveeBackend()
        backend._transport = lamp_transport()

        results = await backend.discover(config)

        assert len(results) == 1
        assert isinstance(results[0].adapter, GoveeSegmentAdapter)

    async def test_discover_creates_solid_adapter_for_unknown(self, config: AppConfig) -> None:
        backend = GoveeBackend()
        backend._transport = lamp_transport(sku="not-a-model")

        results = await backend.discover(config)

        assert len(results) == 1
        assert isinstance(results[0].adapter, GoveeSolidAdapter)

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


async def _connect(
    config: AppConfig, sku: str = TEST_MODEL, output: dict[str, Any] | None = None
) -> DiscoveredDevice:
    backend = GoveeBackend()
    backend._transport = lamp_transport()
    (device,) = await backend.connect_known([lamp_row(sku, output)], config)
    return device


async def test_an_upright_razer_lamp_streams_each_segment_standing(
    monkeypatch: pytest.MonkeyPatch, config: AppConfig
) -> None:
    monkeypatch.setitem(SKU_REGISTRY, TEST_MODEL, UPRIGHT)
    device = await _connect(config)
    assert isinstance(device.adapter, GoveeSegmentAdapter) and device.adapter.razer
    assert device.adapter.led_count == 15
    assert device.adapter.geometry == StripGeometry((0, 1, 0), UPRIGHT_HEIGHT_M)
    assert device.max_fps == config.devices.govee.max_fps == GOVEE_RAZER_FPS


async def test_a_lamp_without_razer_plays_one_colour_at_the_colour_rate(
    monkeypatch: pytest.MonkeyPatch, config: AppConfig
) -> None:
    monkeypatch.setitem(SKU_REGISTRY, TEST_MODEL, NO_RAZER)
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


# Review Focus 5: a lamp whose own output is one colour comes back playing one colour.
async def test_a_lamp_set_to_one_colour_comes_back_in_colour(
    monkeypatch: pytest.MonkeyPatch, config: AppConfig
) -> None:
    monkeypatch.setitem(SKU_REGISTRY, TEST_MODEL, UPRIGHT)
    colour = await _connect(config, output={"mode": "colour"})
    assert isinstance(colour.adapter, GoveeSegmentAdapter) and not colour.adapter.razer
    assert colour.max_fps == GOVEE_COLOUR_FPS
    counted = await _connect(config, output={"segments": 10})
    assert isinstance(counted.adapter, GoveeSegmentAdapter) and counted.adapter.razer
    assert counted.adapter.led_count == 10


async def test_a_lamp_offline_at_the_reconnect_gets_its_output_when_a_scan_finds_it(
    monkeypatch: pytest.MonkeyPatch, config: AppConfig
) -> None:
    monkeypatch.setitem(SKU_REGISTRY, TEST_MODEL, UPRIGHT)
    backend = GoveeBackend()
    transport = lamp_transport(None)  # it doesn't answer
    backend._transport = transport
    assert await backend.connect_known([lamp_row(output={"mode": "colour"})], config) == []

    transport.query_status = AsyncMock(return_value={"onOff": 1})  # it's back
    (device,) = await backend.discover(config)

    assert isinstance(device.adapter, GoveeSegmentAdapter) and not device.adapter.razer
    assert device.max_fps == GOVEE_COLOUR_FPS
