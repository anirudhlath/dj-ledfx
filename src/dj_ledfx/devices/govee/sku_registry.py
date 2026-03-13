from __future__ import annotations

from dj_ledfx.devices.govee.types import GoveeDeviceCapability

SKU_REGISTRY: dict[str, GoveeDeviceCapability] = {
    "H6076": GoveeDeviceCapability(is_rgbic=True, segment_count=15),
    "H61A2": GoveeDeviceCapability(is_rgbic=True, segment_count=15),
}

DEFAULT_CAPABILITY = GoveeDeviceCapability(is_rgbic=False, segment_count=0)


def get_device_capability(sku: str) -> GoveeDeviceCapability:
    return SKU_REGISTRY.get(sku, DEFAULT_CAPABILITY)


def get_segment_count(sku: str, config_override: int | None = None) -> int:
    if config_override is not None:
        return config_override
    return get_device_capability(sku).segment_count
