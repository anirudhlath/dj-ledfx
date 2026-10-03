from __future__ import annotations

import base64

import numpy as np
import pytest

from dj_ledfx.devices.govee.protocol import (
    MAX_RAZER_SEGMENTS,
    build_brightness_message,
    build_razer_frame,
    build_razer_switch,
    build_scan_message,
    build_solid_color_message,
    build_status_query,
    build_turn_message,
    xor_checksum,
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

    def test_a_white(self) -> None:
        msg = build_solid_color_message(0, 0, 0, kelvin=2700)
        assert msg["msg"]["data"]["colorTemInKelvin"] == 2700


class TestBuildStatusQuery:
    def test_status_query_format(self) -> None:
        msg = build_status_query()
        assert msg == {"msg": {"cmd": "devStatus", "data": {}}}


class TestXorChecksum:
    def test_simple(self) -> None:
        assert xor_checksum(b"\x33\x01\x01") == 0x33

    def test_all_zeros(self) -> None:
        assert xor_checksum(b"\x00\x00\x00") == 0x00

    def test_known_power_on(self) -> None:
        data = bytes([0x33, 0x01, 0x01] + [0x00] * 16)
        assert xor_checksum(data) == 0x33


class TestRazer:
    def test_razer_switches_on_and_off(self) -> None:
        on = {"msg": {"cmd": "razer", "data": {"pt": "uwABsQEK"}}}
        off = {"msg": {"cmd": "razer", "data": {"pt": "uwABsQAL"}}}
        assert (build_razer_switch(on=True), build_razer_switch(on=False)) == (on, off)

    def test_a_frame_is_one_colour_per_segment_and_a_checksum(self) -> None:
        colors = np.array([[255, 0, 0], [0, 255, 0], [0, 0, 255]], dtype=np.uint8)
        msg = build_razer_frame(colors)
        assert msg["msg"]["cmd"] == "razer"
        packet = base64.b64decode(msg["msg"]["data"]["pt"])
        assert packet[:6] == bytes((0xBB, 0x00, 0xFA, 0xB0, 0x00, 3))
        assert packet[6:15] == colors.tobytes()
        assert len(packet) == 16 and packet[15] == xor_checksum(packet[:15])

    @pytest.mark.parametrize("count", [0, MAX_RAZER_SEGMENTS + 1])
    def test_a_frame_has_1_to_255_segments(self, count: int) -> None:
        with pytest.raises(ValueError, match="1 to 255 segments"):
            build_razer_frame(np.zeros((count, 3), dtype=np.uint8))
