from __future__ import annotations

import struct

import numpy as np

from dj_ledfx.devices.lifx.packet import (
    LifxPacket,
    build_echo_request,
    build_set_color,
    build_set_extended_color_zones,
    build_set_tile_state64,
    parse_echo_response,
    parse_state_device_chain,
    parse_state_extended_color_zones,
    parse_state_service,
    parse_state_version,
    rgb_array_to_hsbk,
    rgb_to_hsbk,
)
from dj_ledfx.devices.lifx.types import TileInfo


class TestLifxPacketHeader:
    def test_pack_header_size(self) -> None:
        pkt = LifxPacket(
            tagged=False, source=12345, target=b"\x00" * 8,
            ack_required=False, res_required=False, sequence=0,
            msg_type=2, payload=b"",
        )
        data = pkt.pack()
        assert len(data) == 36  # header only, no payload

    def test_pack_size_field_includes_payload(self) -> None:
        payload = b"\x01\x02\x03"
        pkt = LifxPacket(
            tagged=False, source=0, target=b"\x00" * 8,
            ack_required=False, res_required=False, sequence=0,
            msg_type=102, payload=payload,
        )
        data = pkt.pack()
        size = int.from_bytes(data[0:2], "little")
        assert size == 36 + 3

    def test_pack_protocol_field(self) -> None:
        pkt = LifxPacket(
            tagged=True, source=0, target=b"\x00" * 8,
            ack_required=False, res_required=False, sequence=0,
            msg_type=2, payload=b"",
        )
        data = pkt.pack()
        flags = int.from_bytes(data[2:4], "little")
        # addressable=1, tagged=1, protocol=1024
        assert flags & 0x1000  # addressable bit
        assert flags & 0x2000  # tagged bit
        assert (flags & 0x0FFF) == 1024  # protocol

    def test_pack_source_field(self) -> None:
        pkt = LifxPacket(
            tagged=False, source=0xDEADBEEF, target=b"\x00" * 8,
            ack_required=False, res_required=False, sequence=0,
            msg_type=2, payload=b"",
        )
        data = pkt.pack()
        source = int.from_bytes(data[4:8], "little")
        assert source == 0xDEADBEEF

    def test_pack_target_field(self) -> None:
        mac = b"\xd0\x73\xd5\x01\x02\x03\x00\x00"
        pkt = LifxPacket(
            tagged=False, source=0, target=mac,
            ack_required=False, res_required=False, sequence=0,
            msg_type=2, payload=b"",
        )
        data = pkt.pack()
        assert data[8:16] == mac

    def test_pack_ack_res_flags(self) -> None:
        pkt = LifxPacket(
            tagged=False, source=0, target=b"\x00" * 8,
            ack_required=True, res_required=True, sequence=42,
            msg_type=2, payload=b"",
        )
        data = pkt.pack()
        assert data[22] & 0x02  # ack_required
        assert data[22] & 0x01  # res_required
        assert data[23] == 42   # sequence

    def test_pack_msg_type(self) -> None:
        pkt = LifxPacket(
            tagged=False, source=0, target=b"\x00" * 8,
            ack_required=False, res_required=False, sequence=0,
            msg_type=715, payload=b"",
        )
        data = pkt.pack()
        msg_type = int.from_bytes(data[32:34], "little")
        assert msg_type == 715

    def test_unpack_roundtrip(self) -> None:
        original = LifxPacket(
            tagged=True, source=9999, target=b"\xAA\xBB\xCC\xDD\xEE\xFF\x00\x00",
            ack_required=True, res_required=False, sequence=200,
            msg_type=102, payload=b"\x01\x02\x03\x04",
        )
        data = original.pack()
        parsed = LifxPacket.unpack(data)
        assert parsed.tagged == original.tagged
        assert parsed.source == original.source
        assert parsed.target == original.target
        assert parsed.ack_required == original.ack_required
        assert parsed.res_required == original.res_required
        assert parsed.sequence == original.sequence
        assert parsed.msg_type == original.msg_type
        assert parsed.payload == original.payload


