import numpy as np
import pytest

from dj_ledfx.effects.rainbow_wave import RainbowWave
from dj_ledfx.types import BeatContext


def _ctx(beat_phase: float = 0.0, bar_phase: float = 0.0, bpm: float = 128.0) -> BeatContext:
    return BeatContext(beat_phase=beat_phase, bar_phase=bar_phase, bpm=bpm, dt=0.016)


def test_output_shape_and_dtype():
    effect = RainbowWave()
    result = effect.render(_ctx(), 20)
    assert result.shape == (20, 3)
    assert result.dtype == np.uint8


def test_spatial_hue_distribution():
    effect = RainbowWave(wave_count=1.0, beat_pulse=0.0)
    result = effect.render(_ctx(bar_phase=0.0), 60)
    # Should have a variety of colors across the strip
    unique_rows = np.unique(result, axis=0)
    assert len(unique_rows) > 5, "Rainbow should produce many distinct colors"


def test_beat_pulse_modulation():
    effect = RainbowWave(beat_pulse=1.0)
    on_beat = effect.render(_ctx(beat_phase=0.0), 10)
    mid_beat = effect.render(_ctx(beat_phase=0.5), 10)
    # On beat is brightest (value=1.0); brightness drops as beat progresses
    assert on_beat.mean() >= mid_beat.mean()


def test_no_beat_pulse():
    effect = RainbowWave(beat_pulse=0.0)
    on_beat = effect.render(_ctx(beat_phase=0.0), 10)
    mid_beat = effect.render(_ctx(beat_phase=0.5), 10)
    # With no beat pulse, brightness should be the same
    np.testing.assert_array_equal(on_beat, mid_beat)


def test_rotates_with_bar_phase():
    effect = RainbowWave(beat_pulse=0.0)
    frame1 = effect.render(_ctx(bar_phase=0.0), 20)
    frame2 = effect.render(_ctx(bar_phase=0.5), 20)
    assert not np.array_equal(frame1, frame2)


def test_parameters_schema():
    schema = RainbowWave.parameters()
    assert "saturation" in schema
    assert "wave_count" in schema
    assert "beat_pulse" in schema


def test_single_led():
    effect = RainbowWave()
    result = effect.render(_ctx(), 1)
    assert result.shape == (1, 3)
    assert result.max() > 0
