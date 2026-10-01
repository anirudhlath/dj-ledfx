"""The tempo clock on fake time, the other half: a DJ takes over, drifts, hands back."""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import timedelta

import pytest
from conftest import events
from tempo_fakes import PLAYER, START, START_WALL, FakeTime, beat_event, play, tempo_clock

from dj_ledfx.events import EventBus
from dj_ledfx.tempo.clock import SOFT_GAIN
from dj_ledfx.tempo.model import (
    QUIET_S,
    SET_GAP_S,
    DecksChanged,
    DeckView,
    DjSet,
    InternalTempo,
    TempoChanged,
)

PERIOD = 60.0 / 128.0  # play()'s default tempo


def test_a_dj_takes_over_and_the_phase_snaps_once() -> None:
    time = FakeTime()
    clock = tempo_clock(time)
    time.now += 1.3  # the internal clock is at beat 2.6

    [first] = play(clock, time, 1, first=3)

    sample = clock.sample_at(first)
    assert (clock.source, clock.stale, clock.bpm) == ("prodjlink", False, 128.0)
    assert (sample.beat_in_bar, sample.beat_phase) == (3, 0.0)
    assert sample.beat_index == 2  # the nearest third beat of a bar: no jump of a bar
    assert clock.dj_playing()


def test_the_followed_deck_s_beats_keep_the_clock_on_time() -> None:
    time = FakeTime()
    clock = tempo_clock(time)
    *_, last = play(clock, time, 8)

    time.now = last + PERIOD + 0.003  # 3 ms late: soft correction
    clock.on_beat(beat_event(time.now, beat=1))
    soft = clock.sample_at(time.now + PERIOD / 2).beat_phase
    time.now += PERIOD + 0.02  # 20 ms late after that: a hard snap
    clock.on_beat(beat_event(time.now, beat=2))
    hard = clock.sample_at(time.now + PERIOD / 2).beat_phase

    assert soft == pytest.approx(0.5 / (1.0 + SOFT_GAIN * 0.003 / PERIOD))
    assert hard == pytest.approx(0.5)
    assert clock.sample_at(time.now).beat_index == 9


# Review Focus 1: two decks in a mix.
def test_two_decks_in_a_mix_never_pull_the_beat_back_and_forth() -> None:
    time = FakeTime()
    clock = tempo_clock(time)
    start = time.now
    for k in range(16):  # deck 2 plays 100 ms behind deck 1 at the same tempo
        time.now = start + k * PERIOD
        clock.on_beat(beat_event(time.now, beat=k % 4 + 1, deck=1))
        time.now += 0.1
        clock.on_beat(beat_event(time.now, beat=k % 4 + 1, deck=2))
        assert clock.sample_at(start + k * PERIOD).beat_phase == pytest.approx(0.0, abs=1e-9)
    assert [deck.master for deck in clock.decks()] == [True, False]
    assert clock.followed_deck() == clock.decks()[0]

    # Deck 1 stops. Once it has been quiet for 2 s, deck 2 takes the clock.
    deck_2 = start + 15 * PERIOD + 0.1
    for k in range(1, 8):
        time.now = deck_2 + k * PERIOD
        clock.on_beat(beat_event(time.now, beat=(15 + k) % 4 + 1, deck=2))
    assert clock.sample_at(time.now).beat_phase == pytest.approx(0.0, abs=1e-9)
    assert [deck.master for deck in clock.decks()] == [False, True]
    assert clock.followed_deck() == clock.decks()[1]


# Review Focus 3: a lost packet, a short pause.
def test_a_lost_beat_packet_is_not_a_drift() -> None:
    time = FakeTime()
    clock = tempo_clock(time)
    *_, last = play(clock, time, 8)

    time.now = last + 2 * PERIOD  # beat 9's packet never came; beat 10's is on time
    clock.on_beat(beat_event(time.now, beat=2))
    on_time = clock.sample_at(time.now + PERIOD / 2)
    time.now += 1.5  # a 1.5 s pause
    clock.settle()
    paused = clock.source

    assert on_time.beat_index == 9 and on_time.beat_phase == pytest.approx(0.5)
    assert paused == "prodjlink"  # under 2 s: no hand-back


def test_a_dj_who_stops_hands_back_without_a_jump() -> None:
    time = FakeTime()
    clock = tempo_clock(time)
    *_, last = play(clock, time, 8, bpm=125.0)
    time.now = last + QUIET_S + 0.1

    before = clock.sample_at(time.now)
    clock.settle()
    after = clock.sample_at(time.now)

    assert clock.source == "internal"
    assert after.beat_index == before.beat_index
    assert after.beat_phase == pytest.approx(before.beat_phase)
    assert clock.internal == InternalTempo(125.0, "kept", time.wall())
    assert clock.sample_at(time.now + 0.48).beat_index == after.beat_index + 1  # at 125 BPM


