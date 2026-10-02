# tests/devices/govee/test_backend.py
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from govee_fakes import NO_RAZER, TEST_MODEL, UPRIGHT, lamp_row, lamp_transport, sent
from loguru import logger

from dj_ledfx.config import (
    GOVEE_COLOUR_FPS,
    GOVEE_RAZER_FPS,
    AppConfig,
    DevicesConfig,
    GoveeConfig,
)
from dj_ledfx.devices.backend import DiscoveredDevice
from dj_ledfx.devices.govee.adapter_base import UPRIGHT_HEIGHT_M
from dj_ledfx.devices.govee.backend import GoveeBackend
from dj_ledfx.devices.govee.colour import GoveeColourAdapter
from dj_ledfx.devices.govee.protocol import build_brightness_message, build_razer_switch
from dj_ledfx.devices.govee.razer import GoveeRazerAdapter
from dj_ledfx.devices.govee.sku_registry import SKU_REGISTRY
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

    async def test_discover_sets_up_a_lamp_without_razer_in_one_colour(
        self, monkeypatch: pytest.MonkeyPatch, config: AppConfig
    ) -> None:
        monkeypatch.setitem(SKU_REGISTRY, TEST_MODEL, NO_RAZER)
        backend = GoveeBackend()
        backend._transport = lamp_transport()

        results = await backend.discover(config)

        assert len(results) == 1
        assert isinstance(results[0].adapter, GoveeColourAdapter)  # NO_RAZER: one colour

    async def test_discover_sets_up_an_unknown_model_in_one_colour(
        self, config: AppConfig
    ) -> None:
        backend = GoveeBackend()
        backend._transport = lamp_transport(sku="not-a-model")

        results = await backend.discover(config)

        assert len(results) == 1
        assert isinstance(results[0].adapter, GoveeColourAdapter)

    async def test_shutdown_closes_the_transport(self) -> None:
        backend = GoveeBackend()
        mock_transport = MagicMock()
        mock_transport.close = AsyncMock()
        backend._transport = mock_transport

        await backend.shutdown()

        mock_transport.close.assert_awaited_once()
        assert backend._transport is None


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
    assert isinstance(device.adapter, GoveeRazerAdapter)
    assert device.adapter.led_count == 15
    assert device.adapter.geometry == StripGeometry((0, 1, 0), UPRIGHT_HEIGHT_M)
    assert device.max_fps == config.devices.govee.max_fps == GOVEE_RAZER_FPS


async def test_a_lamp_without_razer_plays_one_colour_at_the_colour_rate(
    monkeypatch: pytest.MonkeyPatch, config: AppConfig
) -> None:
    monkeypatch.setitem(SKU_REGISTRY, TEST_MODEL, NO_RAZER)
    device = await _connect(config)
    assert isinstance(device.adapter, GoveeColourAdapter)
    assert device.max_fps == GOVEE_COLOUR_FPS


async def test_an_unknown_model_is_one_colour_at_the_colour_rate(config: AppConfig) -> None:
    device = await _connect(config, sku="not-a-model")
    assert isinstance(device.adapter, GoveeColourAdapter)
    assert device.max_fps == GOVEE_COLOUR_FPS


@pytest.mark.parametrize("sku", [TEST_MODEL, "not-a-model"])
async def test_a_lamp_of_one_colour_leaves_razer_when_prepared(
    monkeypatch: pytest.MonkeyPatch, config: AppConfig, sku: str
) -> None:
    """One segment, or a model the table doesn't know: either may have been left in razer."""
    monkeypatch.setitem(
        SKU_REGISTRY, TEST_MODEL, GoveeDeviceCapability(is_rgbic=False, segment_count=1)
    )
    backend = GoveeBackend()
    transport = backend._transport = lamp_transport()
    (device,) = await backend.connect_known([lamp_row(sku)], config)
    transport.send_command.reset_mock()

    await device.adapter.prepare_stream()

    assert sent(transport) == [build_razer_switch(on=False), build_brightness_message(100)]


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
    assert isinstance(colour.adapter, GoveeColourAdapter)
    assert colour.max_fps == GOVEE_COLOUR_FPS
    counted = await _connect(config, output={"segments": 10})
    assert isinstance(counted.adapter, GoveeRazerAdapter)
    assert counted.adapter.led_count == 10


async def test_a_scan_sets_a_lamp_up_with_the_output_its_row_holds(
    monkeypatch: pytest.MonkeyPatch, config: AppConfig
) -> None:
    monkeypatch.setitem(SKU_REGISTRY, TEST_MODEL, UPRIGHT)
    backend = GoveeBackend()
    backend._transport = lamp_transport()

    (own,) = await backend.discover(config, known=[lamp_row(output={"mode": "colour"})])
    (unknown,) = await backend.discover(config)  # no row: the SKU table's

    assert isinstance(own.adapter, GoveeColourAdapter) and own.max_fps == GOVEE_COLOUR_FPS
    assert isinstance(unknown.adapter, GoveeRazerAdapter)


@pytest.mark.parametrize("path", ["connect_known", "discover"])
async def test_a_silent_lamp_is_a_warning_without_a_traceback(
    config: AppConfig, path: str
) -> None:
    backend = GoveeBackend()
    backend._transport = lamp_transport(None)  # it doesn't answer
    records: list[Any] = []
    sink = logger.add(lambda message: records.append(message.record), level="WARNING")
    try:
        if path == "connect_known":
            assert await backend.connect_known([lamp_row()], config) == []
        else:
            assert await backend.discover(config) == []
    finally:
        logger.remove(sink)
    [warning] = records  # nothing worse
    assert warning["level"].name == "WARNING" and warning["exception"] is None


async def test_a_lamp_is_set_up_again_from_its_row_without_asking_it(config: AppConfig) -> None:
    backend = GoveeBackend()
    transport = backend._transport = lamp_transport()
    tracker = MagicMock()

    device = backend.rebuild(lamp_row(output={"segments": 10}), config, tracker)

    assert device is not None and device.tracker is tracker
    assert device.adapter.is_connected and device.adapter.led_count == 10
    transport.query_status.assert_not_awaited()
    assert backend.rebuild({"id": "lifx:test", "backend": "lifx"}, config, tracker) is None
    backend._transport = None  # shut down
    assert backend.rebuild(lamp_row(), config, tracker) is None
