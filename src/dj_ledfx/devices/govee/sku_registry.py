from __future__ import annotations

from dj_ledfx.devices.govee.types import GoveeDeviceCapability

# razer and form: the light-output plan's ruling 12. The upright lamp takes razer frames and
# stands; the strip keeps razer off until one is checked.
SKU_REGISTRY: dict[str, GoveeDeviceCapability] = {
    "H6076": GoveeDeviceCapability(is_rgbic=True, segment_count=15, razer=True, form="upright"),
    "H61A2": GoveeDeviceCapability(is_rgbic=True, segment_count=15),
}

DEFAULT_CAPABILITY = GoveeDeviceCapability(is_rgbic=False, segment_count=0)


def get_device_capability(sku: str) -> GoveeDeviceCapability:
    return SKU_REGISTRY.get(sku, DEFAULT_CAPABILITY)
