"""What a light can do, and what the app can read back from it (spec §6.3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

LightProtocol = Literal["LIFX", "Govee", "OpenRGB"]


@dataclass(frozen=True, slots=True)
class DeviceCapabilities:
    protocol: LightProtocol
    model: str = ""
    colour: bool = True
    multizone: bool = False
    extended_multizone: bool = False
    matrix: bool = False
    chain: bool = False
    temperature_range: tuple[int, int] | None = None
    firmware_version: str | None = None
    openrgb_modes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LightReading:
    power: bool | None  # None: the light can't tell us
    colour: tuple[int, int, int] | None  # 8-bit sRGB, None when unknown


class FirmwareRejected(Exception):
    """The light refused a firmware command: it can't run that effect."""


class NoAnswer(Exception):
    """The light didn't answer a command it must confirm. Not a refusal: ask it again."""


def protocol_of(backend_or_type: str) -> LightProtocol:
    """Map a DeviceInfo backend (or a ghost's device_type) to the contract's protocol."""
    key = backend_or_type.lower()
    if key.startswith("lifx"):
        return "LIFX"
    if key.startswith("govee"):
        return "Govee"
    return "OpenRGB"
