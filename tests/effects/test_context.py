from __future__ import annotations

import time

from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.effects.context import (
    NO_SIGNALS,
    RenderContext,
    SignalView,
    render_context,
    to_beat_context,
)


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
    clock = BeatClock()
    now = time.monotonic()
    clock.on_beat(bpm=120.0, beat_number=1, next_beat_ms=500, timestamp=now)
    target = now + 0.25

    ctx = render_context(clock, target, 1 / 60)

    expected = clock.get_state_at(target)
    assert ctx.t == target
    assert ctx.dt == 1 / 60
    assert ctx.beat_phase == expected.beat_phase
    assert ctx.bar_phase == expected.bar_phase
    assert ctx.bpm == 120.0
    assert (ctx.beat_index, ctx.bar_index) == (0, 0)
    assert ctx.signals is NO_SIGNALS


def test_to_beat_context_keeps_phases_bpm_and_dt() -> None:
    ctx = RenderContext(
        t=1.0,
        dt=0.02,
        beat_phase=0.3,
        bar_phase=0.7,
        bpm=128.0,
        beat_index=0,
        bar_index=0,
        signals=NO_SIGNALS,
    )
    beat = to_beat_context(ctx)
    assert (beat.beat_phase, beat.bar_phase, beat.bpm, beat.dt) == (0.3, 0.7, 128.0, 0.02)
