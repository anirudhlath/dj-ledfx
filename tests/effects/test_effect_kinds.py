from __future__ import annotations

from typing import Any

import numpy as np
import pytest
from conftest import render_ctx
from map_home import leds_at
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
    adapter = StripAdapter(_Ramp())
    adapter.set_params(mapping="order")
    colors = adapter.render(render_ctx(), leds)
    assert colors.shape == (5, 3)
    assert colors.dtype == np.float32
    assert np.allclose(colors[:, 0], np.linspace(0, 255, 5).astype(np.uint8) / 255.0)
    assert np.all(colors[:, 1:] == 0.0)


RAMP = np.linspace(0, 255, 4).astype(np.uint8) / 255.0  # the strip's 4 reds, in order


def test_strip_adapter_projects_each_led_onto_an_axis() -> None:
    leds = leds_at(
        [[3.0, 0.0, 0.0], [0.0, 0.0, 2.0], [2.0, 0.0, 1.0], [1.0, 0.0, 3.0]], ceiling=None
    )
    adapter = StripAdapter(_Ramp())  # linear along east by default
    assert np.allclose(adapter.render(render_ctx(), leds)[:, 0], RAMP[[3, 0, 2, 1]])
    adapter.set_params(axis="up")
    assert np.allclose(adapter.render(render_ctx(), leds)[:, 0], RAMP[[0, 2, 1, 3]])


def test_strip_adapter_projects_radially_from_an_anchor_or_the_middle() -> None:
    leds = leds_at(
        [[0.0, 2.0, 0.0], [0.0, 0.0, 0.0], [0.0, 3.0, 0.0], [0.0, 1.0, 0.0]],
        ceiling=None,
        anchors={"sofa": (0.0, 0.0, 0.0)},
    )
    adapter = StripAdapter(_Ramp())
    adapter.set_params(mapping="radial", centre="sofa")
    assert np.allclose(adapter.render(render_ctx(), leds)[:, 0], RAMP[[2, 0, 3, 1]])
    adapter.set_params(centre="")  # the middle of the zone: y = 1.5
    middle = adapter.render(render_ctx(), leds)[:, 0]
    assert middle[0] == middle[3] and middle[1] == middle[2] and middle[1] > middle[0]


# M2 review M11: the classics default to east, so a strip running north-south would
# otherwise show one colour.
@pytest.mark.parametrize(
    ("points", "settings"),
    [
        ([[1.0, 0.0, 1.0], [1.0, 1.0, 1.0], [1.0, 2.0, 1.0], [1.0, 3.0, 1.0]], {}),
        ([[1.02, 0.0, 1.0], [1.0, 1.0, 1.0], [1.03, 2.0, 1.0], [1.01, 3.0, 1.0]], {}),
        ([[2.0, 2.0, 1.0]] * 4, {"mapping": "radial"}),
        (
            [[2.0, 2.0, 1.0], [2.02, 2.0, 1.0], [2.0, 2.04, 1.0], [2.01, 2.0, 1.0]],
            {"mapping": "radial"},
        ),
    ],
    ids=["north-south", "north-south-jittered", "one-point", "within-5-cm-of-the-middle"],
)
def test_leds_spanning_under_5_cm_along_the_projection_play_in_led_order(
    points: list[list[float]], settings: dict[str, str]
) -> None:
    adapter = StripAdapter(_Ramp())
    adapter.set_params(**settings)
    assert np.allclose(adapter.render(render_ctx(), leds_at(points, ceiling=None))[:, 0], RAMP)


def test_strip_adapter_forwards_parameters() -> None:
    inner = _Ramp()
    adapter = StripAdapter(inner)
    adapter.set_params(level=0.5, mapping="radial")
    assert inner.level == 0.5
    assert adapter.get_params() == {"level": 0.5}  # the strip effect's own settings
    with pytest.raises(ValueError, match="above max"):
        adapter.set_params(level=2.0, mapping="order")
    with pytest.raises(ValueError, match="not in"):
        adapter.set_params(mapping="spiral")
    leds = leds_at(
        [[3.0, 0.0, 0.0], [0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]], ceiling=None
    )
    # A refused change changes nothing: still radial from the middle (x = 1.5), so the
    # two outer LEDs match and so do the two inner ones; in LED order all four differ.
    radial = adapter.render(render_ctx(), leds)[:, 0]
    assert radial[0] == radial[1] and radial[2] == radial[3] and radial[0] > radial[2]


def test_fire_storm_repeats_after_reseed() -> None:
    ctx = BeatContext(beat_phase=0.5, bar_phase=0.25, bpm=128.0, dt=1 / 60)
    a, b = FireStorm(), FireStorm()
    a.reseed(7)
    b.reseed(7)
    for _ in range(3):
        assert np.array_equal(a.render(ctx, 12), b.render(ctx, 12))


def test_start_params_add_brightness_to_the_settings() -> None:
    assert _Probe(period=6.0).start_params(0.4) == {"period": 6.0, "brightness": 0.4}
