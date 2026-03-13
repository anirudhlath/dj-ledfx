from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from dj_ledfx.devices.govee.solid import GoveeSolidAdapter
from dj_ledfx.devices.govee.types import GoveeDeviceRecord


@pytest.fixture
def record() -> GoveeDeviceRecord:
    return GoveeDeviceRecord(
        ip="192.168.1.23",
        device_id="AA:BB:CC:DD:EE:FF:00:11",
        sku="H6001",
        wifi_version="1.00.00",
        ble_version="1.00.00",
    )


@pytest.fixture
def mock_transport() -> MagicMock:
    transport = MagicMock()
    transport.query_status = AsyncMock(return_value={"onOff": 1, "brightness": 100})
    transport.send_command = AsyncMock()
    return transport


class TestGoveeSolidAdapter:
    def test_led_count_is_1(self, mock_transport: MagicMock, record: GoveeDeviceRecord) -> None:
        adapter = GoveeSolidAdapter(mock_transport, record)
        assert adapter.led_count == 1

    def test_device_info(self, mock_transport: MagicMock, record: GoveeDeviceRecord) -> None:
        adapter = GoveeSolidAdapter(mock_transport, record)
        info = adapter.device_info
        assert info.device_type == "govee_solid"
        assert info.led_count == 1
        assert info.address == "192.168.1.23:4003"
        assert "H6001" in info.name

    def test_supports_latency_probing_false(self) -> None:
        assert GoveeSolidAdapter.supports_latency_probing is False

    @pytest.mark.asyncio
    async def test_connect_queries_status(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        adapter = GoveeSolidAdapter(mock_transport, record)
        await adapter.connect()
        assert adapter.is_connected is True
        mock_transport.query_status.assert_awaited_once_with(record.ip)

    @pytest.mark.asyncio
    async def test_connect_raises_on_unreachable(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        mock_transport.query_status = AsyncMock(return_value=None)
        adapter = GoveeSolidAdapter(mock_transport, record)
        with pytest.raises(ConnectionError):
            await adapter.connect()
        assert adapter.is_connected is False

    @pytest.mark.asyncio
    async def test_disconnect(self, mock_transport: MagicMock, record: GoveeDeviceRecord) -> None:
        adapter = GoveeSolidAdapter(mock_transport, record)
        await adapter.connect()
        await adapter.disconnect()
        assert adapter.is_connected is False

    @pytest.mark.asyncio
    async def test_send_frame_uses_first_pixel(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        adapter = GoveeSolidAdapter(mock_transport, record)
        await adapter.connect()

        colors = np.array([[255, 128, 0], [0, 0, 0]], dtype=np.uint8)
        await adapter.send_frame(colors)

        mock_transport.send_command.assert_awaited_once()
        call_args = mock_transport.send_command.call_args
        ip = call_args[0][0]
        payload = call_args[0][1]
        assert ip == "192.168.1.23"
        assert payload["msg"]["cmd"] == "colorwc"
        assert payload["msg"]["data"]["color"] == {"r": 255, "g": 128, "b": 0}
