from __future__ import annotations

from dj_ledfx.devices.govee.types import GoveeDeviceCapability

# razer and form: the light-output plan's ruling 12; segments and the strip's razer: what the
# lamps showed in its Task 8. The upright lamp takes razer frames of 14 segments, its first
# at the bottom (two of three showed nothing for frames of 15), and stands; the strip takes
# razer frames of 15.
SKU_REGISTRY: dict[str, GoveeDeviceCapability] = {
    "H6076": GoveeDeviceCapability(is_rgbic=True, segment_count=14, razer=True, form="upright"),
    "H61A2": GoveeDeviceCapability(is_rgbic=True, segment_count=15, razer=True),
}

DEFAULT_CAPABILITY = GoveeDeviceCapability(is_rgbic=False, segment_count=0)


def get_device_capability(sku: str) -> GoveeDeviceCapability:
    return SKU_REGISTRY.get(sku, DEFAULT_CAPABILITY)
