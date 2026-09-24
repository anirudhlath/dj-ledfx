"""Replies recorded from this home's lights (scripts/lifx_record_fixtures.py) parse."""

from __future__ import annotations

from pathlib import Path

import pytest
from lifx_fakes import read_hex

from dj_ledfx.devices.lifx.packet import (
    MultiZoneEffectType,
    TileEffectType,
    parse_state_device_chain,
    parse_state_host_firmware,
    parse_state_multizone_effect,
    parse_state_tile_effect,
    parse_state_version,
)

RECORDED = Path(__file__).parents[2] / "fixtures" / "lifx" / "recorded"


def _recorded(message: str) -> list[Path]:
    return sorted(RECORDED.glob(f"*-{message}.hex"))


def _pid(path: Path) -> int:
    return int(path.name.split("-", 1)[0])


@pytest.mark.parametrize("path", _recorded("state_host_firmware"), ids=lambda p: p.stem)
def test_host_firmware(path: Path) -> None:
    major, _minor = parse_state_host_firmware(read_hex(path))
    assert major >= 2


@pytest.mark.parametrize("path", _recorded("state_version"), ids=lambda p: p.stem)
def test_version_names_the_product(path: Path) -> None:
    vendor, product, _version = parse_state_version(read_hex(path))
    assert (vendor, product) == (1, _pid(path))


@pytest.mark.parametrize("path", _recorded("state_device_chain"), ids=lambda p: p.stem)
def test_device_chain(path: Path) -> None:
    tiles = parse_state_device_chain(read_hex(path))
    assert 1 <= len(tiles) <= 16
    assert all(1 <= tile.width <= 16 and 1 <= tile.height <= 16 for tile in tiles)


@pytest.mark.parametrize("path", _recorded("state_tile_effect"), ids=lambda p: p.stem)
def test_tile_effect(path: Path) -> None:
    state = parse_state_tile_effect(read_hex(path))
    assert state.effect in {kind.value for kind in TileEffectType}
    assert state.effect == TileEffectType.OFF or state.speed_ms > 0


@pytest.mark.parametrize("path", _recorded("state_multizone_effect"), ids=lambda p: p.stem)
def test_multizone_effect(path: Path) -> None:
    state = parse_state_multizone_effect(read_hex(path))
    assert state.effect in {kind.value for kind in MultiZoneEffectType}
    assert state.effect == MultiZoneEffectType.OFF or state.speed_ms > 0
