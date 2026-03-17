import numpy as np
import pytest

from dj_ledfx.effects.beat_pulse import BeatPulse
from dj_ledfx.effects.params import EffectParam


def test_beat_pulse_on_beat_is_bright() -> None:
    effect = BeatPulse()
    result = effect.render(beat_phase=0.0, bar_phase=0.0, dt=0.016, led_count=10)
    assert result.shape == (10, 3)
    assert result.dtype == np.uint8
    assert result.max() == 255


def test_beat_pulse_decays_after_beat() -> None:
    effect = BeatPulse()
    on_beat = effect.render(beat_phase=0.0, bar_phase=0.0, dt=0.016, led_count=10)
    mid_beat = effect.render(beat_phase=0.5, bar_phase=0.0, dt=0.016, led_count=10)
    assert mid_beat.max() < on_beat.max()


def test_beat_pulse_near_next_beat_is_dark() -> None:
    effect = BeatPulse()
    result = effect.render(beat_phase=0.99, bar_phase=0.0, dt=0.016, led_count=10)
    assert result.max() < 20


def test_beat_pulse_color_changes_with_bar_phase() -> None:
    effect = BeatPulse()
    beat1 = effect.render(beat_phase=0.0, bar_phase=0.0, dt=0.016, led_count=1)
    beat3 = effect.render(beat_phase=0.0, bar_phase=0.5, dt=0.016, led_count=1)
    assert not np.array_equal(beat1, beat3)


def test_beat_pulse_custom_palette() -> None:
    effect = BeatPulse(palette=["#ffffff", "#000000", "#ff0000", "#00ff00"], gamma=1.0)
    result = effect.render(beat_phase=0.0, bar_phase=0.0, dt=0.016, led_count=1)
    assert result[0, 0] == 255
    assert result[0, 1] == 255
    assert result[0, 2] == 255


def test_beat_pulse_parameters_schema():
    schema = BeatPulse.parameters()
    assert "gamma" in schema
    assert schema["gamma"].type == "float"
    assert schema["gamma"].min == 0.5
    assert schema["gamma"].max == 5.0
    assert "palette" in schema
    assert schema["palette"].type == "color_list"


def test_beat_pulse_get_params():
    effect = BeatPulse(gamma=3.0)
    params = effect.get_params()
    assert params["gamma"] == 3.0
    assert isinstance(params["palette"], list)


def test_beat_pulse_set_params():
    effect = BeatPulse()
    effect.set_params(gamma=4.0)
    assert effect.get_params()["gamma"] == 4.0


def test_beat_pulse_set_params_validates():
    effect = BeatPulse()
    with pytest.raises(ValueError):
        effect.set_params(gamma=0.1)
