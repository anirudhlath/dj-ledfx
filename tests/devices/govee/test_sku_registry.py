from __future__ import annotations

from dj_ledfx.devices.govee.sku_registry import (
    DEFAULT_CAPABILITY,
    SKU_REGISTRY,
    get_device_capability,
)


def test_every_entry_has_segments_and_is_found_by_its_model() -> None:
    for model, capability in SKU_REGISTRY.items():
        assert capability.is_rgbic and capability.segment_count > 1, model
        assert get_device_capability(model) is capability


def test_an_unknown_model_plays_one_colour() -> None:
    capability = get_device_capability("not-a-model")
    assert capability == DEFAULT_CAPABILITY
    assert (capability.is_rgbic, capability.segment_count, capability.razer) == (False, 0, False)


# Ruling 12, checked through each model's key wherever its entry sits in the table. The
# models aren't named here: the repo is public, and the table's own lines name them.
def test_the_upright_lamp_takes_razer_and_the_strip_does_not() -> None:
    flags = sorted(
        (entry.razer, entry.form, entry.segments_from_top)
        for entry in map(get_device_capability, SKU_REGISTRY)
    )
    assert flags == [(False, "strip", False), (True, "upright", False)]
