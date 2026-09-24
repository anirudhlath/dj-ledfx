from __future__ import annotations

from typing import Any

import numpy as np
import pytest
from conftest import render_ctx
from numpy.typing import NDArray

from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.effects.base import Effect, StripEffect
from dj_ledfx.effects.context import RenderContext
from dj_ledfx.effects.field import FieldEffect
from dj_ledfx.effects.fire_storm import FireStorm
from dj_ledfx.effects.firmware import FirmwareEffect, Params
from dj_ledfx.effects.ledset import LedSet, LedSource, build_ledset
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.effects.registry import (
    get_effect_class,
    get_effect_schemas,
    get_strip_effect_classes,
)
from dj_ledfx.effects.strip_adapter import StripAdapter
from dj_ledfx.types import BeatContext, FloatRGB

CLASSIC = {"beat_pulse", "breathe", "color_chase", "fire_storm", "rainbow_wave", "strobe"}


class _Ramp(StripEffect, register=False):
    """Red ramps 0..255 along the strip."""

    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {"level": EffectParam(type="float", default=1.0, min=0.0, max=1.0)}

    def __init__(self, level: float = 1.0) -> None:
        self.level = level

    def get_params(self) -> dict[str, Any]:
        return {"level": self.level}

    def _apply_params(self, **kwargs: Any) -> None:
        self.level = float(kwargs.get("level", self.level))

    def render(self, ctx: BeatContext, led_count: int) -> NDArray[np.uint8]:
        out = np.zeros((led_count, 3), dtype=np.uint8)
        out[:, 0] = np.linspace(0, 255 * self.level, led_count).astype(np.uint8)
        return out


class _Probe(FirmwareEffect, register=False):
    display_name = "Probe"

    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {"period": EffectParam(type="float", default=4.0, min=1.0, max=10.0)}

    def __init__(self, period: float = 4.0) -> None:
        self.period = period

    def get_params(self) -> dict[str, Any]:
        return {"period": self.period}

    def supports(self, caps: DeviceCapabilities) -> bool:
        return caps.matrix

    async def start(self, adapter: DeviceAdapter, params: Params) -> None:
        return None

    async def stop(self, adapter: DeviceAdapter) -> None:
        return None

    async def is_running(self, adapter: DeviceAdapter) -> bool | None:
        return None

    def emulate(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        return np.zeros((leds.count, 3), dtype=np.float32)


def test_classic_effects_are_registered_strip_effects() -> None:
    strips = get_strip_effect_classes()
    assert CLASSIC <= set(strips)
    for name in CLASSIC:
        assert issubclass(strips[name], StripEffect)


def test_abstract_kinds_and_opt_outs_are_not_registered() -> None:
    for name in ("strip_effect", "field_effect", "firmware_effect", "strip_adapter", "_ramp"):
        assert name not in Effect._registry


def test_schemas_cover_strip_effects_only() -> None:
    class ProbeField(FieldEffect):
        def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
            return np.zeros((leds.count, 3), dtype=np.float32)

    assert get_effect_class("probe_field") is ProbeField
    assert "probe_field" not in get_effect_schemas()
    assert CLASSIC <= set(get_effect_schemas())


def test_unknown_kinds_raise_key_error() -> None:
    with pytest.raises(KeyError):
        get_effect_class("no_such_effect")


def test_strip_adapter_plays_the_strip_along_the_leds_in_order() -> None:
    leds = build_ledset([LedSource("a", 3), LedSource("b", 2)])
    colors = StripAdapter(_Ramp()).render(render_ctx(), leds)
    assert colors.shape == (5, 3)
    assert colors.dtype == np.float32
    assert np.allclose(colors[:, 0], np.linspace(0, 255, 5).astype(np.uint8) / 255.0)
    assert np.all(colors[:, 1:] == 0.0)


def test_strip_adapter_forwards_parameters() -> None:
    inner = _Ramp()
    adapter = StripAdapter(inner)
    adapter.set_params(level=0.5)
    assert inner.level == 0.5
    assert adapter.get_params() == {"level": 0.5}
    with pytest.raises(ValueError):
        adapter.set_params(level=2.0)


def test_fire_storm_repeats_after_reseed() -> None:
    ctx = BeatContext(beat_phase=0.5, bar_phase=0.25, bpm=128.0, dt=1 / 60)
    a, b = FireStorm(), FireStorm()
    a.reseed(7)
    b.reseed(7)
    for _ in range(3):
        assert np.array_equal(a.render(ctx, 12), b.render(ctx, 12))


def test_start_params_add_brightness_to_the_settings() -> None:
    assert _Probe(period=6.0).start_params(0.4) == {"period": 6.0, "brightness": 0.4}
