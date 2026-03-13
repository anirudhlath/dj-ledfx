from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GoveeDeviceRecord:
    """Discovered Govee device on the LAN."""

    ip: str
    device_id: str
    sku: str
    wifi_version: str
    ble_version: str


@dataclass(frozen=True, slots=True)
class GoveeDeviceCapability:
    """Device capability info from SKU registry."""

    is_rgbic: bool
    segment_count: int  # 0 for non-RGBIC
