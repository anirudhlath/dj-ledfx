import numpy as np
import pytest

from dj_ledfx.effects.color_chase import ColorChase
from dj_ledfx.types import BeatContext


def _ctx(beat_phase: float = 0.0, bar_phase: float = 0.0, bpm: float = 128.0) -> BeatContext:
    return BeatContext(beat_phase=beat_phase, bar_phase=bar_phase, bpm=bpm, dt=0.016)


def test_output_shape_and_dtype():
    effect = ColorChase()
    result = effect.render(_ctx(), 20)
    assert result.shape == (20, 3)
    assert result.dtype == np.uint8


def test_spatial_gradient():
    effect = ColorChase()
    result = effect.render(_ctx(), 20)
    # Not all LEDs should be the same color (spatial variation)
    assert not np.all(result == result[0])


def test_single_led_degradation():
    effect = ColorChase()
    result = effect.render(_ctx(), 1)
    assert result.shape == (1, 3)
    assert result.max() > 0


def test_scrolls_with_beat_phase():
    effect = ColorChase()
    frame1 = effect.render(_ctx(beat_phase=0.0), 20)
    frame2 = effect.render(_ctx(beat_phase=0.5), 20)
    assert not np.array_equal(frame1, frame2), "Should scroll with beat phase"


def test_direction_reverse():
    effect_fwd = ColorChase(direction="forward")
    effect_rev = ColorChase(direction="reverse")
    fwd = effect_fwd.render(_ctx(beat_phase=0.25), 20)
    rev = effect_rev.render(_ctx(beat_phase=0.25), 20)
    assert not np.array_equal(fwd, rev)


def test_parameters_schema():
    schema = ColorChase.parameters()
    assert "palette" in schema
    assert "band_count" in schema
    assert "direction" in schema
    assert schema["direction"].type == "choice"


def test_get_set_params():
    effect = ColorChase(band_count=3.0)
    assert effect.get_params()["band_count"] == 3.0
    effect.set_params(band_count=5.0)
    assert effect.get_params()["band_count"] == 5.0
