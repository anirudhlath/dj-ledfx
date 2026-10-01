from tempo_fakes import PLAYER, beat_packet

from dj_ledfx.prodjlink.constants import BEAT_PACKET_LEN, OFFSET_PACKET_TYPE
from dj_ledfx.prodjlink.packets import BeatPacket, parse_beat_packet


def test_parse_basic_beat_packet() -> None:
    data = beat_packet(next_beat_ms=468)
    result = parse_beat_packet(data)
    assert result is not None
    assert isinstance(result, BeatPacket)
    assert result.bpm == 128.0
    assert result.pitch_percent == 0.0
    assert result.beat_number == 1
    assert result.next_beat_ms == 468
    assert result.device_number == 1
    assert result.device_name == PLAYER


def test_parse_pitched_bpm() -> None:
    data = beat_packet(bpm=128.0, pitch_percent=6.0)
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
    data = bytearray(beat_packet())
    data[OFFSET_PACKET_TYPE] = 0x0A
    assert parse_beat_packet(bytes(data)) is None


def test_parse_rejects_old_hardware() -> None:
    data = beat_packet(capability=0x11)
    assert parse_beat_packet(data) is None


def test_beat_number_values() -> None:
    for beat in (1, 2, 3, 4):
        data = beat_packet(beat=beat)
        result = parse_beat_packet(data)
        assert result is not None
        assert result.beat_number == beat