def test_tapping_holds_the_internal_clock_until_a_dj_starts_again() -> None:
    time = FakeTime()
    clock = tempo_clock(time)
    *_, last = play(clock, time, 4)
    for k in range(3):  # the owner taps 100 BPM while the DJ plays
        time.now = last + 0.1 + 0.6 * k
        clock.tap()
    assert (clock.source, clock.held) == ("internal", True)
    assert clock.bpm == pytest.approx(100.0)

    *_, last = play(clock, time, 4)  # the DJ plays on: still held
    assert clock.source == "internal"
    time.now = last + QUIET_S + 0.5  # the DJ stops
    clock.settle()
    play(clock, time, 1)  # and starts again

    assert (clock.source, clock.held, clock.bpm) == ("prodjlink", False, 128.0)


def test_a_stray_tap_during_a_set_keeps_the_dj_s_tempo_as_a_nudge_does() -> None:
    time = FakeTime()
    clock = tempo_clock(time)
    *_, last = play(clock, time, 4, bpm=125.0)
    time.now = last + 0.1

    clock.tap()

    assert (clock.source, clock.held, clock.bpm) == ("internal", True, 125.0)
    assert clock.internal == InternalTempo(125.0, "kept", time.wall())


def test_decks_show_what_the_beats_carry() -> None:
    time = FakeTime()
    clock = tempo_clock(time)
    play(clock, time, 2, bpm=124.0, pitch_percent=1.2, deck=2)
    time.now += 0.1
    clock.on_beat(beat_event(time.now, deck=3, bpm=126.0))

    assert clock.decks() == (
        DeckView(2, PLAYER, "playing", 124.0, 1.2, True),
        DeckView(3, PLAYER, "playing", 126.0, 0.0, False),
    )
    assert clock.bpm == pytest.approx(124.0 * 1.012)  # the clock's tempo is pitch-adjusted
    time.now += QUIET_S + 1.0
    clock.settle()

    assert [deck.state for deck in clock.decks()] == ["cued", "cued"]
    assert clock.followed_deck() is None  # handed back: no deck drives the clock


def test_a_dj_set_is_remembered_when_it_ends() -> None:
    time = FakeTime()
    clock = tempo_clock(time)
    *_, last = play(clock, time, 64)
    time.now = last + QUIET_S + 0.5
    clock.settle()

    assert clock.last_set == DjSet(START_WALL, START_WALL + timedelta(seconds=last - START))
    time.now += 600.0  # ten minutes later the DJ goes on: the same set
    *_, again = play(clock, time, 4)
    time.now = again + QUIET_S + 0.5
    clock.settle()
    assert clock.last_set is not None and clock.last_set.started == START_WALL

    time.now += SET_GAP_S + 1.0  # after half an hour of silence, a new set
    clock.settle()
    assert clock.decks() == ()
    play(clock, time, 4)
    time.now += QUIET_S + 1.0
    clock.settle()
    assert clock.last_set is not None and clock.last_set.started > START_WALL


# Review Focus 2: garbage never reaches the clock.
def test_impossible_beats_are_ignored() -> None:
    time = FakeTime()
    clock = tempo_clock(time)
    good = beat_event(time.now)

    for bad in (
        replace(good, bpm=math.nan),
        replace(good, bpm=math.inf),
        replace(good, bpm=0.0),
        replace(good, bpm=-128.0),
        replace(good, bpm=900.0),
        replace(good, pitch_percent=math.nan),
        replace(good, timestamp=math.nan),
    ):
        clock.on_beat(bad)

    assert (clock.source, clock.bpm, clock.decks()) == ("internal", 120.0, ())


def test_a_pro_dj_link_lock_waits_for_a_dj_and_carries_on_without_one() -> None:
    time = FakeTime()
    clock = tempo_clock(time)
    clock.set_tempo("prodjlink")
    assert clock.stale

    *_, last = play(clock, time, 4)
    assert (clock.source, clock.stale, clock.bpm) == ("prodjlink", False, 128.0)
    time.now = last + QUIET_S + 0.5
    clock.settle()

    assert (clock.source, clock.stale, clock.bpm) == ("prodjlink", True, 128.0)
    assert clock.internal == InternalTempo()  # a lock hands nothing back
    now = clock.sample_at(time.now).beat_index
    assert clock.sample_at(time.now + PERIOD).beat_index == now + 1  # it carries on


def test_decks_and_the_tempo_are_published_when_they_change() -> None:
    bus = EventBus()
    decks, tempo = events(bus, DecksChanged), events(bus, TempoChanged)
    time = FakeTime()
    clock = tempo_clock(time, event_bus=bus)

    *_, last = play(clock, time, 4)  # a deck appears, and takes over
    assert (len(decks), len(tempo)) == (1, 1)
    time.now = last + QUIET_S + 0.5
    clock.settle()  # it goes quiet, and hands back

    assert (len(decks), len(tempo)) == (2, 2)
