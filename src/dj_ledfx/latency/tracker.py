from __future__ import annotations

import time
from collections.abc import Callable
from typing import Protocol

from dj_ledfx.latency.strategies import ProbeStrategy, StaticLatency, make_strategy

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
        self._measured = False

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

    @property
    def measured(self) -> bool:
        """Whether a round trip measured while the light streamed has landed since the last
        reset. Until one has, the latency is the seed: the config's, or the type's heuristic."""
        return self._measured

    @property
    def streaming(self) -> bool:
        """Whether a frame went out within STREAMING_WINDOW_S: a round trip measured now
        counts, so only then is the light worth a probe."""
        last = self._last_send
        return last is not None and self._clock() - last <= STREAMING_WINDOW_S

    def note_send(self) -> None:
        """A frame went out now, on this tracker's clock."""
        self._last_send = self._clock()

    def update_rtt(self, rtt_ms: float) -> None:
        """A probe's round trip. Half of it is the one-way latency, but only while the light
        streams: an idle light's Wi-Fi dozes, and its round trips run long."""
        if not self.streaming:
            return
        self._strategy.update(rtt_ms / 2.0)
        # A static latency ignores the sample: it stays the configured one.
        self._measured = not isinstance(self._strategy, StaticLatency)

    def reset(self) -> None:
        self._strategy.reset()
        self._last_send = None
        self._measured = False


class LatencyConfig(Protocol):
    """A kind of device's latency settings: OpenRGB's, LIFX's and Govee's configs all have them."""

    @property
    def latency_strategy(self) -> str: ...
    @property
    def latency_ms(self) -> float: ...
    @property
    def latency_window_size(self) -> int: ...
    @property
    def manual_offset_ms(self) -> float: ...


def tracker_for(
    cfg: LatencyConfig, *, seed_ms: float | None = None, display_ms: float = 0.0
) -> LatencyTracker:
    """A device's tracker, as its kind's config says: the strategy it names, seeded at
    seed_ms (else the config's latency_ms), its window and offset, plus how long the light
    takes to show a frame (display_ms)."""
    seed = cfg.latency_ms if seed_ms is None else seed_ms
    strategy = make_strategy(cfg.latency_strategy, seed, cfg.latency_window_size)
    return LatencyTracker(strategy, cfg.manual_offset_ms, display_ms=display_ms)
