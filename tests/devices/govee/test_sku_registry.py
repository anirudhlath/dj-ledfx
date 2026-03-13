from __future__ import annotations

from dj_ledfx.devices.govee.sku_registry import (
    DEFAULT_CAPABILITY,
    get_device_capability,
    get_segment_count,
)


class TestGetDeviceCapability:
    def test_known_sku_h6076(self) -> None:
        cap = get_device_capability("H6076")
        assert cap.is_rgbic is True
        assert cap.segment_count == 15

    def test_known_sku_h61a2(self) -> None:
        cap = get_device_capability("H61A2")
        assert cap.is_rgbic is True
        assert cap.segment_count == 15

    def test_unknown_sku_returns_default(self) -> None:
        cap = get_device_capability("H9999")
        assert cap == DEFAULT_CAPABILITY
        assert cap.is_rgbic is False
        assert cap.segment_count == 0


class TestGetSegmentCount:
    def test_known_sku(self) -> None:
        assert get_segment_count("H6076") == 15

    def test_unknown_sku(self) -> None:
        assert get_segment_count("H9999") == 0

    def test_config_override_wins(self) -> None:
        assert get_segment_count("H6076", config_override=10) == 10

    def test_config_override_none_uses_registry(self) -> None:
        assert get_segment_count("H6076", config_override=None) == 15
