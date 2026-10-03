"""Spec §5.3's look modifiers, a frame at a time: trails, the downbeat flash, the evening
and the brightness cap."""

from __future__ import annotations

import math

import numpy as np
import pytest
from conftest import tempo_ctx

from dj_ledfx.zones.look_modifiers import (
    EVENING_LEVEL,
    EVENING_TINT,
    FLASH_LEVEL,
    TRAILS_FALL,
    Trails,
    capped,
    flashed,
    warmed,
)


def _frame(*levels: float) -> np.ndarray:
    return np.array([[level] * 3 for level in levels], dtype=np.float32)


def test_trails_fade_what_was_shown() -> None:
    trails = Trails()
    trails.apply(_frame(1.0, 0.2), t=10.0, trails_s=1.0)

    shown = trails.apply(_frame(0.0, 0.5), t=10.5, trails_s=1.0)

    np.testing.assert_allclose(shown, _frame(math.exp(-TRAILS_FALL * 0.5), 0.5), rtol=1e-6)


def test_trails_keep_their_own_copy_and_never_change_a_frame() -> None:
    trails = Trails()
    shown = trails.apply(_frame(1.0), t=10.0, trails_s=1.0)
    shown[:] = 0.0  # the runtime draws on the frame it gets back
    given = _frame(0.0)

    after = trails.apply(given, t=10.1, trails_s=1.0)

    assert after[0, 0] == pytest.approx(math.exp(-TRAILS_FALL * 0.1))
    np.testing.assert_array_equal(given, _frame(0.0))


def test_trails_let_go_after_their_time_and_on_new_leds() -> None:
    trails = Trails()
    trails.apply(_frame(1.0), t=10.0, trails_s=1.0)
    np.testing.assert_array_equal(trails.apply(_frame(0.0), t=11.0, trails_s=1.0), _frame(0.0))

    trails.apply(_frame(1.0), t=12.0, trails_s=1.0)
    two = trails.apply(_frame(0.0, 0.0), t=12.1, trails_s=1.0)  # a light joined the zone
    np.testing.assert_array_equal(two, _frame(0.0, 0.0))


def test_a_frame_rendered_for_an_earlier_moment_keeps_the_whole_trail() -> None:
    trails = Trails()  # a shorter horizon renders the next frame a little earlier
    trails.apply(_frame(1.0), t=10.0, trails_s=1.0)

    np.testing.assert_array_equal(trails.apply(_frame(0.0), t=9.99, trails_s=1.0), _frame(1.0))


def test_the_downbeat_flashes_towards_white_and_fades_by_half_a_beat() -> None:
    grey = _frame(0.5)

    np.testing.assert_allclose(flashed(grey, tempo_ctx(4.0)), _frame(0.5 + 0.5 * FLASH_LEVEL))
    quarter = 0.5 + 0.5 * FLASH_LEVEL * 0.25  # a quarter of a beat in: (1 - 0.5)² of it
    np.testing.assert_allclose(flashed(grey, tempo_ctx(4.25)), _frame(quarter), rtol=1e-6)
    for beats in (4.5, 5.0, 6.0, 7.0):  # the rest of the bar, its other beats included
        np.testing.assert_array_equal(flashed(grey, tempo_ctx(beats)), grey)
    np.testing.assert_array_equal(flashed(_frame(1.5), tempo_ctx(4.0)), _frame(1.5))


def test_the_evening_warms_and_dims_by_its_amount() -> None:
    white = _frame(1.0)
    fullest = np.asarray(EVENING_TINT, dtype=np.float32) * np.float32(EVENING_LEVEL)

    np.testing.assert_array_equal(warmed(white, 0.0), white)
    np.testing.assert_allclose(warmed(white, 1.0)[0], fullest, rtol=1e-6)
    np.testing.assert_allclose(warmed(white, 0.5)[0], (1.0 + fullest) / 2.0, rtol=1e-6)
    red, _, blue = warmed(white, 1.0)[0]
    assert red > blue  # warmer


def test_the_cap_lowers_only_what_is_over_it_and_keeps_the_hue() -> None:
    frame = np.array([[1.0, 0.5, 0.0], [0.3, 0.3, 0.3], [2.0, 1.0, 0.0], [0, 0, 0]], np.float32)

    np.testing.assert_allclose(
        capped(frame, 0.6),
        [[0.6, 0.3, 0.0], [0.3, 0.3, 0.3], [0.6, 0.3, 0.0], [0.0, 0.0, 0.0]],
        rtol=1e-6,
    )
    np.testing.assert_array_equal(capped(frame, 0.0), np.zeros_like(frame))
