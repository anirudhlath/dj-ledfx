from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from govee_fakes import STATUS, lamp_record, lamp_transport, sent

from dj_ledfx.devices.capabilities import LightReading, NoAnswer, try_read
from dj_ledfx.devices.govee.colour import GoveeColourAdapter
from dj_ledfx.devices.govee.razer import GoveeRazerAdapter
from dj_ledfx.devices.govee.state import GoveeDeviceState
from dj_ledfx.devices.govee.transport import GoveeTransport
from dj_ledfx.devices.govee.types import GoveeDeviceRecord


@pytest.fixture
def record() -> GoveeDeviceRecord:
    return lamp_record()


async def test_connect_changes_nothing_on_the_lamp(record: GoveeDeviceRecord) -> None:
    transport = lamp_transport()
    adapter = GoveeColourAdapter(transport, record)
    await adapter.connect()
    assert adapter.is_connected
    transport.send_command.assert_not_awaited()


async def test_connect_without_the_reply_port_connects_blind(record: GoveeDeviceRecord) -> None:
    transport = lamp_transport(can_receive=False)
    adapter = GoveeColourAdapter(transport, record)
    await adapter.connect()
    assert adapter.is_connected
    transport.query_status.assert_not_awaited()


async def test_read_light_reports_power_and_colour(record: GoveeDeviceRecord) -> None:
    adapter = GoveeColourAdapter(lamp_transport(), record)
    assert await adapter.read_light() == LightReading(power=False, colour=(10, 20, 30))


async def test_read_light_is_unknown_while_another_program_holds_the_reply_port(
    record: GoveeDeviceRecord,
) -> None:
    transport = lamp_transport(can_receive=False)
    adapter = GoveeColourAdapter(transport, record)
    assert await adapter.read_light() == LightReading.UNKNOWN
    transport.query_status.assert_not_awaited()


# Review Focus 1: a lamp that stops answering mid-look is a missed read. Three in a row take
# it offline (zones/lights.py), so it gets no frames until a scan finds it again.
async def test_a_lamp_that_stops_answering_is_missing_not_unknown(
    record: GoveeDeviceRecord,
) -> None:
    transport = lamp_transport()
    transport.query_status = AsyncMock(side_effect=[None, None, None, None])  # silent
    adapter = GoveeColourAdapter(transport, record)
    with pytest.raises(NoAnswer):
        await adapter.read_light()
    assert transport.query_status.await_count == 2  # asked again before giving up
    assert await try_read(adapter) is None  # what the light monitor counts as a miss


# A streaming lamp answered 9 status queries of 10: one lost reply is asked again, so it
# isn't a missed read (the light-output fixes' review, Important 1).
async def test_one_lost_reply_is_not_a_miss(record: GoveeDeviceRecord) -> None:
    transport = lamp_transport()
    transport.query_status = AsyncMock(side_effect=[None, STATUS])
    adapter = GoveeColourAdapter(transport, record)
    assert await try_read(adapter) == LightReading(power=False, colour=(10, 20, 30))


async def test_connect_and_capture_ask_again_too(record: GoveeDeviceRecord) -> None:
    transport = lamp_transport()
    transport.query_status = AsyncMock(side_effect=[None, STATUS, None, STATUS])
    adapter = GoveeColourAdapter(transport, record)
    await adapter.connect()
    assert adapter.is_connected
    assert await adapter.capture_state() is not None


async def test_capture_reads_the_lamp_now(record: GoveeDeviceRecord) -> None:
    adapter = GoveeColourAdapter(lamp_transport(), record)
    captured = await adapter.capture_state()
    assert captured is not None
    assert GoveeDeviceState.from_bytes(captured) == GoveeDeviceState(
        on_off=0, brightness=50, r=10, g=20, b=30
    )


async def test_capture_is_none_without_the_reply_port(record: GoveeDeviceRecord) -> None:
    assert (
        await GoveeColourAdapter(lamp_transport(can_receive=False), record).capture_state() is None
    )


async def test_set_power_and_prepare_stream(record: GoveeDeviceRecord) -> None:
    transport = lamp_transport()
    adapter = GoveeRazerAdapter(transport, record, 15)
    await adapter.set_power(True)
    await adapter.prepare_stream()
    assert sent(transport) == [
        {"msg": {"cmd": "turn", "data": {"value": 1}}},
        {
            "msg": {
                "cmd": "colorwc",
                "data": {"color": {"r": 0, "g": 0, "b": 0}, "colorTemInKelvin": 0},
            }
        },
        {"msg": {"cmd": "brightness", "data": {"value": 100}}},
    ]


def test_transport_knows_whether_it_can_receive() -> None:
    transport = GoveeTransport()
    assert transport.can_receive is False
    transport._recv_transport = MagicMock()
    assert transport.can_receive is True


def test_a_lamp_names_its_model_and_its_segments(record: GoveeDeviceRecord) -> None:
    solid = GoveeColourAdapter(lamp_transport(), record).capabilities
    lamp = GoveeRazerAdapter(lamp_transport(), record, 15).capabilities
    assert (solid.protocol, solid.model) == ("Govee", f"Govee {record.sku}")
    assert not solid.multizone
    assert (lamp.model, lamp.multizone) == (solid.model, True)
