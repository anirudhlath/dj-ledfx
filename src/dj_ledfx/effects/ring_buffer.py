"""A running zone's rendered frames, ahead of time: the engine writes them, the send loops
read the one nearest each light's own moment."""

from __future__ import annotations

from dj_ledfx.types import RenderedFrame


class RingBuffer:
    def __init__(self, capacity: int) -> None:
        self._capacity = capacity
        self._frames: list[RenderedFrame | None] = [None] * capacity
        self._write_index = 0
        self._count = 0

    @property
    def count(self) -> int:
        return self._count

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def fill_level(self) -> float:
        return self._count / self._capacity

    def write(self, frame: RenderedFrame) -> None:
        self._frames[self._write_index] = frame
        self._write_index = (self._write_index + 1) % self._capacity
        if self._count < self._capacity:
            self._count += 1

    def find_nearest(self, target_time: float) -> RenderedFrame | None:
        best: RenderedFrame | None = None
        best_diff = float("inf")

        for frame in self._frames:
            if frame is None:
                continue
            diff = abs(frame.target_time - target_time)
            if diff < best_diff:
                best_diff = diff
                best = frame

        if best is None:
            return None

        return RenderedFrame(
            colors=best.colors.copy(),
            target_time=best.target_time,
            beat_phase=best.beat_phase,
            bar_phase=best.bar_phase,
        )
