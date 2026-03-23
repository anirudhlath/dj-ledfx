import numpy as np
import pytest

from dj_ledfx.effects.base import Effect
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.types import BeatContext


class DummyEffect(Effect):
    @classmethod
    def parameters(cls):
        return {"speed": EffectParam(type="float", default=1.0, min=0.1, max=10.0)}

    def __init__(self, speed: float = 1.0):
        self._speed = speed

    def _apply_params(self, **kwargs):
        if "speed" in kwargs:
            self._speed = kwargs["speed"]

    def get_params(self):
        return {"speed": self._speed}

    def render(self, ctx: BeatContext, led_count: int):
        import numpy as np

        return np.zeros((led_count, 3), dtype=np.uint8)


def test_effect_auto_registers():
    assert "dummy_effect" in Effect._registry


def test_effect_parameters_schema():
    schema = DummyEffect.parameters()
    assert "speed" in schema
    assert schema["speed"].type == "float"


def test_set_params_validates_unknown_key():
    e = DummyEffect()
    with pytest.raises(ValueError, match="Unknown parameter"):
        e.set_params(nonexistent=5)


def test_set_params_validates_range():
    e = DummyEffect()
    with pytest.raises(ValueError, match="below min"):
        e.set_params(speed=0.01)
    with pytest.raises(ValueError, match="above max"):
        e.set_params(speed=100.0)


def test_set_params_applies():
    e = DummyEffect()
    e.set_params(speed=5.0)
    assert e.get_params()["speed"] == 5.0


def test_constructor_validation():
    with pytest.raises(TypeError, match="does not accept"):

        class _BadEffect(Effect):
            @classmethod
            def parameters(cls):
                return {"foo": EffectParam(type="float", default=1.0)}

            def __init__(self):
                pass

            def render(self, ctx: BeatContext, led_count: int):
                import numpy as np

                return np.zeros((led_count, 3), dtype=np.uint8)


from dj_ledfx.effects.registry import (  # noqa: E402
    create_effect,
    get_effect_classes,
    get_effect_schemas,
)


def test_get_effect_classes_includes_beat_pulse():
    classes = get_effect_classes()
    assert "beat_pulse" in classes


def test_get_effect_schemas():
    schemas = get_effect_schemas()
    assert "beat_pulse" in schemas
    assert "gamma" in schemas["beat_pulse"]


def test_create_effect():
    effect = create_effect("beat_pulse", gamma=3.0)
    assert effect.get_params()["gamma"] == 3.0


def test_create_effect_unknown():
    with pytest.raises(KeyError):
        create_effect("nonexistent_effect")


def test_all_registered_effects_render_with_defaults():
    """Smoke test: instantiate every registered effect with defaults, render one frame."""
    ctx = BeatContext(beat_phase=0.5, bar_phase=0.25, bpm=128.0, dt=0.016)
    for name, cls in get_effect_classes().items():
        if name == "dummy_effect":
            continue
        effect = cls()
        result = effect.render(ctx, 10)
        assert result.shape == (10, 3), f"{name} returned wrong shape"
        assert result.dtype == np.uint8, f"{name} returned wrong dtype"


def test_all_registered_effects_render_with_zero_bpm():
    """Edge case: bpm=0 should not crash any effect."""
    ctx = BeatContext(beat_phase=0.0, bar_phase=0.0, bpm=0.0, dt=0.016)
    for name, cls in get_effect_classes().items():
        if name == "dummy_effect":
            continue
        effect = cls()
        result = effect.render(ctx, 5)
        assert result.shape == (5, 3), f"{name} crashed with bpm=0"


def test_all_registered_effects_render_with_zero_leds():
    """Edge case: led_count=0 should return empty array, not crash."""
    ctx = BeatContext(beat_phase=0.0, bar_phase=0.0, bpm=128.0, dt=0.016)
    for name, cls in get_effect_classes().items():
        if name == "dummy_effect":
            continue
        effect = cls()
        result = effect.render(ctx, 0)
        assert result.shape == (0, 3), f"{name} crashed with led_count=0"
