from __future__ import annotations

import base64

import numpy as np

from dj_ledfx.devices.govee.protocol import (
    build_ble_packet,
    build_brightness_message,
    build_pt_real_message,
    build_scan_message,
    build_segment_color_packet,
    build_solid_color_message,
    build_status_query,
    build_turn_message,
    encode_segment_mask,
    map_colors_to_segments,
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


class TestBuildBlePacket:
    def test_packet_length(self) -> None:
        pkt = build_ble_packet(0x05, 0x0B, b"\xff\x00\x00")
        assert len(pkt) == 20

    def test_starts_with_identifier(self) -> None:
        pkt = build_ble_packet(0x05, 0x0B, b"\xff\x00\x00")
        assert pkt[0] == 0x33

    def test_command_type_and_sub(self) -> None:
        pkt = build_ble_packet(0x05, 0x0B, b"\xff\x00\x00")
        assert pkt[1] == 0x05
        assert pkt[2] == 0x0B

    def test_checksum_valid(self) -> None:
        pkt = build_ble_packet(0x05, 0x0B, b"\xff\x00\x00")
        assert xor_checksum(pkt[:19]) == pkt[19]

    def test_payload_embedded(self) -> None:
        pkt = build_ble_packet(0x05, 0x0B, b"\xaa\xbb\xcc")
        assert pkt[3] == 0xAA
        assert pkt[4] == 0xBB
        assert pkt[5] == 0xCC


class TestEncodeSegmentMask:
    def test_segment_0(self) -> None:
        mask = encode_segment_mask([0], total_segments=15)
        assert mask == bytes([0x01, 0x00])

    def test_segment_8(self) -> None:
        mask = encode_segment_mask([8], total_segments=15)
        assert mask == bytes([0x00, 0x01])

    def test_all_15_segments(self) -> None:
        mask = encode_segment_mask(list(range(15)), total_segments=15)
        assert mask == bytes([0xFF, 0x7F])

    def test_segments_0_and_14(self) -> None:
        mask = encode_segment_mask([0, 14], total_segments=15)
        assert mask == bytes([0x01, 0x40])


class TestBuildSegmentColorPacket:
    def test_red_segment_0(self) -> None:
        mask = encode_segment_mask([0], total_segments=15)
        pkt = build_segment_color_packet(255, 0, 0, mask)
        assert len(pkt) == 20
        assert pkt[0] == 0x33
        assert pkt[1] == 0x05
        assert pkt[2] == 0x0B
        assert pkt[3:6] == bytes([255, 0, 0])
        assert pkt[8] == 0x01
        assert pkt[9] == 0x00
        assert xor_checksum(pkt[:19]) == pkt[19]


class TestBuildPtRealMessage:
    def test_single_packet(self) -> None:
        pkt = build_ble_packet(0x05, 0x0B, b"\xff\x00\x00")
        msg = build_pt_real_message([pkt])
        assert msg["msg"]["cmd"] == "ptReal"
        commands = msg["msg"]["data"]["command"]
        assert len(commands) == 1
        decoded = base64.b64decode(commands[0])
        assert decoded == pkt

    def test_multiple_packets(self) -> None:
        pkts = [build_ble_packet(0x05, 0x0B, bytes([i, 0, 0])) for i in range(3)]
        msg = build_pt_real_message(pkts)
        assert len(msg["msg"]["data"]["command"]) == 3


class TestMapColorsToSegments:
    def test_exact_match(self) -> None:
        colors = np.array([[255, 0, 0], [0, 255, 0], [0, 0, 255]], dtype=np.uint8)
        result = map_colors_to_segments(colors, 3)
        assert result == [(255, 0, 0), (0, 255, 0), (0, 0, 255)]

    def test_downsample_averaging(self) -> None:
        colors = np.array([[200, 0, 0], [100, 0, 0], [0, 200, 0], [0, 100, 0]], dtype=np.uint8)
        result = map_colors_to_segments(colors, 2)
        assert result == [(150, 0, 0), (0, 150, 0)]

    def test_single_segment(self) -> None:
        colors = np.array([[100, 0, 0], [0, 100, 0], [0, 0, 100]], dtype=np.uint8)
        result = map_colors_to_segments(colors, 1)
        r, g, b = result[0]
        assert r == 33
        assert g == 33
        assert b == 33

    def test_more_segments_than_leds(self) -> None:
        colors = np.array([[255, 0, 0], [0, 0, 255]], dtype=np.uint8)
        result = map_colors_to_segments(colors, 4)
        assert len(result) == 4
        assert result[0] == (255, 0, 0)
        assert result[1] == (255, 0, 0)
        assert result[2] == (0, 0, 255)
        assert result[3] == (0, 0, 255)
