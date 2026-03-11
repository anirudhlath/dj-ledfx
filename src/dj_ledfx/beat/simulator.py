from __future__ import annotations

import asyncio
import time

from loguru import logger

from dj_ledfx.events import EventBus
from dj_ledfx.prodjlink.listener import BeatEvent


class BeatSimulator:
    def __init__(
        self,
        event_bus: EventBus,
        bpm: float = 128.0,
    ) -> None:
        self._event_bus = event_bus
        self._bpm = bpm
        self._running = False
        self._beat_number = 0  # will start at 1

    def stop(self) -> None:
        self._running = False

    async def run(self) -> None:
        self._running = True
        beat_period = 60.0 / self._bpm
        logger.info("BeatSimulator started at {:.1f} BPM", self._bpm)

        next_beat = time.monotonic()

        while self._running:
            now = time.monotonic()
            if now < next_beat:
                await asyncio.sleep(next_beat - now)
                if not self._running:
                    break

            self._beat_number = (self._beat_number % 4) + 1
            ts = time.monotonic()
            next_beat_ms = int(beat_period * 1000)

            event = BeatEvent(
                bpm=self._bpm,
                beat_position=self._beat_number,
                next_beat_ms=next_beat_ms,
                device_number=0,
                device_name="BeatSimulator",
                timestamp=ts,
            )
            self._event_bus.emit(event)
            logger.debug("Sim beat {}/4 at {:.1f} BPM", self._beat_number, self._bpm)

            next_beat += beat_period

        logger.info("BeatSimulator stopped")
