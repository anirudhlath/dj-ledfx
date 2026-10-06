from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections import deque
from collections.abc import Callable, Sequence
from typing import Protocol

# How many recent samples a windowed latency strategy keeps: a median of nine ignores up to
# four spikes and follows a level that holds for five.
LATENCY_WINDOW = 9
# Three samples in a row outside the spread are a new level, not three outliers.
OUTLIERS_TO_SHIFT = 3


class ProbeStrategy(Protocol):
    def update(self, new_sample: float) -> None: ...
    def get_latency(self) -> float: ...
    # Forget the samples and start again from latency_ms, or from the seed without one.
    def reset(self, latency_ms: float | None = None) -> None: ...


class StaticLatency:
    def __init__(self, latency_ms: float = 10.0) -> None:
        self._latency = latency_ms

    def update(self, new_sample: float) -> None:
        pass

    def get_latency(self) -> float:
        return self._latency

    def reset(self, latency_ms: float | None = None) -> None:
        pass  # it keeps the configured latency


class EMALatency:
    def __init__(self, alpha: float = 0.3, initial_value_ms: float = 0.0) -> None:
        self._alpha = alpha
        self._initial_value_ms = initial_value_ms
        self._value: float = initial_value_ms
        self._initialized = False
        self._samples: list[float] = []
        self._outliers = 0  # in a row

    def update(self, new_sample: float) -> None:
        if self._is_outlier(new_sample):
            self._outliers += 1
            if self._outliers < OUTLIERS_TO_SHIFT:
                return
            # The latency moved and stayed there: start again from the new level.
            self._samples.clear()
            self._initialized = False
        self._outliers = 0
        self._samples.append(new_sample)
        if len(self._samples) > 100:
            self._samples.pop(0)

        if not self._initialized:
            self._value = new_sample
            self._initialized = True
        else:
            self._value = self._alpha * new_sample + (1.0 - self._alpha) * self._value

    def _is_outlier(self, sample: float) -> bool:
        if len(self._samples) < 5:
            return False
        mean = sum(self._samples) / len(self._samples)
        variance = sum((s - mean) ** 2 for s in self._samples) / len(self._samples)
        std = math.sqrt(variance) if variance > 0 else 0.0
        # When std is 0 (all samples identical), use 10% of mean as threshold
        threshold = 2.0 * std if std > 0 else mean * 0.1
        return threshold > 0 and abs(sample - mean) > threshold

    def get_latency(self) -> float:
        return self._value  # before its first sample, the value it starts from

    def reset(self, latency_ms: float | None = None) -> None:
        self._value = self._initial_value_ms if latency_ms is None else latency_ms
        self._initialized = False
        self._samples.clear()
        self._outliers = 0


class WindowedLatency(ABC):
    """One statistic of the last window_size samples, worked out when a sample lands: the
    latency is read every frame, and a sample lands every few seconds at most."""

    def __init__(self, window_size: int, initial_value_ms: float = 0.0) -> None:
        self._window: deque[float] = deque(maxlen=window_size)
        self._initial_value_ms = initial_value_ms
        self._latency = initial_value_ms

    @staticmethod
    @abstractmethod
    def _statistic(samples: Sequence[float]) -> float:
        """The latency the samples give (never empty)."""

    def update(self, new_sample: float) -> None:
        self._window.append(new_sample)
        self._latency = self._statistic(self._window)

    def get_latency(self) -> float:
        return self._latency

    def reset(self, latency_ms: float | None = None) -> None:
        self._window.clear()
        self._latency = self._initial_value_ms if latency_ms is None else latency_ms


class WindowedMeanLatency(WindowedLatency):
    @staticmethod
    def _statistic(samples: Sequence[float]) -> float:
        return sum(samples) / len(samples)


class WindowedMedianLatency(WindowedLatency):
    """The median of the last window_size samples: a lone spike doesn't move it, and a
    level that holds for more than half the window moves it all the way."""

    @staticmethod
    def _statistic(samples: Sequence[float]) -> float:
        ordered = sorted(samples)
        middle = len(ordered) // 2
        if len(ordered) % 2:
            return ordered[middle]
        return (ordered[middle - 1] + ordered[middle]) / 2.0


# Each strategy a config can name, made from its seed (latency_ms) and its window size.
STRATEGIES: dict[str, Callable[[float, int], ProbeStrategy]] = {
    "static": lambda latency_ms, _window: StaticLatency(latency_ms),
    "ema": lambda latency_ms, _window: EMALatency(initial_value_ms=latency_ms),
    "windowed_mean": lambda latency_ms, window: WindowedMeanLatency(window, latency_ms),
    "windowed_median": lambda latency_ms, window: WindowedMedianLatency(window, latency_ms),
}


def make_strategy(name: str, latency_ms: float, window_size: int) -> ProbeStrategy:
    """The strategy a config names, seeded at latency_ms (a static one keeps it)."""
    factory = STRATEGIES.get(name)
    if factory is None:
        raise ValueError(f"Unknown latency strategy '{name}': one of {', '.join(STRATEGIES)}")
    return factory(latency_ms, window_size)
