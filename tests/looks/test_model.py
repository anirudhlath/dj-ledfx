from __future__ import annotations

from typing import Any, ClassVar

import numpy as np
import pytest

from dj_ledfx.effects.base import Effect
from dj_ledfx.effects.context import RenderContext
from dj_ledfx.effects.field import FieldEffect
from dj_ledfx.effects.firmware_lifx import LifxFlame
from dj_ledfx.effects.ledset import LedSet
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.effects.strip_adapter import StripAdapter
from dj_ledfx.looks.model import (
    LIGHTS_SETTING,
    Layer,
    Look,
    LookError,
    LookModifiers,
    Transition,
    firmware_layers,
    look_from_dict,
    look_to_dict,
    make_effect,
    setting_schema,
    validate_look,
    visible_field_layer,
    visible_field_layers,
)
from dj_ledfx.looks.selectors import Selector
from dj_ledfx.types import FloatRGB


def _layer(**overrides: Any) -> dict[str, Any]:
    layer: dict[str, Any] = {
        "id": "l1",
        "name": "Breathe",
        "type": "field",
        "kind": "breathe",
        "visible": True,
        "blend": "normal",
        "opacity": 1.0,
        "settings": {"beats_per_cycle": {"value": 2.0}},
    }
    layer.update(overrides)
    return layer


def _look(**overrides: Any) -> dict[str, Any]:
    look: dict[str, Any] = {
        "id": "mine-1",
        "name": "My breathe",
        "category": "tempo",
        "builtIn": False,
        "derivedFrom": "classic-breathe",
        "description": "Slow",
        "thumbnail": "classic-breathe",
        "scope": "any-zone",
        "needs": [],
        "uses": ["tempo"],
        "starred": False,
        "layers": [_layer()],
        "modifiers": {
            "trailsS": None,
            "downbeatFlash": False,
            "brightnessCap": None,
            "evening": False,
        },
        "transition": {"kind": "fade", "durationS": 2.0},
    }
    look.update(overrides)
    return look


def test_contract_round_trip() -> None:
    look = look_from_dict(_look())
    assert look.id == "mine-1"
    assert look.derived_from == "classic-breathe"
    assert look.uses == ("tempo",)
    assert look.layers[0].settings == {"beats_per_cycle": 2.0}
    assert look.transition == Transition(kind="fade", duration_s=2.0)

    out = look_to_dict(look, starred=True)
    assert out["builtIn"] is False
    assert out["derivedFrom"] == "classic-breathe"
    assert out["starred"] is True
    assert out["layers"][0]["settings"] == {"beats_per_cycle": {"value": 2.0}}
    assert out["modifiers"] == {
        "trailsS": None,
        "downbeatFlash": False,
        "brightnessCap": None,
        "evening": False,
    }
    assert out["transition"] == {"kind": "fade", "durationS": 2.0}
    assert look_from_dict(out) == look


def test_layer_schema_follows_the_effect_parameters() -> None:
    schema = {
        entry["key"]: entry
        for entry in look_to_dict(look_from_dict(_look()))["layers"][0]["schema"]
    }
    assert schema["palette"]["type"] == "palette"
    assert schema["beats_per_cycle"] == {
        "key": "beats_per_cycle",
        "label": "Beats per Cycle",
        "bindable": False,
        "type": "number",
        "min": 1.0,
        "max": 4.0,
        "step": 0.5,
    }


