from __future__ import annotations

import base64
from typing import Any
from unittest.mock import MagicMock

import numpy as np
import pytest
from govee_fakes import lamp_record, lamp_transport, sent

from dj_ledfx.devices.govee.adapter_base import UPRIGHT_HEIGHT_M
from dj_ledfx.devices.govee.protocol import build_brightness_message, build_razer_switch
from dj_ledfx.devices.govee.razer import RAZER_IDLE_S, GoveeRazerAdapter
from dj_ledfx.devices.govee.state import GoveeDeviceState
from dj_ledfx.scheduling.scheduler import KEEPALIVE_S
from dj_ledfx.spatial.geometry import StripGeometry

RAZER_ON, RAZER_OFF = build_razer_switch(on=True), build_razer_switch(on=False)


def _razer_rgb(message: dict[str, Any]) -> bytes:
    """A razer frame's colours: after the header and the count, before the checksum."""
    assert message["msg"]["cmd"] == "razer"
    return base64.b64decode(message["msg"]["data"]["pt"])[6:-1]


@pytest.fixture
def transport() -> MagicMock:
    return lamp_transport({"onOff": 1, "brightness": 80, "color": {"r": 100, "g": 150, "b": 200}})


def test_a_razer_lamp_is_its_segments(transport: MagicMock) -> None:
    adapter = GoveeRazerAdapter(transport, lamp_record(), 15)
    assert adapter.razer and adapter.led_count == 15
    assert (adapter.device_info.device_type, adapter.device_info.led_count) == (
        "govee_segment",
        15,
    )
    assert adapter.geometry == StripGeometry((1, 0, 0), 1.0)  # a strip lies along its length


def test_an_upright_lamp_stands(transport: MagicMock) -> None:
    up = GoveeRazerAdapter(transport, lamp_record(), 15, form="upright")
    down = GoveeRazerAdapter(transport, lamp_record(), 15, form="upright", from_top=True)
    assert up.geometry == StripGeometry((0, 1, 0), UPRIGHT_HEIGHT_M)
    assert down.geometry == StripGeometry((0, -1, 0), UPRIGHT_HEIGHT_M)


async def test_each_segment_gets_its_own_colour(transport: MagicMock) -> None:
    adapter = GoveeRazerAdapter(transport, lamp_record(), 3)
    colors = np.array([[255, 0, 0], [0, 255, 0], [0, 0, 255]], dtype=np.uint8)
    await adapter.send_frame(colors)
    switch, frame = sent(transport)
    assert switch == RAZER_ON and _razer_rgb(frame) == colors.tobytes()


async def test_razer_is_switched_on_again_after_a_pause(transport: MagicMock) -> None:
    now = [100.0]
    adapter = GoveeRazerAdapter(transport, lamp_record(), 3, clock=lambda: now[0])
    frame = np.zeros((3, 3), dtype=np.uint8)
    await adapter.send_frame(frame)
    now[0] += 1.0
    await adapter.send_frame(frame)
    now[0] += RAZER_IDLE_S + 0.1
    await adapter.send_frame(frame)
    assert [m == RAZER_ON for m in sent(transport)] == [True, False, False, True, False]


async def test_a_prepared_lamp_gets_full_brightness_and_razer_with_its_next_frame(
    transport: MagicMock,
) -> None:
    adapter = GoveeRazerAdapter(transport, lamp_record(), 3, clock=lambda: 100.0)
    frame = np.zeros((3, 3), dtype=np.uint8)
    await adapter.send_frame(frame)
    transport.send_command.reset_mock()

    await adapter.prepare_stream()
    await adapter.send_frame(frame)

    assert sent(transport)[:2] == [build_brightness_message(100), RAZER_ON]


# Review Focus 2: a look started right after another re-arms razer.
async def test_a_look_started_right_after_another_re_arms(transport: MagicMock) -> None:
    adapter = GoveeRazerAdapter(transport, lamp_record(), 3, clock=lambda: 100.0)
    frame = np.zeros((3, 3), dtype=np.uint8)
    await adapter.send_frame(frame)
    captured = GoveeDeviceState(on_off=1, brightness=80, r=1, g=2, b=3).to_bytes()
    await adapter.restore_state(captured)  # the first look's Off
    await adapter.prepare_stream()  # the next look, at once
    transport.send_command.reset_mock()
    await adapter.send_frame(frame)
    assert sent(transport)[0] == RAZER_ON


async def test_a_restore_takes_the_lamp_out_of_razer_first(transport: MagicMock) -> None:
    adapter = GoveeRazerAdapter(transport, lamp_record(), 3)
    state = GoveeDeviceState(on_off=0, brightness=50, r=10, g=20, b=30)
    await adapter.restore_state(state.to_bytes())
    first, *rest = sent(transport)
    assert first == RAZER_OFF
    assert [m["msg"]["cmd"] for m in rest] == ["colorwc", "brightness", "turn"]


async def test_a_lamp_switched_off_elsewhere_is_left_alone(transport: MagicMock) -> None:
    adapter = GoveeRazerAdapter(transport, lamp_record(), 3)
    state = GoveeDeviceState(on_off=1, brightness=50, r=10, g=20, b=30)
    await adapter.restore_state(state.to_bytes(), power=False)
    assert sent(transport) == []


async def test_a_failed_send_disconnects_it(transport: MagicMock) -> None:
    adapter = GoveeRazerAdapter(transport, lamp_record(), 3)
    await adapter.connect()
    transport.send_command.side_effect = OSError("network down")
    await adapter.send_frame(np.zeros((3, 3), dtype=np.uint8))
    assert adapter.is_connected is False


def test_a_still_look_keeps_razer_armed() -> None:
    """The scheduler re-sends an unchanged frame every KEEPALIVE_S, and razer is switched on
    again after RAZER_IDLE_S without a frame: a still look must come round first."""
    assert KEEPALIVE_S < RAZER_IDLE_S
