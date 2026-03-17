from __future__ import annotations

import time

from loguru import logger

from dj_ledfx import metrics
from dj_ledfx.types import BeatState

_DRIFT_HARD_SNAP_MS = 5.0


class BeatClock:
    def __init__(self, timeout_s: float = 2.0) -> None:
        self._timeout_s = timeout_s
        self._bpm: float = 0.0
        self._beat_period: float = 0.0  # seconds per beat
        self._last_beat_time: float = 0.0  # monotonic timestamp of last beat
        self._last_beat_number: int = 1  # 1-4
        self._is_playing: bool = False
        self._last_packet_time: float = 0.0
        self._pitch_percent: float | None = None
        self._last_deck_number: int | None = None
        self._last_deck_name: str | None = None

    @property
    def pitch_percent(self) -> float | None:
        return self._pitch_percent

    @property
    def last_deck_number(self) -> int | None:
        return self._last_deck_number

    @property
    def last_deck_name(self) -> str | None:
        return self._last_deck_name

    def on_beat(
        self,
        bpm: float,
        beat_number: int,
        next_beat_ms: int,
        timestamp: float,
        *,
        pitch_percent: float | None = None,
        device_number: int | None = None,
        device_name: str | None = None,
    ) -> None:
        if bpm <= 0:
            return

        new_beat_period = 60.0 / bpm

        if self._is_playing and self._beat_period > 0:
            predicted_beat_time = self._last_beat_time + self._beat_period
            drift_ms = abs(timestamp - predicted_beat_time) * 1000.0

            if drift_ms < _DRIFT_HARD_SNAP_MS:
                correction = (timestamp - predicted_beat_time) / new_beat_period
                adjusted_period = new_beat_period * (1.0 + correction * 0.1)
                self._beat_period = adjusted_period
                logger.trace("Beat drift {:.1f}ms — soft correction", drift_ms)
            else:
                self._beat_period = new_beat_period
                logger.debug("Beat drift {:.1f}ms — hard snap", drift_ms)
        else:
            self._beat_period = new_beat_period

        self._bpm = bpm
        self._last_beat_time = timestamp
        self._last_beat_number = beat_number
        self._last_packet_time = timestamp
        self._is_playing = True
        if pitch_percent is not None:
            self._pitch_percent = pitch_percent
        if device_number is not None:
            self._last_deck_number = device_number
        if device_name is not None:
            self._last_deck_name = device_name
        metrics.BEAT_BPM.set(bpm)
        metrics.BEAT_PHASE.set((self._last_beat_number - 1) / 4.0)

    def get_state(self) -> BeatState:
        return self.get_state_at(time.monotonic())

    def get_state_at(self, at_time: float) -> BeatState:
        if not self._is_playing or self._bpm <= 0:
            return BeatState(
                beat_phase=0.0,
                bar_phase=0.0,
                bpm=0.0,
                is_playing=False,
                next_beat_time=0.0,
            )

        elapsed_since_packet = at_time - self._last_packet_time
        if elapsed_since_packet > self._timeout_s:
            return BeatState(
                beat_phase=0.0,
                bar_phase=0.0,
                bpm=self._bpm,
                is_playing=False,
                next_beat_time=0.0,
            )

        elapsed = at_time - self._last_beat_time
        beats_elapsed = elapsed / self._beat_period
        beat_phase = beats_elapsed % 1.0

        bar_beat_index = (self._last_beat_number - 1 + beats_elapsed) % 4.0
        bar_phase = bar_beat_index / 4.0

        beats_to_next = 1.0 - beat_phase
        next_beat_time = at_time + beats_to_next * self._beat_period

        return BeatState(
            beat_phase=beat_phase,
            bar_phase=bar_phase,
            bpm=self._bpm,
            is_playing=True,
            next_beat_time=next_beat_time,
        )
