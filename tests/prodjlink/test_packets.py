import struct

from dj_ledfx.prodjlink.constants import (
    BEAT_PACKET_LEN,
    CAPABILITY_CDJ3000,
    MAGIC_HEADER,
    OFFSET_BEAT_NUMBER,
    OFFSET_BPM,
    OFFSET_CAPABILITY,
    OFFSET_DEVICE_NAME,
    OFFSET_DEVICE_NUMBER,
    OFFSET_NEXT_BEAT_MS,
    OFFSET_PACKET_TYPE,
    OFFSET_PITCH,
    PACKET_TYPE_BEAT,
    PITCH_CENTER,
)
from dj_ledfx.prodjlink.packets import BeatPacket, parse_beat_packet


def _build_beat_packet(
    *,
    bpm_raw: int = 12800,
    pitch_raw: int = PITCH_CENTER,
    beat_number: int = 1,
    next_beat_ms: int = 468,
    device_number: int = 1,
    device_name: str = "XDJ-AZ",
    capability: int = CAPABILITY_CDJ3000,
) -> bytes:
    buf = bytearray(BEAT_PACKET_LEN)
    buf[0:10] = MAGIC_HEADER
    buf[OFFSET_PACKET_TYPE] = PACKET_TYPE_BEAT
    name_bytes = device_name.encode("ascii")[:20].ljust(20, b"\x00")
    buf[OFFSET_DEVICE_NAME : OFFSET_DEVICE_NAME + 20] = name_bytes
    buf[OFFSET_DEVICE_NUMBER] = device_number
    struct.pack_into(">I", buf, OFFSET_NEXT_BEAT_MS, next_beat_ms)
    struct.pack_into(">I", buf, OFFSET_PITCH, pitch_raw)
    struct.pack_into(">H", buf, OFFSET_BPM, bpm_raw)
    buf[OFFSET_BEAT_NUMBER] = beat_number
    buf[OFFSET_CAPABILITY] = capability
    return bytes(buf)


def test_parse_basic_beat_packet() -> None:
    data = _build_beat_packet()
    result = parse_beat_packet(data)
    assert result is not None
    assert isinstance(result, BeatPacket)
    assert result.bpm == 128.0
    assert result.pitch_percent == 0.0
    assert result.beat_number == 1
    assert result.next_beat_ms == 468
    assert result.device_number == 1
    assert result.device_name == "XDJ-AZ"


def test_parse_pitched_bpm() -> None:
    pitch_raw = PITCH_CENTER + int(6.0 * 10485.76)
    data = _build_beat_packet(bpm_raw=12800, pitch_raw=pitch_raw)
    result = parse_beat_packet(data)
    assert result is not None
    assert abs(result.pitch_percent - 6.0) < 0.01
    assert abs(result.pitch_adjusted_bpm - 128.0 * 1.06) < 0.1


def test_parse_rejects_wrong_magic() -> None:
    data = b"\x00" * BEAT_PACKET_LEN
    assert parse_beat_packet(data) is None


def test_parse_rejects_short_packet() -> None:
    assert parse_beat_packet(b"\x00" * 10) is None


def test_parse_rejects_non_beat_packet() -> None:
    data = bytearray(_build_beat_packet())
    data[OFFSET_PACKET_TYPE] = 0x0A
    assert parse_beat_packet(bytes(data)) is None


def test_parse_rejects_old_hardware() -> None:
    data = _build_beat_packet(capability=0x11)
    assert parse_beat_packet(data) is None


def test_beat_number_values() -> None:
    for beat in (1, 2, 3, 4):
        data = _build_beat_packet(beat_number=beat)
        result = parse_beat_packet(data)
        assert result is not None
        assert result.beat_number == beat
