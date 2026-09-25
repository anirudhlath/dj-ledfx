from typing import Any

import pytest

from dj_ledfx.effects.params import EffectParam, check_setting


def test_effect_param_float():
    p = EffectParam(type="float", default=2.0, min=0.5, max=5.0, step=0.1, label="Gamma")
    assert p.type == "float"
    assert p.default == 2.0
    assert p.min == 0.5


def test_effect_param_frozen():
    p = EffectParam(type="bool", default=True)
    with pytest.raises(AttributeError):
        p.type = "int"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("param", "value"),
    [
        (EffectParam(type="anchor", default=""), "sofa"),
        (EffectParam(type="zone", default=""), "living"),
        (EffectParam(type="point", default=(0.0, 0.0, 0.0)), [1.0, 2.0, 0.5]),
        (EffectParam(type="range", default=(0.0, 1.0), min=0.0, max=3.0), [0.5, 2.0]),
        (EffectParam(type="device_set", default=[]), ["lamp-1", "type:candle"]),
        (EffectParam(type="device_set", default=""), "type:candle"),
        (EffectParam(type="float", default=0.5, min=0.0, max=1.0), 1),
    ],
)
def test_settings_of_each_type_are_accepted(param: EffectParam, value: Any) -> None:
    check_setting("key", param, value)


@pytest.mark.parametrize(
    ("param", "value", "reason"),
    [
        (EffectParam(type="anchor", default=""), 3, "anchor id"),
        (EffectParam(type="point", default=(0.0, 0.0, 0.0)), [1.0, 2.0], "3 numbers"),
        (
            EffectParam(type="point", default=(0.0, 0.0, 0.0)),
            [1.0, float("inf"), 0.0],
            "3 numbers",
        ),
        (EffectParam(type="range", default=(0.0, 1.0)), [2.0, 1.0], "low first"),
        (EffectParam(type="range", default=(0.0, 1.0), min=0.0, max=3.0), [0.5, 4.0], "above max"),
        (EffectParam(type="device_set", default=[]), [1, 2], "selector"),
        (EffectParam(type="float", default=0.5, min=0.0, max=1.0), True, "a number"),
        (EffectParam(type="float", default=0.5, min=0.0, max=1.0), 2.0, "above max"),
        (EffectParam(type="choice", default="a", choices=["a"]), "b", "not in"),
    ],
)
def test_bad_settings_are_refused_with_the_reason(
    param: EffectParam, value: Any, reason: str
) -> None:
    with pytest.raises(ValueError, match=reason):
        check_setting("key", param, value)


def test_a_setting_is_not_bindable_unless_it_says_so() -> None:
    assert EffectParam(type="float", default=0.5).bindable is False
    assert EffectParam(type="float", default=0.5, bindable=True).bindable is True