def test_setting_schema_types() -> None:
    schema = {entry["key"]: entry for entry in setting_schema("lifx_waveform")}
    assert schema["colour"]["type"] == "colour"
    assert schema["waveform"] == {
        "key": "waveform",
        "label": "Shape",
        "bindable": False,
        "type": "choice",
        "options": ["sine", "triangle", "saw", "half_sine", "pulse"],
    }
    assert {entry["key"]: entry for entry in setting_schema("lifx_move")}["reverse"][
        "type"
    ] == "boolean"
    assert setting_schema("no_such_effect") == []


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"name": ""}, "name"),
        ({"category": "party"}, "category"),
        ({"scope": "whole-home"}, "M6"),
        ({"needs": ["weather"]}, "input"),
        ({"layers": [_layer(type="particles", kind="fireflies")]}, "M5"),
        ({"layers": [_layer(settings={"beats_per_cycle": {"value": 2.0, "binding": {}}})]}, "M7"),
        ({"layers": [_layer(mask={"kind": "height"})]}, "M4"),
        ({"layers": [_layer(settings={"beats_per_cycle": 2.0})]}, "value"),
        (
            {
                "modifiers": {
                    "trailsS": 0.5,
                    "downbeatFlash": False,
                    "brightnessCap": None,
                    "evening": False,
                }
            },
            "M4",
        ),
        ({"transition": {"kind": "melt", "durationS": 1.0}}, "transition"),
    ],
)
def test_looks_m1_cannot_run_are_refused_with_the_reason(
    change: dict[str, Any], reason: str
) -> None:
    with pytest.raises(LookError, match=reason):
        validate_look(look_from_dict(_look(**change)))


@pytest.mark.parametrize(
    ("layers", "reason"),
    [
        ([], "at least one layer"),
        ([_layer(kind="no_such_effect")], "unknown effect"),
        ([_layer(type="firmware", kind="breathe")], "firmware"),
        ([_layer(kind="lifx_flame", settings={})], "field"),
        ([_layer(settings={"beats_per_cycle": {"value": 99.0}})], "above max"),
        (
            [_layer(type="firmware", kind="lifx_flame", settings={"lights": {"value": "type:"}})],
            "one word",
        ),
        ([_layer(settings={"lights": {"value": ["lamp"]}})], "M4"),
    ],
)
def test_layer_problems_are_refused(layers: list[dict[str, Any]], reason: str) -> None:
    with pytest.raises(LookError, match=reason):
        validate_look(look_from_dict(_look(layers=layers)))


def test_hidden_field_layers_and_firmware_layers_are_fine() -> None:
    look = look_from_dict(
        _look(
            layers=[
                _layer(id="a", visible=False),
                _layer(id="b"),
                _layer(id="c", type="firmware", kind="lifx_flame", settings={}),
                _layer(id="d", type="firmware", kind="openrgb_mode", settings={}),
            ]
        )
    )
    validate_look(look)
    field_layer = visible_field_layer(look)
    assert field_layer is not None and field_layer.id == "b"
    assert [layer.id for layer in firmware_layers(look)] == ["c", "d"]


# B12: a hidden firmware layer is left out, as a hidden field layer is.
def test_hidden_firmware_layers_are_left_out() -> None:
    look = look_from_dict(
        _look(
            layers=[
                _layer(id="c", type="firmware", kind="lifx_flame", settings={}, visible=False),
                _layer(id="d", type="firmware", kind="openrgb_mode", settings={}),
            ]
        )
    )
    assert [layer.id for layer in firmware_layers(look)] == ["d"]


def test_a_firmware_only_look_has_no_field_layer() -> None:
    look = look_from_dict(_look(layers=[_layer(type="firmware", kind="lifx_flame", settings={})]))
    validate_look(look)
    assert visible_field_layer(look) is None


def test_make_effect_wraps_strip_effects_and_applies_settings() -> None:
    effect = make_effect(
        Layer(
            id="l", name="Breathe", type="field", kind="breathe", settings={"beats_per_cycle": 2.0}
        )
    )
    assert isinstance(effect, StripAdapter)
    assert effect.get_params()["beats_per_cycle"] == 2.0
    flame = make_effect(
        Layer(id="f", name="Flame", type="firmware", kind="lifx_flame", settings={"period": 3.0})
    )
    assert isinstance(flame, LifxFlame)
    assert flame.get_params() == {"period": 3.0}


