"""Govee stand-ins: the test lamp (its record, its device row, a fake light with its caps),
the SKU table's kinds of lamp, and a transport that hears the lamp."""

from __future__ import annotations

import json
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from conftest import FakeLight

from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.devices.govee.types import GoveeDeviceCapability, GoveeDeviceRecord

TEST_MODEL = "test-model"  # a test registers it in SKU_REGISTRY as the kind it needs
LAMP = "govee:test-lamp"  # the test lamp's stable id
UPRIGHT = GoveeDeviceCapability(is_rgbic=True, segment_count=15, razer=True, form="upright")
NO_RAZER = GoveeDeviceCapability(is_rgbic=True, segment_count=15)
STATUS: dict[str, Any] = {"onOff": 0, "brightness": 50, "color": {"r": 10, "g": 20, "b": 30}}
# A lamp on warm white: its white LEDs, at a colour temperature, beside a colour that means
# nothing (black from one lamp, white from another).
WARM_WHITE: dict[str, Any] = {
    "onOff": 1,
    "brightness": 80,
    "color": {"r": 0, "g": 0, "b": 0},
    "colorTemInKelvin": 2700,
}


def lamp_record(sku: str = TEST_MODEL) -> GoveeDeviceRecord:
    return GoveeDeviceRecord(
        ip="127.0.0.1", device_id="test-lamp", sku=sku, wifi_version="", ble_version=""
    )


def lamp_row(sku: str = TEST_MODEL, output: dict[str, Any] | None = None) -> dict[str, Any]:
    """The test lamp's device row, with its own output in extra when one is given."""
    row: dict[str, Any] = {
        "id": LAMP,
        "name": "Test lamp",
        "backend": "govee",
        "ip": "127.0.0.1",
        "device_id": "test-lamp",
        "sku": sku,
    }
    if output is not None:
        row["extra"] = json.dumps({"output": output})
    return row


def govee_lamp(led_count: int = 15) -> FakeLight:
    """A fake light standing in for the test lamp, with Govee's capabilities."""
    return FakeLight(
        LAMP, name="Test lamp", led_count=led_count, caps=DeviceCapabilities(protocol="Govee")
    )


def lamp_transport(
    status: dict[str, Any] | None = STATUS, *, can_receive: bool = True, sku: str = TEST_MODEL
) -> MagicMock:
    """A transport that hears the lamp (status: its answer to a status query, None for
    silence; can_receive=False: another program holds the reply port), and whose scans find
    it as a lamp of `sku`."""
    transport = MagicMock()
    transport.is_open = True
    transport.can_receive = can_receive
    transport.query_status = AsyncMock(return_value=status)
    transport.last_heard = MagicMock(return_value=None)  # never heard but by its reads
    transport.send_command = AsyncMock()

    async def discover(timeout_s: float = 10.0, on_record: Any = None) -> list[Any]:
        record = lamp_record(sku)
        on_record(record)
        return [record]  # the records the scan heard

    transport.discover = discover
    return transport


def send_times(transport: MagicMock) -> list[float]:
    """When each message goes through the transport from now on (`time.monotonic()`)."""
    times: list[float] = []
    transport.send_command.side_effect = lambda *_: times.append(time.monotonic())
    return times


def sent(transport: MagicMock) -> list[dict[str, Any]]:
    """Every message sent through the transport, in order."""
    return [call.args[1] for call in transport.send_command.call_args_list]
