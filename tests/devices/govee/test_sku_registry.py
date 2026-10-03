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


# Ruling 12 and what the lamps showed in the plan's Task 8 (2026-10-02), checked through each
# model's key wherever its entry sits in the table. The models aren't named here: the repo
# is public, and the table's own lines name them. The upright lamps show 14 segments, the
# first at the bottom, and two of three stayed dark for frames of 15; the strip takes razer
# frames of 15.
def test_each_kind_plays_razer_with_the_segments_its_lamps_showed() -> None:
    kinds = sorted(
        (entry.form, entry.razer, entry.segment_count, entry.segments_from_top)
        for entry in map(get_device_capability, SKU_REGISTRY)
    )
    assert kinds == [("strip", True, 15, False), ("upright", True, 14, False)]
