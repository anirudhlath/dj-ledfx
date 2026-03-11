from __future__ import annotations

from dj_ledfx.latency.strategies import ProbeStrategy


class LatencyTracker:
    def __init__(
        self,
        strategy: ProbeStrategy,
        manual_offset_ms: float = 0.0,
    ) -> None:
        self._strategy = strategy
        self._manual_offset_ms = manual_offset_ms

    @property
    def effective_latency_ms(self) -> float:
        return self._strategy.get_latency() + self._manual_offset_ms

    @property
    def effective_latency_s(self) -> float:
        return self.effective_latency_ms / 1000.0

    def update(self, sample_ms: float) -> None:
        self._strategy.update(sample_ms)

    def reset(self) -> None:
        self._strategy.reset()
