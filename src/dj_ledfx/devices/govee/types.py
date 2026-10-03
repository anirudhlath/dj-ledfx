from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True)
class GoveeDeviceRecord:
    """Discovered Govee device on the LAN."""

    ip: str
    device_id: str
    sku: str
    wifi_version: str
    ble_version: str


GoveeForm = Literal["upright", "strip"]  # how a lamp's segments run: up a pole, or along


@dataclass(frozen=True, slots=True)
class GoveeDeviceCapability:
    """What the SKU table knows of a model."""

    is_rgbic: bool
    segment_count: int  # 0 for non-RGBIC
    razer: bool = False  # it takes razer (DreamView) frames: one colour per segment
    form: GoveeForm = "strip"
    segments_from_top: bool = False  # an upright lamp's segment 0 is at the top
