import pytest
from dj_ledfx.effects.params import EffectParam


def test_effect_param_float():
    p = EffectParam(type="float", default=2.0, min=0.5, max=5.0, step=0.1, label="Gamma")
    assert p.type == "float"
    assert p.default == 2.0
    assert p.min == 0.5


def test_effect_param_frozen():
    p = EffectParam(type="bool", default=True)
    with pytest.raises(AttributeError):
        p.type = "int"  # type: ignore[misc]
