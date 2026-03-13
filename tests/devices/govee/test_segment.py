from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from dj_ledfx.devices.govee.protocol import xor_checksum
from dj_ledfx.devices.govee.segment import GoveeSegmentAdapter
from dj_ledfx.devices.govee.types import GoveeDeviceRecord


@pytest.fixture
def record() -> GoveeDeviceRecord:
    return GoveeDeviceRecord(
        ip="192.168.1.23",
        device_id="AA:BB:CC:DD:EE:FF:00:11",
        sku="H6076",
        wifi_version="1.00.00",
        ble_version="1.00.00",
    )


@pytest.fixture
def mock_transport() -> MagicMock:
    transport = MagicMock()
    transport.query_status = AsyncMock(return_value={"onOff": 1})
    transport.send_command = AsyncMock()
    return transport


class TestGoveeSegmentAdapter:
    def test_led_count_equals_segments(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        adapter = GoveeSegmentAdapter(mock_transport, record, num_segments=15)
        assert adapter.led_count == 15

    def test_device_info(self, mock_transport: MagicMock, record: GoveeDeviceRecord) -> None:
        adapter = GoveeSegmentAdapter(mock_transport, record, num_segments=15)
        info = adapter.device_info
        assert info.device_type == "govee_segment"
        assert info.led_count == 15

    def test_supports_latency_probing_false(self) -> None:
        assert GoveeSegmentAdapter.supports_latency_probing is False

    @pytest.mark.asyncio
    async def test_connect_raises_on_unreachable(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        mock_transport.query_status = AsyncMock(return_value=None)
        adapter = GoveeSegmentAdapter(mock_transport, record, num_segments=15)
        with pytest.raises(ConnectionError):
            await adapter.connect()
        assert adapter.is_connected is False

    @pytest.mark.asyncio
    async def test_send_frame_colorwc_fallback(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        """Default mode sends colorwc with averaged color."""
        adapter = GoveeSegmentAdapter(mock_transport, record, num_segments=3)
        await adapter.connect()
        mock_transport.send_command.reset_mock()

        colors = np.array([[255, 0, 0], [0, 255, 0], [0, 0, 255]], dtype=np.uint8)
        await adapter.send_frame(colors)

        mock_transport.send_command.assert_awaited_once()
        call_args = mock_transport.send_command.call_args
        payload = call_args[0][1]
        assert payload["msg"]["cmd"] == "colorwc"
        assert "color" in payload["msg"]["data"]

    @pytest.mark.asyncio
    async def test_send_frame_sends_pt_real(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        adapter = GoveeSegmentAdapter(mock_transport, record, num_segments=3, use_pt_real=True)
        await adapter.connect()
        mock_transport.send_command.reset_mock()

        colors = np.array([[255, 0, 0], [0, 255, 0], [0, 0, 255]], dtype=np.uint8)
        await adapter.send_frame(colors)

        mock_transport.send_command.assert_awaited_once()
        call_args = mock_transport.send_command.call_args
        payload = call_args[0][1]
        assert payload["msg"]["cmd"] == "ptReal"
        commands = payload["msg"]["data"]["command"]
        assert len(commands) == 3

        # Verify each command is valid base64 and 20 bytes
        for cmd_b64 in commands:
            decoded = base64.b64decode(cmd_b64)
            assert len(decoded) == 20
            assert decoded[0] == 0x33
            assert decoded[1] == 0x05
            assert decoded[2] == 0x0B
            assert xor_checksum(decoded[:19]) == decoded[19]

    @pytest.mark.asyncio
    async def test_send_frame_downsamples(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        """6 LEDs → 3 segments = downsampled (ptReal mode)."""
        adapter = GoveeSegmentAdapter(mock_transport, record, num_segments=3, use_pt_real=True)
        await adapter.connect()
        mock_transport.send_command.reset_mock()

        colors = np.array(
            [[200, 0, 0], [100, 0, 0], [0, 200, 0], [0, 100, 0], [0, 0, 200], [0, 0, 100]],
            dtype=np.uint8,
        )
        await adapter.send_frame(colors)

        payload = mock_transport.send_command.call_args[0][1]
        commands = payload["msg"]["data"]["command"]
        assert len(commands) == 3
