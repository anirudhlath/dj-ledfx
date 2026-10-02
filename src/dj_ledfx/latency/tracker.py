from __future__ import annotations

import time
from collections.abc import Callable

from dj_ledfx.latency.strategies import ProbeStrategy

# A round trip that arrives within this long of a send was measured while the light streamed.
STREAMING_WINDOW_S = 0.5


class LatencyTracker:
    """A light's latency: one-way network time from its strategy, plus the time the light
    takes to show a frame it has (display_ms), plus the owner's offset."""

    def __init__(
        self,
        strategy: ProbeStrategy,
        manual_offset_ms: float = 0.0,
        *,
        display_ms: float = 0.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._strategy = strategy
        self._manual_offset_ms = manual_offset_ms
        self._display_ms = display_ms
        self._clock = clock
        self._last_send: float | None = None

    @property
    def manual_offset_ms(self) -> float:
        return self._manual_offset_ms

    @manual_offset_ms.setter
    def manual_offset_ms(self, value: float) -> None:
        self._manual_offset_ms = value

    @property
    def effective_latency_ms(self) -> float:
        return self._strategy.get_latency() + self._display_ms + self._manual_offset_ms

    @property
    def effective_latency_s(self) -> float:
        return self.effective_latency_ms / 1000.0

    def update(self, sample_ms: float) -> None:
        """A one-way sample, taken as it is: a send that returns once the device has it."""
        self._strategy.update(sample_ms)

    def note_send(self) -> None:
        """A frame went out now, on this tracker's clock."""
        self._last_send = self._clock()

    def update_rtt(self, rtt_ms: float) -> None:
        """A probe's round trip. Half of it is the one-way latency, but only while the light
        streams: an idle light's Wi-Fi dozes, and its round trips run long."""
        if self._last_send is None or self._clock() - self._last_send > STREAMING_WINDOW_S:
            return
        self._strategy.update(rtt_ms / 2.0)

    def reset(self) -> None:
        self._strategy.reset()
        self._last_send = None
