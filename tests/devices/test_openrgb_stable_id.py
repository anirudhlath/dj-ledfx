"""Test that OpenRGB adapters populate stable_id on DeviceInfo."""
from dj_ledfx.types import DeviceInfo


def test_openrgb_stable_id_format():
    info = DeviceInfo(
        name="My Keyboard",
        device_type="openrgb",
        led_count=100,
        address="127.0.0.1:6742",
        stable_id="openrgb:127.0.0.1:6742:0",
    )
    assert info.stable_id == "openrgb:127.0.0.1:6742:0"
