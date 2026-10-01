"""The tempo clock on fake time (spec §9: "source takeover and source loss, driven by fake
time"). This half: the internal clock, the lock and the controls."""

from __future__ import annotations

import math
from unittest.mock import MagicMock

import pytest
from conftest import events
from tempo_fakes import START, START_WALL, FakeTime, tempo_clock

from dj_ledfx import metrics
from dj_ledfx.events import EventBus
from dj_ledfx.tempo.model import (
    InternalTempo,
    TempoChanged,
    TempoError,
    TempoLockedError,
    TempoSettings,
)


def test_the_internal_clock_runs_from_the_start() -> None:
    time = FakeTime()
    clock = tempo_clock(time)

    later = clock.sample_at(START + 2.75)  # 120 BPM: 5.5 beats

    assert (later.beat_index, later.bar_index, later.beat_in_bar) == (5, 1, 2)
    assert later.beat_phase == pytest.approx(0.5)
    assert later.bar_phase == pytest.approx(0.375)
    assert (later.bpm, later.source, later.stale, later.pitch_percent) == (
        120.0,
        "internal",
        False,
        0.0,
    )


def test_a_bpm_set_here_changes_the_tempo_without_a_jump() -> None:
    time = FakeTime()
    clock = tempo_clock(time)
    time.now += 0.75  # beat 1.5

    clock.set_tempo("auto", 60.0)

    assert clock.sample_at(time.now).beat_index == 1
    assert clock.sample_at(time.now).beat_phase == pytest.approx(0.5)
    assert clock.sample_at(time.now + 1.0).beat_phase == pytest.approx(0.5)  # a beat a second
    assert clock.sample_at(time.now + 1.0).beat_index == 2
    assert clock.internal == InternalTempo(60.0, "set", START_WALL.replace(microsecond=750_000))
    assert clock.held  # under Auto it holds until a DJ starts again


def test_the_clock_starts_from_its_settings() -> None:
    settings = TempoSettings(lock="internal", internal=InternalTempo(95.0, "tapped", START_WALL))

    clock = tempo_clock(FakeTime(), settings=settings)

    assert (clock.lock, clock.bpm, clock.internal) == ("internal", 95.0, settings.internal)
    assert clock.settings() == settings


def test_a_lock_pins_a_source() -> None:
    clock = tempo_clock(FakeTime())

    clock.set_tempo("prodjlink")
    assert (clock.source, clock.stale) == ("prodjlink", True)  # no DJ: nothing to follow
    clock.set_tempo("music")
    assert (clock.source, clock.stale) == ("music", True)  # the music's beat arrives in M7
    clock.set_tempo("internal")
    assert (clock.source, clock.stale) == ("internal", False)


# Review Focus 2: garbage never reaches the clock.
def test_tempo_controls_refuse_bad_values() -> None:
    time = FakeTime()
    clock = tempo_clock(time)
    before = clock.sample_at(time.now)

    for bpm in (math.nan, math.inf, 0.0, 29.0, 301.0, -120.0):
        with pytest.raises(TempoError):
            clock.set_tempo("auto", bpm)
    with pytest.raises(TempoError):
        clock.set_tempo("sideways")  # type: ignore[arg-type]
    for delta in (math.nan, math.inf, 1.5, -2.0):
        with pytest.raises(TempoError):
            clock.nudge(delta)
    with pytest.raises(TempoError) as refused:
        clock.set_tempo("prodjlink", 120.0)  # a BPM only for Auto or Internal
    assert not isinstance(refused.value, TempoLockedError)  # nothing is locked yet

    assert (clock.lock, clock.bpm, clock.held) == ("auto", 120.0, False)
    assert clock.sample_at(time.now) == before


def test_a_nudge_moves_the_beat_not_the_tempo() -> None:
    time = FakeTime()
    clock = tempo_clock(time)
    time.now += 0.5  # beat 1

    clock.nudge(0.25)
    assert clock.sample_at(time.now).beat_phase == pytest.approx(0.25)  # sooner
    clock.nudge(-0.5)
    assert clock.sample_at(time.now).beat_phase == pytest.approx(0.75)  # back past beat 1
    assert clock.sample_at(time.now).beat_index == 0

    assert clock.bpm == 120.0
    assert clock.sample_at(time.now + 0.5).beat_phase == pytest.approx(0.75)


def test_taps_set_the_tempo_from_the_third_and_the_first_is_a_downbeat() -> None:
    time = FakeTime()
    clock = tempo_clock(time, settings=TempoSettings(internal=InternalTempo(90.0)))
    time.now += 3.1  # somewhere in bar 1

    times = []
    for _ in range(3):
        clock.tap()
        times.append(time.now)
        assert clock.bpm == (90.0 if len(times) < 3 else pytest.approx(120.0))
        time.now += 0.5

    first, third = clock.sample_at(times[0]), clock.sample_at(times[2])
    assert (first.beat_in_bar, first.beat_phase) == (1, 0.0)
    assert (third.beat_in_bar, third.beat_phase) == (3, 0.0)
    assert (clock.internal.how, clock.held) == ("tapped", True)


def test_taps_before_the_run_has_a_tempo_leave_how_the_bpm_was_set() -> None:
    time = FakeTime()
    settings = TempoSettings(internal=InternalTempo(95.0, "set", START_WALL))
    clock = tempo_clock(time, settings=settings)
    time.now += 60.0

    clock.tap()
    time.now += 0.5
    clock.tap()

    assert clock.internal == settings.internal  # still "95.0 · set 19:00": nothing tapped yet
    assert (clock.bpm, clock.held) == (95.0, True)  # it holds, as a nudge does


def test_a_locked_clock_refuses_taps_and_nudges() -> None:
    clock = tempo_clock(FakeTime())
    clock.set_tempo("prodjlink")

    with pytest.raises(TempoLockedError):
        clock.tap()
    with pytest.raises(TempoLockedError):
        clock.nudge(0.1)


def test_a_change_is_published_once() -> None:
    bus = EventBus()
    changed = events(bus, TempoChanged)
    clock = tempo_clock(FakeTime(), event_bus=bus)

    clock.set_tempo("internal")
    clock.set_tempo("internal")  # nothing new
    clock.settle()

    assert len(changed) == 1


# The internal clock drives with no beats arriving, so the BPM gauge can't wait for one.
def test_the_bpm_gauge_follows_whatever_drives_the_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    gauge = MagicMock()
    monkeypatch.setattr(metrics, "BEAT_BPM", gauge)
    clock = tempo_clock(FakeTime())

    clock.settle()
    clock.set_tempo("internal", 96.0)
    clock.settle()

    assert [call.args for call in gauge.set.call_args_list] == [(120.0,), (96.0,)]
