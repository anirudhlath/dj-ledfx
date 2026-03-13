from __future__ import annotations

from dj_ledfx.devices.govee.protocol import (
    build_brightness_message,
    build_scan_message,
    build_solid_color_message,
    build_status_query,
    build_turn_message,
)


class TestBuildScanMessage:
    def test_scan_message_format(self) -> None:
        msg = build_scan_message()
        assert msg == {"msg": {"cmd": "scan", "data": {"account_topic": "reserve"}}}


class TestBuildTurnMessage:
    def test_turn_on(self) -> None:
        msg = build_turn_message(on=True)
        assert msg == {"msg": {"cmd": "turn", "data": {"value": 1}}}

    def test_turn_off(self) -> None:
        msg = build_turn_message(on=False)
        assert msg == {"msg": {"cmd": "turn", "data": {"value": 0}}}


class TestBuildBrightnessMessage:
    def test_normal_value(self) -> None:
        msg = build_brightness_message(50)
        assert msg == {"msg": {"cmd": "brightness", "data": {"value": 50}}}

    def test_clamps_low(self) -> None:
        msg = build_brightness_message(0)
        assert msg["msg"]["data"]["value"] == 1

    def test_clamps_high(self) -> None:
        msg = build_brightness_message(150)
        assert msg["msg"]["data"]["value"] == 100


class TestBuildSolidColorMessage:
    def test_red(self) -> None:
        msg = build_solid_color_message(255, 0, 0)
        assert msg == {
            "msg": {
                "cmd": "colorwc",
                "data": {"color": {"r": 255, "g": 0, "b": 0}, "colorTemInKelvin": 0},
            }
        }


class TestBuildStatusQuery:
    def test_status_query_format(self) -> None:
        msg = build_status_query()
        assert msg == {"msg": {"cmd": "devStatus", "data": {}}}
