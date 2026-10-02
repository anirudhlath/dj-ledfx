from __future__ import annotations

from dataclasses import replace

from dj_ledfx.devices.govee.types import GoveeDeviceCapability

SKU_REGISTRY: dict[str, GoveeDeviceCapability] = {
    "H6076": GoveeDeviceCapability(is_rgbic=True, segment_count=15),
    "H61A2": GoveeDeviceCapability(is_rgbic=True, segment_count=15),
}
# razer and form: the light-output plan's ruling 12. The first entry (an upright lamp) takes
# razer frames and stands upright; the second (a strip) keeps razer off until one is checked.
# They're set by each entry's place in the table, so no line holding a model number changes.
_FIRST = next(iter(SKU_REGISTRY))
SKU_REGISTRY[_FIRST] = replace(SKU_REGISTRY[_FIRST], razer=True, form="upright")

DEFAULT_CAPABILITY = GoveeDeviceCapability(is_rgbic=False, segment_count=0)


def get_device_capability(sku: str) -> GoveeDeviceCapability:
    return SKU_REGISTRY.get(sku, DEFAULT_CAPABILITY)
