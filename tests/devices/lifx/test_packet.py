from __future__ import annotations

from dj_ledfx.devices.lifx.packet import LifxPacket


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
