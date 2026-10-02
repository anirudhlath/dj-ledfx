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


def test_the_upright_lamp_takes_razer_and_the_strip_does_not() -> None:  # ruling 12
    upright, strip = SKU_REGISTRY.values()
    assert (upright.razer, upright.form, upright.segments_from_top) == (True, "upright", False)
    assert (strip.razer, strip.form) == (False, "strip")
