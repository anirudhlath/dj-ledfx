from __future__ import annotations

import base64
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
from govee_fakes import sent

from dj_ledfx.devices.govee.protocol import build_brightness_message, build_razer_switch
from dj_ledfx.devices.govee.segment import RAZER_IDLE_S, UPRIGHT_HEIGHT_M, GoveeSegmentAdapter
from dj_ledfx.devices.govee.state import GoveeDeviceState
from dj_ledfx.devices.govee.types import GoveeDeviceRecord
from dj_ledfx.spatial.geometry import StripGeometry

RAZER_ON, RAZER_OFF = build_razer_switch(on=True), build_razer_switch(on=False)


def _razer_rgb(message: dict[str, Any]) -> bytes:
    """A razer frame's colours: after the header and the count, before the checksum."""
    assert message["msg"]["cmd"] == "razer"
    return base64.b64decode(message["msg"]["data"]["pt"])[6:-1]


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
        """In colour mode a frame goes out as its average colour, by colorwc."""
        adapter = GoveeSegmentAdapter(mock_transport, record, num_segments=3, razer=False)
        await adapter.connect()
        mock_transport.send_command.reset_mock()

        colors = np.array([[255, 0, 0], [0, 255, 0], [0, 0, 255]], dtype=np.uint8)
        await adapter.send_frame(colors)

        mock_transport.send_command.assert_awaited_once()
        call_args = mock_transport.send_command.call_args
        payload = call_args[0][1]
        assert payload["msg"]["cmd"] == "colorwc"
        assert "color" in payload["msg"]["data"]

    def test_geometry_returns_strip(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        adapter = GoveeSegmentAdapter(mock_transport, record, num_segments=15)
        geo = adapter.geometry
        assert isinstance(geo, StripGeometry)
        assert geo.direction == (1, 0, 0)
        assert geo.length == 1.0

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
        adapter = GoveeSegmentAdapter(mock_transport, record, num_segments=15, razer=False)
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
        adapter = GoveeSegmentAdapter(mock_transport, record, num_segments=15, razer=False)
        await adapter.connect()
        mock_transport.send_command.reset_mock()

        state = GoveeDeviceState(on_off=1, brightness=80, r=255, g=255, b=255)
        await adapter.restore_state(state.to_bytes())

        calls = mock_transport.send_command.call_args_list
        # Should send: color, brightness (no turn off since on_off=1)
        assert len(calls) == 2
        assert calls[0][0][1]["msg"]["cmd"] == "colorwc"
        assert calls[1][0][1]["msg"]["cmd"] == "brightness"


class TestRazer:
    async def test_each_segment_gets_its_own_colour(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        adapter = GoveeSegmentAdapter(mock_transport, record, 3, razer=True)
        colors = np.array([[255, 0, 0], [0, 255, 0], [0, 0, 255]], dtype=np.uint8)
        await adapter.send_frame(colors)
        switch, frame = sent(mock_transport)
        assert switch == RAZER_ON and _razer_rgb(frame) == colors.tobytes()

    async def test_razer_is_switched_on_again_after_a_pause(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        now = [100.0]
        adapter = GoveeSegmentAdapter(mock_transport, record, 3, razer=True, clock=lambda: now[0])
        frame = np.zeros((3, 3), dtype=np.uint8)
        await adapter.send_frame(frame)
        now[0] += 1.0
        await adapter.send_frame(frame)
        now[0] += RAZER_IDLE_S + 0.1
        await adapter.send_frame(frame)
        assert [m == RAZER_ON for m in sent(mock_transport)] == [True, False, False, True, False]

    # Review Focus 2: a look started right after another re-arms razer.
    async def test_a_look_started_right_after_another_re_arms(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        adapter = GoveeSegmentAdapter(mock_transport, record, 3, razer=True, clock=lambda: 100.0)
        frame = np.zeros((3, 3), dtype=np.uint8)
        await adapter.send_frame(frame)
        captured = GoveeDeviceState(on_off=1, brightness=80, r=1, g=2, b=3).to_bytes()
        await adapter.restore_state(captured)  # the first look's Off
        await adapter.prepare_stream()  # the next look, at once
        mock_transport.send_command.reset_mock()
        await adapter.send_frame(frame)
        assert sent(mock_transport)[0] == RAZER_ON

    async def test_a_restore_takes_the_lamp_out_of_razer_first(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        adapter = GoveeSegmentAdapter(mock_transport, record, 3, razer=True)
        state = GoveeDeviceState(on_off=0, brightness=50, r=10, g=20, b=30)
        await adapter.restore_state(state.to_bytes())
        first, *rest = sent(mock_transport)
        assert first == RAZER_OFF
        assert [m["msg"]["cmd"] for m in rest] == ["colorwc", "brightness", "turn"]

    async def test_a_lamp_switched_off_elsewhere_is_left_alone(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        adapter = GoveeSegmentAdapter(mock_transport, record, 3, razer=True)
        state = GoveeDeviceState(on_off=1, brightness=50, r=10, g=20, b=30)
        await adapter.restore_state(state.to_bytes(), power=False)
        assert sent(mock_transport) == []

    async def test_a_lamp_playing_one_colour_leaves_razer_when_prepared(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        adapter = GoveeSegmentAdapter(mock_transport, record, 3, razer=False)
        await adapter.prepare_stream()
        assert sent(mock_transport) == [RAZER_OFF, build_brightness_message(100)]

    def test_an_upright_lamp_stands(
        self, mock_transport: MagicMock, record: GoveeDeviceRecord
    ) -> None:
        up = GoveeSegmentAdapter(mock_transport, record, 15, form="upright")
        down = GoveeSegmentAdapter(mock_transport, record, 15, form="upright", from_top=True)
        assert up.geometry == StripGeometry((0, 1, 0), UPRIGHT_HEIGHT_M)
        assert down.geometry == StripGeometry((0, -1, 0), UPRIGHT_HEIGHT_M)
