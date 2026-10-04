from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
from govee_fakes import STATUS, WARM_WHITE, lamp_record, lamp_transport, send_times, sent

from dj_ledfx.devices.govee import adapter_base
from dj_ledfx.devices.govee.adapter_base import STATUS_TIMEOUT_S
from dj_ledfx.devices.govee.colour import GoveeColourAdapter
from dj_ledfx.devices.govee.protocol import (
    build_brightness_message,
    build_razer_switch,
    build_solid_color_message,
)
from dj_ledfx.devices.govee.state import GoveeDeviceState
from dj_ledfx.spatial.geometry import PointGeometry, StripGeometry

RAZER_OFF = build_razer_switch(on=False)


@pytest.fixture
def transport() -> MagicMock:
    return lamp_transport({"onOff": 1, "brightness": 100, "color": {"r": 255, "g": 255, "b": 255}})


def test_a_lamp_of_one_segment_is_a_point(transport: MagicMock) -> None:
    adapter = GoveeColourAdapter(transport, lamp_record())
    info = adapter.device_info
    assert not adapter.razer and adapter.led_count == 1
    assert (info.device_type, info.led_count) == ("govee_solid", 1)
    assert info.address == "127.0.0.1:4003" and "test-model" in info.name
    assert isinstance(adapter.geometry, PointGeometry)


def test_a_lamp_of_segments_playing_one_colour_keeps_its_segments(
    transport: MagicMock,
) -> None:
    adapter = GoveeColourAdapter(transport, lamp_record(), 15)
    assert (adapter.device_info.device_type, adapter.led_count) == ("govee_segment", 15)
    assert adapter.geometry == StripGeometry((1, 0, 0), 1.0)


async def test_connect_queries_status(transport: MagicMock) -> None:
    adapter = GoveeColourAdapter(transport, lamp_record())
    await adapter.connect()
    assert adapter.is_connected is True
    transport.query_status.assert_awaited_once_with("127.0.0.1", timeout_s=STATUS_TIMEOUT_S)


async def test_connect_raises_on_unreachable(transport: MagicMock) -> None:
    transport.query_status = AsyncMock(return_value=None)
    adapter = GoveeColourAdapter(transport, lamp_record())
    with pytest.raises(ConnectionError):
        await adapter.connect()
    assert adapter.is_connected is False


async def test_disconnect(transport: MagicMock) -> None:
    adapter = GoveeColourAdapter(transport, lamp_record())
    await adapter.connect()
    await adapter.disconnect()
    assert adapter.is_connected is False


@pytest.mark.parametrize(
    ("frame", "colour"),
    [
        ([[255, 128, 0]], (255, 128, 0)),
        ([[255, 0, 0], [0, 255, 0], [0, 0, 255]], (85, 85, 85)),
    ],
)
async def test_a_frame_goes_out_as_its_average_colour(
    transport: MagicMock, frame: list[list[int]], colour: tuple[int, int, int]
) -> None:
    adapter = GoveeColourAdapter(transport, lamp_record(), len(frame))
    await adapter.send_frame(np.array(frame, dtype=np.uint8))
    assert sent(transport) == [build_solid_color_message(*colour)]


async def test_a_prepared_lamp_leaves_razer_for_full_brightness(transport: MagicMock) -> None:
    adapter = GoveeColourAdapter(transport, lamp_record(), 15)
    await adapter.prepare_stream()
    assert sent(transport) == [RAZER_OFF, build_brightness_message(100)]


async def test_a_prepare_gives_the_lamp_time_to_take_each_command(transport: MagicMock) -> None:
    sent_at = send_times(transport)
    adapter = GoveeColourAdapter(transport, lamp_record(), 15)
    await adapter.prepare_stream()
    assert len(sent_at) == 2  # razer off, brightness
    assert sent_at[1] - sent_at[0] > 0.9 * adapter_base.COMMAND_GAP_S


async def test_a_lamp_on_white_needs_no_white_off() -> None:
    """No white off here: each colorwc frame carries colour temperature 0 itself, which takes
    the lamp out of white."""
    transport = lamp_transport(WARM_WHITE)
    adapter = GoveeColourAdapter(transport, lamp_record(), 3)
    await adapter.prepare_stream()
    await adapter.send_frame(np.array([[255, 0, 0], [0, 255, 0], [0, 0, 255]], dtype=np.uint8))
    razer_off, brightness, frame = sent(transport)
    assert (razer_off, brightness) == (RAZER_OFF, build_brightness_message(100))
    assert frame == build_solid_color_message(85, 85, 85)
    assert frame["msg"]["data"]["colorTemInKelvin"] == 0


async def test_capture_state_returns_original(transport: MagicMock) -> None:
    transport.query_status = AsyncMock(
        return_value={"onOff": 0, "brightness": 50, "color": {"r": 10, "g": 20, "b": 30}}
    )
    adapter = GoveeColourAdapter(transport, lamp_record())
    state_bytes = await adapter.capture_state()
    assert state_bytes is not None
    restored = GoveeDeviceState.from_bytes(state_bytes)
    assert (restored.on_off, restored.brightness) == (0, 50)


async def test_restore_without_power_sends_nothing(transport: MagicMock) -> None:
    adapter = GoveeColourAdapter(transport, lamp_record())
    state = GoveeDeviceState(on_off=1, brightness=50, r=10, g=20, b=30)
    await adapter.restore_state(state.to_bytes(), power=False)
    transport.send_command.assert_not_called()  # a colour command may switch it on


@pytest.mark.parametrize(("on_off", "last"), [(0, ["turn"]), (1, [])])
async def test_a_restore_leaves_razer_then_puts_colour_and_brightness_back(
    transport: MagicMock, on_off: int, last: list[str]
) -> None:
    transport.query_status.return_value = STATUS  # it takes an off
    adapter = GoveeColourAdapter(transport, lamp_record())
    state = GoveeDeviceState(on_off=on_off, brightness=50, r=10, g=20, b=30)
    await adapter.restore_state(state.to_bytes())

    first, colour, brightness, *rest = sent(transport)
    assert first == RAZER_OFF
    assert colour == build_solid_color_message(10, 20, 30)
    assert brightness == build_brightness_message(50)
    assert [m["msg"]["cmd"] for m in rest] == last  # switched off last, if it was off


async def test_a_lamp_on_white_gets_its_white_back(transport: MagicMock) -> None:
    """Sent its colour alone, a lamp captured on warm white came back in an old colour."""
    adapter = GoveeColourAdapter(transport, lamp_record())
    state = GoveeDeviceState(on_off=1, brightness=80, r=0, g=0, b=0, kelvin=2700)
    await adapter.restore_state(state.to_bytes())
    colour = next(m for m in sent(transport) if m["msg"]["cmd"] == "colorwc")
    assert colour["msg"]["data"]["colorTemInKelvin"] == 2700
