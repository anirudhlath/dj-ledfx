"""LIFX product capabilities from LIFX's own registry (spec §6.3).

`data/products.json` is a pinned copy of https://github.com/LIFX/products. To update it,
download products.json from a newer commit, update PRODUCTS_URL and PRODUCTS_SHA256,
and run tests/devices/lifx/test_products.py.
"""

from __future__ import annotations

import functools
import json
from dataclasses import dataclass
from importlib.resources import files
from typing import Any

from dj_ledfx.devices.capabilities import DeviceCapabilities

PRODUCTS_URL = (
    "https://raw.githubusercontent.com/LIFX/products/"
    "8adbe485db11621639f693f3a1510603f029c902/products.json"
)
PRODUCTS_SHA256 = "09f6b87367ea3a974cd4be9e7a562db73e1776d012854fb487b00ac9be520360"


@dataclass(frozen=True, slots=True)
class LifxProduct:
    pid: int
    name: str
    colour: bool
    multizone: bool
    extended_multizone: bool
    matrix: bool
    chain: bool
    relays: bool  # a switch, not a light
    temperature_range: tuple[int, int] | None


@functools.cache
def _registry() -> dict[int, tuple[dict[str, Any], dict[int, dict[str, Any]]]]:
    """vid -> (vendor defaults, pid -> product entry)."""
    raw = (files("dj_ledfx.devices.lifx") / "data" / "products.json").read_bytes()
    vendors: list[dict[str, Any]] = json.loads(raw)
    return {
        int(vendor["vid"]): (
            dict(vendor.get("defaults", {})),
            {int(product["pid"]): product for product in vendor["products"]},
        )
        for vendor in vendors
    }


def lifx_product(pid: int, firmware: tuple[int, int] | None, vid: int = 1) -> LifxProduct | None:
    vendor = _registry().get(vid)
    if vendor is None:
        return None
    defaults, products = vendor
    entry = products.get(pid)
    if entry is None:
        return None
    features: dict[str, Any] = {**defaults, **entry.get("features", {})}
    if firmware is not None:
        for upgrade in entry.get("upgrades", []):
            if firmware >= (int(upgrade["major"]), int(upgrade["minor"])):
                features.update(upgrade.get("features", {}))
    temperature = features.get("temperature_range")
    return LifxProduct(
        pid=pid,
        name=str(entry["name"]),
        colour=bool(features.get("color", False)),
        multizone=bool(features.get("multizone", False)),
        extended_multizone=bool(features.get("extended_multizone", False)),
        matrix=bool(features.get("matrix", False)),
        chain=bool(features.get("chain", False)),
        relays=bool(features.get("relays", False)),
        temperature_range=(int(temperature[0]), int(temperature[1])) if temperature else None,
    )


def lifx_capabilities(
    pid: int, firmware: tuple[int, int] | None, vid: int = 1
) -> DeviceCapabilities:
    version = f"{firmware[0]}.{firmware[1]}" if firmware is not None else None
    product = lifx_product(pid, firmware, vid)
    if product is None:
        return DeviceCapabilities(
            protocol="LIFX", model=f"LIFX product {pid}", firmware_version=version
        )
    return DeviceCapabilities(
        protocol="LIFX",
        model=product.name,
        colour=product.colour,
        multizone=product.multizone,
        extended_multizone=product.extended_multizone,
        matrix=product.matrix,
        chain=product.chain,
        temperature_range=product.temperature_range,
        firmware_version=version,
    )