def test_defaults() -> None:
    look = Look(id="x", name="X", category="ambient")
    assert look.modifiers == LookModifiers()
    assert look.transition == Transition()
    assert look.scope == "any-zone"
    assert not look.built_in


class _EveryType(FieldEffect, register=False):
    PARAMS: ClassVar[dict[str, EffectParam]] = {
        "centre": EffectParam(type="anchor", default="", label="Centre"),
        "at": EffectParam(type="point", default=(0.0, 0.0, 0.0)),
        "zone": EffectParam(type="zone", default=""),
        "lights": EffectParam(type="device_set", default=[]),
        "band": EffectParam(type="range", default=(0.0, 1.0), min=0.0, max=3.0),
        "level": EffectParam(type="float", default=0.5, min=0.0, max=1.0, bindable=True),
    }

    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return cls.PARAMS

    def __init__(
        self,
        centre: str = "",
        at: Any = None,
        zone: str = "",
        lights: Any = None,
        band: Any = None,
        level: float = 0.5,
    ) -> None:
        pass

    def render(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        return np.zeros((leds.count, 3), dtype=np.float32)


def test_the_new_setting_types_reach_the_schema_in_the_contracts_names() -> None:
    Effect._registry["every_type"] = _EveryType  # conftest drops it after the test
    schema = {entry["key"]: entry for entry in setting_schema("every_type")}
    assert {key: entry["type"] for key, entry in schema.items()} == {
        "centre": "anchor",
        "at": "point",
        "zone": "zone",
        "lights": "lights",
        "band": "range",
        "level": "number",
    }
    assert schema["centre"] == {
        "key": "centre",
        "label": "Centre",
        "bindable": False,
        "type": "anchor",
    }
    assert (schema["band"]["min"], schema["band"]["max"]) == (0.0, 3.0)
    assert schema["level"]["bindable"] is True


def test_field_layers_stack_and_firmware_layers_pick_their_lights() -> None:
    look = look_from_dict(
        _look(
            layers=[
                _layer(id="a"),
                _layer(id="b", blend="screen", opacity=0.5),
                _layer(
                    id="c",
                    type="firmware",
                    kind="lifx_flame",
                    settings={LIGHTS_SETTING: {"value": "type:candle"}, "period": {"value": 3.0}},
                ),
            ]
        )
    )
    validate_look(look)
    assert [layer.id for layer in visible_field_layers(look)] == ["a", "b"]
    flame = look.layers[2]
    assert flame.lights == (Selector("type", "candle"),)
    assert flame.settings == {"period": 3.0}  # the effect's own settings
    assert look.layers[0].lights is None
    assert make_effect(flame).get_params()["period"] == 3.0
    written = look_to_dict(look)["layers"][2]["settings"]
    assert written == {"period": {"value": 3.0}, "lights": {"value": ["type:candle"]}}


def test_firmware_layers_offer_a_lights_setting() -> None:
    assert setting_schema("lifx_flame")[-1] == {
        "key": "lights",
        "label": "Lights",
        "bindable": False,
        "type": "lights",
    }
    assert "lights" not in {entry["key"] for entry in setting_schema("breathe")}


def test_strip_effects_offer_the_projection_settings() -> None:
    schema = {entry["key"]: entry for entry in setting_schema("breathe")}
    assert list(schema)[-3:] == ["mapping", "axis", "centre"]
    assert schema["mapping"]["options"] == ["linear", "radial", "order"]
    assert schema["centre"]["type"] == "anchor"
    assert "mapping" not in {entry["key"] for entry in setting_schema("lifx_flame")}


def test_a_strip_layer_takes_its_projection_from_its_settings() -> None:
    effect = make_effect(
        Layer(
            id="l",
            name="Breathe",
            type="field",
            kind="breathe",
            settings={"beats_per_cycle": 2.0, "mapping": "radial", "centre": "sofa"},
        )
    )
    assert isinstance(effect, StripAdapter) and effect.get_params()["beats_per_cycle"] == 2.0
