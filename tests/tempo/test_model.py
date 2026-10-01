from __future__ import annotations

import pytest

from dj_ledfx.tempo.model import (
    DEFAULT_BPM,
    InternalTempo,
    TempoError,
    TempoLockedError,
    TempoSettings,
    check_bpm,
)


def test_a_bpm_is_a_finite_number_from_30_to_300() -> None:
    assert check_bpm(30) == 30.0
    assert check_bpm(124.5) == 124.5
    assert check_bpm(300.0) == 300.0
    for bad in (29.9, 300.1, 0, -120, float("nan"), float("inf"), True, "120", None):
        with pytest.raises(TempoError):
            check_bpm(bad)


def test_a_locked_tempo_says_which_lock_and_what_to_do() -> None:
    error = TempoLockedError("prodjlink")

    assert str(error) == (
        "The tempo is locked to Pro DJ Link: choose Auto or Internal to set it here"
    )
    assert error.lock == "prodjlink"
    assert isinstance(error, TempoError)


def test_the_settings_start_on_auto_at_the_default_bpm() -> None:
    settings = TempoSettings()

    assert settings.lock == "auto"
    assert settings.internal == InternalTempo(DEFAULT_BPM, "default", None)
    assert settings.last_set is None
