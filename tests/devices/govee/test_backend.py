# tests/devices/govee/test_backend.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dj_ledfx.config import AppConfig, DevicesConfig, GoveeConfig
from dj_ledfx.devices.govee.backend import GoveeBackend
from dj_ledfx.devices.govee.segment import GoveeSegmentAdapter
from dj_ledfx.devices.govee.solid import GoveeSolidAdapter
from dj_ledfx.devices.govee.types import GoveeDeviceRecord


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
        assert results[0].max_fps == 40

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
