import numpy as np
from conftest import beat_ctx

from dj_ledfx.effects.breathe import Breathe

RED, GREEN = "#ff0000", "#00ff00"


def _level(breathe: Breathe, beats: float, bpm: float = 120.0) -> int:
    return int(breathe.render(beat_ctx(beats, bpm=bpm), 1).max())


def test_output_shape_and_dtype():
    effect = Breathe()
    result = effect.render(beat_ctx(0.0), 10)
    assert result.shape == (10, 3)
    assert result.dtype == np.uint8


def test_brightness_never_below_min():
    effect = Breathe(min_brightness=0.1)
    for beats in np.linspace(0.0, 3.99, 20):
        # At min_brightness=0.1, no channel should be fully zero if palette isn't black
        assert effect.render(beat_ctx(float(beats)), 1).max() > 0


def test_brightness_varies_across_bar():
    effect = Breathe()
    values = [_level(effect, float(beats)) for beats in np.linspace(0.0, 3.99, 10)]
    assert max(values) > min(values), "Brightness should vary across bar"


def test_parameters_schema():
    schema = Breathe.parameters()
    assert "palette" in schema
    assert "min_brightness" in schema
    cycle = schema["beats_per_cycle"]
    assert (cycle.default, cycle.min, cycle.max) == (4.0, 1.0, 8.0)


def test_get_set_params():
    effect = Breathe(beats_per_cycle=2.0)
    assert effect.get_params()["beats_per_cycle"] == 2.0
    effect.set_params(beats_per_cycle=3.0)
    assert effect.get_params()["beats_per_cycle"] == 3.0


def test_single_led():
    effect = Breathe()
    result = effect.render(beat_ctx(0.0), 1)
    assert result.shape == (1, 3)


def test_a_breath_lasts_beats_per_cycle_beats_and_may_span_bars() -> None:
    for cycle in (3.0, 8.0):
        breathe = Breathe(palette=["#ffffff"], beats_per_cycle=cycle, min_brightness=0.0)
        beats = [n * cycle / 2 for n in range(5)]  # dimmest, brightest, dimmest...
        assert [_level(breathe, b) for b in beats] == [0, 255, 0, 255, 0]


def test_a_breath_glides_on_over_bar_lines() -> None:
    breathe = Breathe(beats_per_cycle=3.0)  # three beats: not a bar
    for bar_line in (4.0, 8.0):
        before = breathe.render(beat_ctx(bar_line - 1e-6), 1).astype(int)
        on = breathe.render(beat_ctx(bar_line), 1).astype(int)
        assert np.abs(on - before).max() <= 1


def test_each_breath_takes_the_next_colour_at_its_dimmest() -> None:
    breathe = Breathe(palette=[RED, GREEN], beats_per_cycle=2.0, min_brightness=0.0)
    assert breathe.render(beat_ctx(1.0), 1)[0].tolist() == [255, 0, 0]  # the first breath
    assert breathe.render(beat_ctx(3.0), 1)[0].tolist() == [0, 255, 0]  # the second
    assert _level(breathe, 2.0 - 1e-6) <= 1 and _level(breathe, 2.0) == 0  # changed in the dark


def test_the_tempo_sets_when_the_breaths_come_and_nothing_else() -> None:
    breathe = Breathe()
    assert _level(breathe, 2.5, bpm=90.0) == _level(breathe, 2.5, bpm=150.0)
