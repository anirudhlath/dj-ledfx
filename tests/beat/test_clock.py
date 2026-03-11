import time

from dj_ledfx.beat.clock import BeatClock


def test_initial_state() -> None:
    clock = BeatClock()
    state = clock.get_state()
    assert state.is_playing is False
    assert state.bpm == 0.0
    assert state.beat_phase == 0.0
    assert state.bar_phase == 0.0


def test_on_beat_starts_playing() -> None:
    clock = BeatClock()
    now = time.monotonic()
    clock.on_beat(bpm=128.0, beat_number=1, next_beat_ms=468, timestamp=now)
    state = clock.get_state()
    assert state.is_playing is True
    assert state.bpm == 128.0


def test_phase_advances_between_beats() -> None:
    clock = BeatClock()
    now = time.monotonic()
    clock.on_beat(bpm=120.0, beat_number=1, next_beat_ms=500, timestamp=now)
    state = clock.get_state_at(now + 0.25)
    assert 0.4 < state.beat_phase < 0.6


def test_bar_phase_tracks_beat_position() -> None:
    clock = BeatClock()
    now = time.monotonic()
    clock.on_beat(bpm=120.0, beat_number=3, next_beat_ms=500, timestamp=now)
    state = clock.get_state_at(now)
    assert 0.49 < state.bar_phase < 0.51


def test_stops_after_timeout() -> None:
    clock = BeatClock(timeout_s=2.0)
    now = time.monotonic()
    clock.on_beat(bpm=128.0, beat_number=1, next_beat_ms=468, timestamp=now)
    state = clock.get_state_at(now + 3.0)
    assert state.is_playing is False


def test_hard_snap_on_large_drift() -> None:
    clock = BeatClock()
    now = time.monotonic()
    clock.on_beat(bpm=120.0, beat_number=1, next_beat_ms=500, timestamp=now)
    clock.on_beat(bpm=120.0, beat_number=2, next_beat_ms=500, timestamp=now + 0.510)
    state = clock.get_state_at(now + 0.510)
    assert state.beat_phase < 0.05


def test_extrapolate_future_phase() -> None:
    clock = BeatClock()
    now = time.monotonic()
    clock.on_beat(bpm=120.0, beat_number=1, next_beat_ms=500, timestamp=now)
    state = clock.get_state_at(now + 1.0)
    assert state.beat_phase < 0.05 or state.beat_phase > 0.95
