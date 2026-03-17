import importlib
import time
from unittest.mock import MagicMock

import dj_ledfx.metrics as metrics_mod
from dj_ledfx.beat.clock import BeatClock


def test_on_beat_sets_bpm_metric() -> None:
    """Verify on_beat() calls metrics.BEAT_BPM.set()."""
    importlib.reload(metrics_mod)
    mock_bpm = MagicMock()
    mock_phase = MagicMock()
    original_bpm = metrics_mod.BEAT_BPM
    original_phase = metrics_mod.BEAT_PHASE
    metrics_mod.BEAT_BPM = mock_bpm
    metrics_mod.BEAT_PHASE = mock_phase
    try:
        from dj_ledfx.beat.clock import BeatClock

        clock = BeatClock()
        clock.on_beat(bpm=128.0, beat_number=1, next_beat_ms=468, timestamp=time.monotonic())
        mock_bpm.set.assert_called_once_with(128.0)
        mock_phase.set.assert_called_once()
    finally:
        metrics_mod.BEAT_BPM = original_bpm
        metrics_mod.BEAT_PHASE = original_phase


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


def test_clock_stores_deck_info() -> None:
    clock = BeatClock()
    clock.on_beat(128.0, 1, 469, time.monotonic(),
                  pitch_percent=2.3, device_number=1, device_name="XDJ-AZ")
    assert clock.pitch_percent == 2.3
    assert clock.last_deck_number == 1
    assert clock.last_deck_name == "XDJ-AZ"


def test_clock_deck_info_defaults_none() -> None:
    clock = BeatClock()
    assert clock.pitch_percent is None
    assert clock.last_deck_number is None
    assert clock.last_deck_name is None
