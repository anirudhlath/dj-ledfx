from __future__ import annotations

import hashlib
from importlib.resources import files

import pytest

from dj_ledfx.devices.lifx.products import PRODUCTS_SHA256, lifx_capabilities, lifx_product


def test_vendored_registry_matches_the_pin() -> None:
    data = (files("dj_ledfx.devices.lifx") / "data" / "products.json").read_bytes()
    assert hashlib.sha256(data).hexdigest() == PRODUCTS_SHA256


@pytest.mark.parametrize("pid", [57, 68, 137, 138, 185, 186, 215, 216])
def test_candles_are_matrix_lights(pid: int) -> None:
    product = lifx_product(pid, (3, 90))
    assert product is not None
    assert product.matrix and not product.chain and not product.multizone


def test_tile_is_a_matrix_chain() -> None:
    product = lifx_product(55, (3, 70))
    assert product is not None and product.matrix and product.chain


@pytest.mark.parametrize("pid", [171, 173, 176, 177, 217, 218])
def test_spot_path_ceiling_and_tube_are_matrix_lights(pid: int) -> None:
    product = lifx_product(pid, (4, 10))
    assert product is not None and product.matrix


@pytest.mark.parametrize("pid", [141, 142, 205, 206])
def test_neon_is_extended_multizone(pid: int) -> None:
    product = lifx_product(pid, (4, 10))
    assert product is not None and product.multizone and product.extended_multizone


def test_first_lifx_z_has_no_extended_multizone() -> None:
    product = lifx_product(31, (1, 22))
    assert product is not None and product.multizone and not product.extended_multizone


def test_upgrades_apply_from_their_firmware_version() -> None:
    before = lifx_product(32, (2, 76))
    after = lifx_product(32, (2, 77))
    unknown = lifx_product(32, None)
    assert before is not None and not before.extended_multizone
    assert after is not None and after.extended_multizone
    assert unknown is not None and not unknown.extended_multizone


def test_temperature_range_upgrade() -> None:
    old = lifx_product(27, (2, 70))
    new = lifx_product(27, (2, 80))
    assert old is not None and old.temperature_range == (2500, 9000)
    assert new is not None and new.temperature_range == (1500, 9000)


def test_switch_and_clean_bulb_are_no_longer_misclassified() -> None:
    switch = lifx_product(70, None)
    clean = lifx_product(90, None)
    assert switch is not None and switch.relays and not switch.matrix and not switch.multizone
    assert clean is not None and not clean.multizone and not clean.matrix


def test_unknown_product() -> None:
    assert lifx_product(9999, (3, 0)) is None
    caps = lifx_capabilities(9999, (3, 0))
    assert caps.protocol == "LIFX"
    assert caps.model == "LIFX product 9999"
    assert caps.colour and not caps.matrix and not caps.multizone


def test_capabilities_carry_model_firmware_and_features() -> None:
    caps = lifx_capabilities(217, (4, 10))
    assert caps.model == "LIFX Tube"
    assert caps.firmware_version == "4.10"
    assert caps.matrix and caps.colour
    assert caps.temperature_range == (1500, 9000)
    assert lifx_capabilities(217, None).firmware_version is None
