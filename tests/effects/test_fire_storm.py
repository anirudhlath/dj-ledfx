import numpy as np

from dj_ledfx.effects.fire_storm import FireStorm
from dj_ledfx.types import BeatContext


def _ctx(beat_phase: float = 0.0, bar_phase: float = 0.0, bpm: float = 128.0) -> BeatContext:
    return BeatContext(beat_phase=beat_phase, bar_phase=bar_phase, bpm=bpm, dt=0.016)


def test_output_shape_and_dtype():
    effect = FireStorm()
    result = effect.render(_ctx(), 20)
    assert result.shape == (20, 3)
    assert result.dtype == np.uint8


def test_per_led_variation():
    effect = FireStorm(smoothing=0.0)
    result = effect.render(_ctx(), 20)
    unique_rows = np.unique(result, axis=0)
    assert len(unique_rows) > 1, "Per-LED noise should produce variation"


def test_temporal_smoothing():
    effect = FireStorm(smoothing=0.9)
    frame1 = effect.render(_ctx(), 10)
    frame2 = effect.render(_ctx(), 10)
    # With high smoothing, frames should be similar (not identical due to noise)
    diff = np.abs(frame1.astype(int) - frame2.astype(int))
    assert diff.mean() < 100, "High smoothing should produce similar consecutive frames"


def test_no_smoothing_varies():
    effect = FireStorm(smoothing=0.0)
    frame1 = effect.render(_ctx(), 10)
    frame2 = effect.render(_ctx(), 10)
    assert not np.array_equal(frame1, frame2), "No smoothing should produce different frames"


def test_statefulness_across_renders():
    effect = FireStorm(smoothing=0.5)
    # First render initializes state
    effect.render(_ctx(), 10)
    # Second render should use previous state
    result = effect.render(_ctx(), 10)
    assert result.shape == (10, 3)


def test_led_count_change_resets_state():
    effect = FireStorm(smoothing=0.5)
    effect.render(_ctx(), 10)
    # Changing led_count should work without error
    result = effect.render(_ctx(), 20)
    assert result.shape == (20, 3)


def test_parameters_schema():
    schema = FireStorm.parameters()
    assert "palette" in schema
    assert "intensity" in schema
    assert "smoothing" in schema


def test_get_set_params():
    effect = FireStorm(intensity=0.5)
    assert effect.get_params()["intensity"] == 0.5
    effect.set_params(intensity=0.8)
    assert effect.get_params()["intensity"] == 0.8


def test_single_led():
    effect = FireStorm()
    result = effect.render(_ctx(), 1)
    assert result.shape == (1, 3)
