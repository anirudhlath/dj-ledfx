import numpy as np
from conftest import beat_ctx

from dj_ledfx.effects.rainbow_wave import RainbowWave


def test_output_shape_and_dtype():
    effect = RainbowWave()
    result = effect.render(beat_ctx(0.0), 20)
    assert result.shape == (20, 3)
    assert result.dtype == np.uint8


def test_spatial_hue_distribution():
    effect = RainbowWave(wave_count=1.0, beat_pulse=0.0)
    result = effect.render(beat_ctx(0.0), 60)
    # Should have a variety of colors across the strip
    unique_rows = np.unique(result, axis=0)
    assert len(unique_rows) > 5, "Rainbow should produce many distinct colors"


def test_beat_pulse_modulation():
    effect = RainbowWave(beat_pulse=1.0)
    # On the beat every LED is at its brightest (value 1.0), and it dims as the beat goes on
    on_beat = effect.render(beat_ctx(0.0), 10).max(axis=1)
    mid_beat = effect.render(beat_ctx(0.5), 10).max(axis=1)
    assert (on_beat == 255).all() and (mid_beat < on_beat).all()


def test_no_beat_pulse():
    effect = RainbowWave(beat_pulse=0.0)
    # With no beat pulse, every LED stays at its brightest through the beat
    for beats in (0.0, 0.5, 0.9):
        assert (effect.render(beat_ctx(beats), 10).max(axis=1) == 255).all()


def test_parameters_schema():
    schema = RainbowWave.parameters()
    assert "saturation" in schema
    assert "wave_count" in schema
    assert "beat_pulse" in schema


def test_single_led():
    effect = RainbowWave()
    result = effect.render(beat_ctx(0.0), 1)
    assert result.shape == (1, 3)
    assert result.max() > 0


def test_the_rainbow_turns_once_a_bar() -> None:
    rainbow = RainbowWave(beat_pulse=0.0)
    first = [rainbow.render(beat_ctx(b), 4)[0].tolist() for b in (0.0, 2.0, 4.0, 8.0)]
    assert first == [[255, 0, 0], [0, 255, 255], [255, 0, 0], [255, 0, 0]]  # cyan half-way


def test_the_rainbow_turns_on_over_bar_lines() -> None:
    rainbow = RainbowWave(beat_pulse=0.0)
    for bar_line in (4.0, 8.0):
        before = rainbow.render(beat_ctx(bar_line - 1e-6), 20).astype(int)
        on = rainbow.render(beat_ctx(bar_line), 20).astype(int)
        assert np.abs(on - before).max() <= 1


def test_the_tempo_sets_when_the_bars_come_and_nothing_else() -> None:
    rainbow = RainbowWave()
    slow, fast = beat_ctx(2.5, bpm=90.0), beat_ctx(2.5, bpm=150.0)
    assert np.array_equal(rainbow.render(slow, 20), rainbow.render(fast, 20))
