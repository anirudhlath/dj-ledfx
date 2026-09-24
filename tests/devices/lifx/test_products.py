from __future__ import annotations

import hashlib
from importlib.resources import files

import pytest

from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.devices.lifx.products import PRODUCTS_SHA256, lifx_capabilities


def test_vendored_registry_matches_the_pin() -> None:
    data = (files("dj_ledfx.devices.lifx") / "data" / "products.json").read_bytes()
    assert hashlib.sha256(data).hexdigest() == PRODUCTS_SHA256


def _caps(pid: int, firmware: tuple[int, int] | None) -> DeviceCapabilities:
    caps, _relays = lifx_capabilities(pid, firmware)
    return caps


@pytest.mark.parametrize("pid", [57, 68, 137, 138, 185, 186, 215, 216])
def test_candles_are_matrix_lights(pid: int) -> None:
    caps = _caps(pid, (3, 90))
    assert caps.matrix and not caps.chain and not caps.multizone


def test_tile_is_a_matrix_chain() -> None:
    caps = _caps(55, (3, 70))
    assert caps.matrix and caps.chain


@pytest.mark.parametrize("pid", [171, 173, 176, 177, 217, 218])
def test_spot_path_ceiling_and_tube_are_matrix_lights(pid: int) -> None:
    assert _caps(pid, (4, 10)).matrix


@pytest.mark.parametrize("pid", [141, 142, 205, 206])
def test_neon_is_extended_multizone(pid: int) -> None:
    caps = _caps(pid, (4, 10))
    assert caps.multizone and caps.extended_multizone


def test_first_lifx_z_has_no_extended_multizone() -> None:
    caps = _caps(31, (1, 22))
    assert caps.multizone and not caps.extended_multizone


def test_upgrades_apply_from_their_firmware_version() -> None:
    assert not _caps(32, (2, 76)).extended_multizone
    assert _caps(32, (2, 77)).extended_multizone
    assert not _caps(32, None).extended_multizone


def test_temperature_range_upgrade() -> None:
    assert _caps(27, (2, 70)).temperature_range == (2500, 9000)
    assert _caps(27, (2, 80)).temperature_range == (1500, 9000)


def test_switch_and_clean_bulb_are_no_longer_misclassified() -> None:
    switch, relays = lifx_capabilities(70, None)
    clean, clean_relays = lifx_capabilities(90, None)
    assert relays and not switch.matrix and not switch.multizone
    assert not clean_relays and not clean.multizone and not clean.matrix


def test_unknown_product() -> None:
    caps, relays = lifx_capabilities(9999, (3, 0))
    assert not relays
    assert caps.protocol == "LIFX"
    assert caps.model == "LIFX product 9999"
    assert caps.colour and not caps.matrix and not caps.multizone


def test_capabilities_carry_model_firmware_and_features() -> None:
    caps = _caps(217, (4, 10))
    assert caps.model == "LIFX Tube"
    assert caps.firmware_version == "4.10"
    assert caps.matrix and caps.colour
    assert caps.temperature_range == (1500, 9000)
    assert _caps(217, None).firmware_version is None
