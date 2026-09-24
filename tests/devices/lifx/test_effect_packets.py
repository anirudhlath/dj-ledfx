from __future__ import annotations

from pathlib import Path

import pytest
from lifx_fakes import read_hex

from dj_ledfx.devices.lifx.packet import (
    MultiZoneEffectType,
    TileEffectType,
    Waveform,
    build_get_tile_effect,
    build_set_light_power,
    build_set_multizone_effect,
    build_set_tile_effect,
    build_set_waveform,
    parse_state_host_firmware,
    parse_state_multizone_effect,
    parse_state_tile_effect,
)

FIXTURES = Path(__file__).parents[2] / "fixtures" / "lifx"


def test_set_tile_effect_flame_matches_fixture() -> None:
    payload = build_set_tile_effect(TileEffectType.FLAME, 4000)
    assert len(payload) == 188
    assert payload == read_hex(FIXTURES / "set_tile_effect_flame.hex")


def test_set_tile_effect_morph_matches_fixture() -> None:
    palette = [(0, 65535, 65535, 3500), (21845, 65535, 65535, 3500), (43690, 65535, 65535, 3500)]
    payload = build_set_tile_effect(TileEffectType.MORPH, 6000, palette)
    assert payload == read_hex(FIXTURES / "set_tile_effect_morph.hex")


def test_set_tile_effect_keeps_at_most_16_palette_colours() -> None:
    payload = build_set_tile_effect(
        TileEffectType.MORPH, 1000, [(i, 0, 0, 3500) for i in range(20)]
    )
    assert len(payload) == 188
    assert payload[59] == 16


def test_get_tile_effect_is_two_reserved_bytes() -> None:
    assert build_get_tile_effect() == b"\x00\x00"


def test_set_multizone_effect_move_matches_fixture() -> None:
    payload = build_set_multizone_effect(MultiZoneEffectType.MOVE, 8000)
    assert len(payload) == 59
    assert payload == read_hex(FIXTURES / "set_multizone_effect_move.hex")


def test_set_multizone_effect_reverse_sets_direction_zero() -> None:
    payload = build_set_multizone_effect(MultiZoneEffectType.MOVE, 8000, reverse=True)
    assert payload[31:35] == b"\x00\x00\x00\x00"


def test_set_waveform_matches_fixture() -> None:
    payload = build_set_waveform((0, 65535, 32768, 3500), 4000, 1e6, Waveform.SINE)
    assert len(payload) == 21
    assert payload == read_hex(FIXTURES / "set_waveform_sine.hex")


def test_set_light_power_matches_fixture() -> None:
    assert build_set_light_power(True) == read_hex(FIXTURES / "set_light_power_on.hex")
    assert build_set_light_power(False) == b"\x00\x00\x00\x00\x00\x00"


def test_parse_state_tile_effect() -> None:
    state = parse_state_tile_effect(read_hex(FIXTURES / "state_tile_effect_flame.hex"))
    assert state.instance_id == 7
    assert state.effect == TileEffectType.FLAME
    assert state.speed_ms == 4000
    assert state.palette == ()


def test_parse_state_tile_effect_reads_the_palette() -> None:
    palette = [(100, 200, 300, 3500), (400, 500, 600, 4000)]
    set_payload = build_set_tile_effect(TileEffectType.MORPH, 5000, palette, instance_id=3)
    # StateTileEffect is SetTileEffect with one reserved byte fewer at the front.
    state = parse_state_tile_effect(set_payload[1:])
    assert state.effect == TileEffectType.MORPH
    assert state.instance_id == 3
    assert state.palette == tuple(palette)


def test_parse_state_tile_effect_rejects_short_payloads() -> None:
    with pytest.raises(ValueError):
        parse_state_tile_effect(b"\x00" * 20)


def test_parse_state_multizone_effect() -> None:
    state = parse_state_multizone_effect(read_hex(FIXTURES / "state_multizone_effect_move.hex"))
    assert state.instance_id == 9
    assert state.effect == MultiZoneEffectType.MOVE
    assert state.speed_ms == 8000
    assert state.reverse is True


def test_parse_state_host_firmware() -> None:
    assert parse_state_host_firmware(read_hex(FIXTURES / "state_host_firmware.hex")) == (3, 90)
