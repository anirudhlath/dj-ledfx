from __future__ import annotations

from conftest import tempo_ctx
from tempo_fakes import START, FakeTime, play, tempo_clock

from dj_ledfx.effects.context import (
    DJ_BEAT,
    NO_SIGNALS,
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
