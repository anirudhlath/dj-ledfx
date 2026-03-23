import numpy as np
import pytest

from dj_ledfx.effects.strobe import Strobe
from dj_ledfx.types import BeatContext


def _ctx(beat_phase: float = 0.0, bar_phase: float = 0.0, bpm: float = 128.0) -> BeatContext:
    return BeatContext(beat_phase=beat_phase, bar_phase=bar_phase, bpm=bpm, dt=0.016)


def test_output_shape_and_dtype():
    effect = Strobe()
    result = effect.render(_ctx(), 10)
    assert result.shape == (10, 3)
    assert result.dtype == np.uint8


def test_on_at_beat_start():
    effect = Strobe(duty_cycle=0.15)
    result = effect.render(_ctx(beat_phase=0.0), 1)
    assert result.max() > 0, "Should be ON at beat start"


def test_off_after_duty_cycle():
    # Use low BPM (<=100) so energy=0 and subdivision=1 (no subdivision active)
    effect = Strobe(duty_cycle=0.15)
    result = effect.render(_ctx(beat_phase=0.5, bpm=90.0), 1)
    assert result.max() == 0, "Should be OFF well past duty cycle"


def test_duty_cycle_boundary():
    # Use low BPM (<=100) so energy=0 and subdivision=1 (no subdivision active)
    effect = Strobe(duty_cycle=0.5)
    on = effect.render(_ctx(beat_phase=0.1, bpm=90.0), 1)
    off = effect.render(_ctx(beat_phase=0.6, bpm=90.0), 1)
    assert on.max() > 0
    assert off.max() == 0


def test_subdivision_at_high_bpm():
    effect = Strobe(duty_cycle=0.15, max_subdivision=4)
    # At high BPM (160+), subdivision should be 4 (16th notes)
    # beat_phase=0.5 should be ON again (2nd subdivision of 4)
    result = effect.render(_ctx(beat_phase=0.5, bpm=160.0), 1)
    # At subdivision=4, phase 0.5 maps to sub_phase = (0.5*4)%1 = 0.0 → ON
    assert result.max() > 0


def test_parameters_schema():
    schema = Strobe.parameters()
    assert "palette" in schema
    assert "duty_cycle" in schema
    assert "max_subdivision" in schema


def test_get_set_params():
    effect = Strobe(duty_cycle=0.3)
    assert effect.get_params()["duty_cycle"] == 0.3
    effect.set_params(duty_cycle=0.1)
    assert effect.get_params()["duty_cycle"] == 0.1


def test_uniform_across_leds():
    effect = Strobe()
    result = effect.render(_ctx(beat_phase=0.0), 5)
    # All LEDs should be the same color
    for i in range(1, 5):
        np.testing.assert_array_equal(result[0], result[i])
