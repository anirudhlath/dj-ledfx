from __future__ import annotations

import pytest

from dj_ledfx.devices.capabilities import DeviceCapabilities, LightReading, protocol_of


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("lifx", "LIFX"),
        ("lifx_tile", "LIFX"),
        ("govee", "Govee"),
        ("govee_segment", "Govee"),
        ("openrgb", "OpenRGB"),
        ("", "OpenRGB"),
    ],
)
def test_protocol_of(value: str, expected: str) -> None:
    assert protocol_of(value) == expected


def test_capabilities_default_to_a_plain_colour_light() -> None:
    caps = DeviceCapabilities(protocol="Govee")
    assert caps.colour is True
    assert not (caps.multizone or caps.extended_multizone or caps.matrix or caps.chain)
    assert caps.openrgb_modes == ()


def test_light_reading_allows_unknown_values() -> None:
    reading = LightReading(power=None, colour=None)
    assert reading.power is None and reading.colour is None
