"""Test that LIFX discovery populates stable_id and mac on DeviceInfo."""

from dj_ledfx.types import DeviceInfo


def test_lifx_stable_id_format():
    mac_hex = b"\xd0\x73\xd5\xaa\xbb\xcc".hex()
    stable_id = f"lifx:{mac_hex}"
    info = DeviceInfo(
        name="LIFX Strip (192.168.1.5)",
        device_type="lifx_strip",
        led_count=60,
        address="192.168.1.5:56700",
        mac=mac_hex,
        stable_id=stable_id,
    )
    assert info.stable_id == "lifx:d073d5aabbcc"
    assert info.mac == "d073d5aabbcc"
