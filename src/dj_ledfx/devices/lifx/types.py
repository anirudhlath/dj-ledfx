from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LifxDeviceRecord:
    """Discovered LIFX device before adapter creation."""

    mac: bytes  # 6-byte MAC address
    ip: str  # device IP (from UDP response source)
    port: int  # service port (from StateService)
    vendor: int  # vendor ID (1 = LIFX)
    product: int  # product ID (determines device type)


@dataclass(frozen=True, slots=True)
class TileInfo:
    """Spatial metadata for a single tile in a chain."""

    user_x: float
    user_y: float
    width: int
    height: int
    accel_x: int
    accel_y: int
    accel_z: int
