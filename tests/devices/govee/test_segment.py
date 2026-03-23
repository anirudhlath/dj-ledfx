from __future__ import annotations

import base64
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest

from dj_ledfx.devices.govee.protocol import xor_checksum
from dj_ledfx.devices.govee.segment import GoveeSegmentAdapter
from dj_ledfx.devices.govee.state import GoveeDeviceState
from dj_ledfx.devices.govee.types import GoveeDeviceRecord
from dj_ledfx.spatial.geometry import StripGeometry


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
    transport.query_status = AsyncMock(
        return_value={"onOff": 1, "brightness": 80, "color": {"r": 100, "g": 150, "b": 200}}
    )
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

    def test_geometry_returns_strip(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        adapter = GoveeSegmentAdapter(mock_transport, record, num_segments=15)
        geo = adapter.geometry
        assert isinstance(geo, StripGeometry)
        assert geo.direction == (1, 0, 0)
        assert geo.length == 1.0

    @pytest.mark.asyncio
    async def test_connect_captures_original_state(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        mock_transport.query_status = AsyncMock(
            return_value={"onOff": 0, "brightness": 50, "color": {"r": 10, "g": 20, "b": 30}}
        )
        adapter = GoveeSegmentAdapter(mock_transport, record, num_segments=15)
        await adapter.connect()
        assert adapter._original_state is not None
        assert adapter._original_state.on_off == 0
        assert adapter._original_state.brightness == 50
        assert adapter._original_state.r == 10

    @pytest.mark.asyncio
    async def test_capture_state_returns_original(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        mock_transport.query_status = AsyncMock(
            return_value={"onOff": 0, "brightness": 50, "color": {"r": 10, "g": 20, "b": 30}}
        )
        adapter = GoveeSegmentAdapter(mock_transport, record, num_segments=15)
        await adapter.connect()
        state_bytes = await adapter.capture_state()
        restored = GoveeDeviceState.from_bytes(state_bytes)
        assert restored.on_off == 0
        assert restored.brightness == 50
        assert restored.r == 10

    @pytest.mark.asyncio
    async def test_restore_state_sends_commands(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        adapter = GoveeSegmentAdapter(mock_transport, record, num_segments=15)
        await adapter.connect()
        mock_transport.send_command.reset_mock()

        state = GoveeDeviceState(on_off=0, brightness=50, r=10, g=20, b=30)
        await adapter.restore_state(state.to_bytes())

        calls = mock_transport.send_command.call_args_list
        # Should send: color, brightness, turn off (3 commands)
        assert len(calls) == 3
        assert calls[0][0][1]["msg"]["cmd"] == "colorwc"
        assert calls[0][0][1]["msg"]["data"]["color"] == {"r": 10, "g": 20, "b": 30}
        assert calls[1][0][1]["msg"]["cmd"] == "brightness"
        assert calls[1][0][1]["msg"]["data"]["value"] == 50
        assert calls[2][0][1]["msg"]["cmd"] == "turn"
        assert calls[2][0][1]["msg"]["data"]["value"] == 0

    @pytest.mark.asyncio
    async def test_restore_state_skips_turn_off_when_on(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        adapter = GoveeSegmentAdapter(mock_transport, record, num_segments=15)
        await adapter.connect()
        mock_transport.send_command.reset_mock()

        state = GoveeDeviceState(on_off=1, brightness=80, r=255, g=255, b=255)
        await adapter.restore_state(state.to_bytes())

        calls = mock_transport.send_command.call_args_list
        # Should send: color, brightness (no turn off since on_off=1)
        assert len(calls) == 2
        assert calls[0][0][1]["msg"]["cmd"] == "colorwc"
        assert calls[1][0][1]["msg"]["cmd"] == "brightness"
