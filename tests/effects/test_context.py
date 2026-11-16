from __future__ import annotations

from conftest import render_ctx, tempo_ctx
from sun_fakes import AT_DUSK
from tempo_fakes import START, FakeTime, play, tempo_clock

from dj_ledfx.effects.context import (
    DJ_BEAT,
    EVENING,
    NO_SIGNALS,
    SUN_AZIMUTH,
    SUN_ELEVATION,
    RenderContext,
    SignalView,
    render_context,
    to_beat_context,
)
from dj_ledfx.tempo.model import TempoSettings


def test_signal_view_returns_default_for_missing_signal() -> None:
    view = SignalView({"loudness": 0.4})
    assert view.get("loudness") == 0.4
    assert view.get("bass") == 0.0
    assert view.get("bass", 0.5) == 0.5


def test_signal_view_is_a_snapshot() -> None:
    values = {"loudness": 0.4}
    view = SignalView(values)
    values["loudness"] = 0.9
    assert view.get("loudness") == 0.4


def test_render_context_samples_the_clock_at_the_target_time() -> None:
    clock = tempo_clock(FakeTime())  # the internal clock: 120 BPM, beat 0 at START
    target = START + 2.75  # five and a half beats on: the second bar's second beat

    ctx = render_context(clock, target, 1 / 60)

    sample = clock.sample_at(target)  # test_clock.py checks its numbers
    assert (ctx.t, ctx.dt, ctx.bpm) == (target, 1 / 60, sample.bpm)
    assert (ctx.beat_index, ctx.beat_phase, ctx.bar_index, ctx.bar_phase) == (
        sample.beat_index,
        sample.beat_phase,
        sample.bar_index,
        sample.bar_phase,
    )
    assert ctx.signals is NO_SIGNALS


def test_a_dj_s_beat_is_signalled_to_the_looks() -> None:
    time = FakeTime()
    clock = tempo_clock(time)
    play(clock, time, 2)

    ctx = render_context(clock, time.now, 1 / 60)

    assert ctx.signals.get(DJ_BEAT) == 1.0
    assert to_beat_context(ctx).dj


def test_the_evening_is_signalled_to_the_looks() -> None:
    time = FakeTime()
    clock = tempo_clock(time)
    play(clock, time, 2)

    ctx = render_context(clock, time.now, 1 / 60, evening=0.4)

    assert (ctx.signals.get(EVENING), ctx.signals.get(DJ_BEAT)) == (0.4, 1.0)
    assert render_context(clock, time.now, 1 / 60).signals.get(EVENING) == 0.0


# M6 ruling 5: the sun's height and bearing (true north's degrees) while there is a sun,
# and neither without one, so a look reading them gets its own default.
def test_a_frame_carries_the_suns_signals_while_there_is_one() -> None:
    time = FakeTime()
    clock = tempo_clock(time)
    play(clock, time, 2)

    sunny = render_context(clock, time.now, 1 / 60, 0.4, sun=AT_DUSK).signals
    sunless = render_context(clock, time.now, 1 / 60, 0.4, sun=None).signals

    assert (sunny.get(SUN_ELEVATION), sunny.get(SUN_AZIMUTH)) == (2.0, 270.0)
    assert (sunless.get(SUN_ELEVATION, -99.0), sunless.get(SUN_AZIMUTH, -99.0)) == (-99.0, -99.0)
    for signals in (sunny, sunless):
        assert (signals.get(EVENING), signals.get(DJ_BEAT)) == (0.4, 1.0)
    alone = render_context(tempo_clock(FakeTime()), START, 1 / 60, sun=AT_DUSK).signals
    assert (alone.get(SUN_ELEVATION), alone.get(EVENING), alone.get(DJ_BEAT)) == (2.0, 0.0, 0.0)


def test_a_pro_dj_link_lock_with_no_dj_signals_no_dj() -> None:
    clock = tempo_clock(FakeTime(), settings=TempoSettings(lock="prodjlink"))

    ctx = render_context(clock, START, 1 / 60)  # stale: the clock carries on alone

    assert ctx.signals is NO_SIGNALS
    assert not to_beat_context(ctx).dj


def test_to_beat_context_keeps_the_beat_bpm_and_dt() -> None:
    ctx = RenderContext(
        t=1.0,
        dt=0.02,
        beat_phase=0.3,
        bar_phase=0.7,
        bpm=128.0,
        beat_index=37,
        bar_index=9,
        signals=NO_SIGNALS,
    )
    beat = to_beat_context(ctx)
    assert (beat.beat_index, beat.beat_phase, beat.bar_phase, beat.bpm, beat.dt) == (
        37,
        0.3,
        0.7,
        128.0,
        0.02,
    )


def test_a_moment_says_where_the_music_is_in_beats() -> None:
    assert tempo_ctx(13.25).beats == 13.25
    assert to_beat_context(tempo_ctx(13.25)).beats == 13.25


def test_a_frame_carries_the_looks_elapsed_time() -> None:
    clock = tempo_clock(FakeTime())

    assert render_context(clock, START, 1 / 60, elapsed_s=12.5).elapsed_s == 12.5
    assert render_context(clock, START, 1 / 60).elapsed_s == 0.0  # a look that keeps no time
    assert tempo_ctx(4.0).elapsed_s == render_ctx().elapsed_s == 0.0