class TestPayloadBuilders:
    def test_build_set_color_size(self) -> None:
        payload = build_set_color((0, 65535, 65535, 3500), duration_ms=0)
        assert len(payload) == 13

    def test_build_echo_request_size(self) -> None:
        payload = build_echo_request(b"\xAA" * 64)
        assert len(payload) == 64

    def test_build_set_tile_state64_size(self) -> None:
        colors = [(0, 0, 0, 0)] * 64
        payload = build_set_tile_state64(0, 1, 0, 0, 8, 0, colors)
        assert len(payload) == 522

    def test_build_set_extended_color_zones_size(self) -> None:
        colors = [(0, 0, 0, 0)] * 10
        payload = build_set_extended_color_zones(0, 0, 0, 10, colors)
        assert len(payload) == 664


class TestPayloadParsers:
    def test_parse_state_service(self) -> None:
        payload = struct.pack("<BI", 1, 56700)
        service, port = parse_state_service(payload)
        assert service == 1
        assert port == 56700

    def test_parse_state_version(self) -> None:
        payload = struct.pack("<III", 1, 55, 0)
        vendor, product, version = parse_state_version(payload)
        assert vendor == 1
        assert product == 55

    def test_parse_echo_response(self) -> None:
        data = b"\xBB" * 64
        assert parse_echo_response(data) == data

    def test_parse_state_extended_color_zones(self) -> None:
        header = struct.pack("<HH", 10, 0)
        hsbk_data = struct.pack("<4H", 100, 200, 300, 3500) * 10
        payload = header + hsbk_data
        zone_count, zone_index, colors = parse_state_extended_color_zones(payload)
        assert zone_count == 10
        assert zone_index == 0
        assert len(colors) == 10
        assert colors[0] == (100, 200, 300, 3500)

    def test_parse_state_device_chain(self) -> None:
        header = struct.pack("<BB", 0, 1)
        tile_data = struct.pack(
            "<hhhh ff BB x III QQ HH I",
            100, -200, 9800,
            0,
            1.0, 2.5,
            8, 8,
            1, 55, 0,
            0, 0,
            0, 0,
            0,
        )
        payload = header + tile_data
        tiles = parse_state_device_chain(payload)
        assert len(tiles) == 1
        assert tiles[0].width == 8
        assert tiles[0].height == 8
        assert abs(tiles[0].user_x - 1.0) < 0.01
        assert abs(tiles[0].user_y - 2.5) < 0.01


class TestColorConversion:
    def test_pure_red(self) -> None:
        h, s, b, k = rgb_to_hsbk(255, 0, 0)
        assert h == 0
        assert s == 65535
        assert b == 65535

    def test_pure_green(self) -> None:
        h, s, b, k = rgb_to_hsbk(0, 255, 0)
        assert abs(h - 21845) < 2

    def test_pure_white(self) -> None:
        h, s, b, k = rgb_to_hsbk(255, 255, 255, kelvin=4000)
        assert s == 0
        assert b == 65535
        assert k == 4000

    def test_black(self) -> None:
        h, s, b, k = rgb_to_hsbk(0, 0, 0)
        assert b == 0

    def test_array_conversion_shape(self) -> None:
        colors = np.array([[255, 0, 0], [0, 255, 0], [0, 0, 255]], dtype=np.uint8)
        result = rgb_array_to_hsbk(colors)
        assert result.shape == (3, 4)
        assert result.dtype == np.uint16

    def test_array_matches_scalar(self) -> None:
        colors = np.array([[255, 0, 0], [0, 255, 0], [0, 0, 255]], dtype=np.uint8)
        result = rgb_array_to_hsbk(colors, kelvin=3500)
        for i, (r, g, b_val) in enumerate(colors):
            scalar = rgb_to_hsbk(int(r), int(g), int(b_val), kelvin=3500)
            for j in range(4):
                assert abs(int(result[i, j]) - scalar[j]) <= 1
