"""Test that Govee adapters populate stable_id on DeviceInfo."""

from unittest.mock import MagicMock

from dj_ledfx.devices.govee.segment import GoveeSegmentAdapter
from dj_ledfx.devices.govee.solid import GoveeSolidAdapter
from dj_ledfx.devices.govee.types import GoveeDeviceRecord


def _make_record():
    return GoveeDeviceRecord(
        ip="192.168.1.10",
        device_id="1F:80:C5:32:32:36:72:4E",
        sku="H6159",
        wifi_version="1.0",
        ble_version="1.0",
    )


def test_segment_adapter_stable_id():
    transport = MagicMock()
    adapter = GoveeSegmentAdapter(transport, _make_record(), num_segments=10)
    info = adapter.device_info
    assert info.stable_id == "govee:1F:80:C5:32:32:36:72:4E"


def test_solid_adapter_stable_id():
    transport = MagicMock()
    adapter = GoveeSolidAdapter(transport, _make_record())
    info = adapter.device_info
    assert info.stable_id == "govee:1F:80:C5:32:32:36:72:4E"
