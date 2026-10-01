import numpy as np
import pytest
from tempo_fakes import START, FakeTime, play, tempo_clock

from dj_ledfx.effects.context import render_context, to_beat_context
from dj_ledfx.effects.strobe import Strobe
from dj_ledfx.tempo.clock import TempoClock
from dj_ledfx.tempo.model import InternalTempo, TempoSettings
from dj_ledfx.types import BeatContext


def _ctx(beat_phase: float = 0.0, bar_phase: float = 0.0, bpm: float = 128.0) -> BeatContext:
    """A DJ's beat: Strobe's subdivisions."""
    return BeatContext(beat_phase=beat_phase, bar_phase=bar_phase, bpm=bpm, dt=0.016, dj=True)


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


def _flashes_per_s(clock: TempoClock, seconds: float = 4.0) -> float:
    """How often Strobe flashes on this clock, drawn every millisecond from START."""
    strobe, flashes, was_on = Strobe(), 0, False
    for k in range(round(seconds * 1000)):
        ctx = to_beat_context(render_context(clock, START + k / 1000, 0.016))
        on = bool(strobe.render(ctx, 1).any())
        flashes += on and not was_on
        was_on = on
    return flashes / seconds


def test_strobe_flashes_once_a_beat_on_the_internal_clock() -> None:
    clock = tempo_clock(FakeTime())  # no DJ: the internal clock's 120 BPM

    assert _flashes_per_s(clock) == 2.0


@pytest.mark.parametrize("bpm", [180.0, 200.0, 300.0])
def test_strobe_stays_under_three_flashes_a_second_without_a_dj(bpm: float) -> None:
    clock = tempo_clock(FakeTime(), settings=TempoSettings(internal=InternalTempo(bpm)))

    assert _flashes_per_s(clock) < 3.0


def test_strobe_keeps_its_subdivisions_while_a_dj_plays() -> None:
    time = FakeTime()
    clock = tempo_clock(time)
    play(clock, time, 9, bpm=120.0)  # beats from START to START + 4 s

    assert _flashes_per_s(clock) == 4.0  # eighth notes at 120 BPM, as before M3
