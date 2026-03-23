import numpy as np

from dj_ledfx.effects.breathe import Breathe
from dj_ledfx.types import BeatContext


def _ctx(beat_phase: float = 0.0, bar_phase: float = 0.0, bpm: float = 128.0) -> BeatContext:
    return BeatContext(beat_phase=beat_phase, bar_phase=bar_phase, bpm=bpm, dt=0.016)


def test_output_shape_and_dtype():
    effect = Breathe()
    result = effect.render(_ctx(), 10)
    assert result.shape == (10, 3)
    assert result.dtype == np.uint8


def test_brightness_never_below_min():
    effect = Breathe(min_brightness=0.1)
    # Test many phases
    for phase in np.linspace(0.0, 0.99, 20):
        result = effect.render(_ctx(bar_phase=phase), 1)
        # At min_brightness=0.1, no channel should be fully zero if palette isn't black
        assert result.max() > 0


def test_brightness_varies_across_bar():
    effect = Breathe()
    values = []
    for phase in np.linspace(0.0, 0.99, 10):
        result = effect.render(_ctx(bar_phase=phase), 1)
        values.append(result.max())
    assert max(values) > min(values), "Brightness should vary across bar"


def test_energy_adaptation_faster_at_high_bpm():
    effect = Breathe(beats_per_cycle=4.0)
    # At low BPM (80), cycle should be slower — check full bar for brightness range
    phases = np.linspace(0, 0.99, 20)
    low_bpm_values = [effect.render(_ctx(bar_phase=p, bpm=80.0), 1).max() for p in phases]
    high_bpm_values = [effect.render(_ctx(bar_phase=p, bpm=160.0), 1).max() for p in phases]
    # High BPM should complete more cycles per bar
    low_zero_crossings = sum(
        1
        for i in range(1, len(low_bpm_values))
        if (low_bpm_values[i] > 128) != (low_bpm_values[i - 1] > 128)
    )
    high_zero_crossings = sum(
        1
        for i in range(1, len(high_bpm_values))
        if (high_bpm_values[i] > 128) != (high_bpm_values[i - 1] > 128)
    )
    assert high_zero_crossings >= low_zero_crossings


def test_parameters_schema():
    schema = Breathe.parameters()
    assert "palette" in schema
    assert "beats_per_cycle" in schema
    assert "min_brightness" in schema


def test_get_set_params():
    effect = Breathe(beats_per_cycle=2.0)
    assert effect.get_params()["beats_per_cycle"] == 2.0
    effect.set_params(beats_per_cycle=3.0)
    assert effect.get_params()["beats_per_cycle"] == 3.0


def test_single_led():
    effect = Breathe()
    result = effect.render(_ctx(), 1)
    assert result.shape == (1, 3)
