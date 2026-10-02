from __future__ import annotations

import math
import statistics
from collections import deque
from typing import Protocol

# Three samples in a row outside the spread are a new level, not three outliers.
OUTLIERS_TO_SHIFT = 3
STRATEGIES = ("static", "ema", "windowed_mean", "windowed_median")


class ProbeStrategy(Protocol):
    def update(self, new_sample: float) -> None: ...
    def get_latency(self) -> float: ...
    def reset(self) -> None: ...


class StaticLatency:
    def __init__(self, latency_ms: float = 10.0) -> None:
        self._latency = latency_ms

    def update(self, new_sample: float) -> None:
        pass

    def get_latency(self) -> float:
        return self._latency

    def reset(self) -> None:
        pass


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
        if not self._initialized:
            return self._initial_value_ms
        return self._value

    def reset(self) -> None:
        self._value = self._initial_value_ms
        self._initialized = False
        self._samples.clear()
        self._outliers = 0


class WindowedMeanLatency:
    def __init__(self, window_size: int = 10, initial_value_ms: float = 0.0) -> None:
        self._window: deque[float] = deque(maxlen=window_size)
        self._initial_value_ms = initial_value_ms

    def update(self, new_sample: float) -> None:
        self._window.append(new_sample)

    def get_latency(self) -> float:
        if not self._window:
            return self._initial_value_ms
        return sum(self._window) / len(self._window)

    def reset(self) -> None:
        self._window.clear()


class WindowedMedianLatency:
    """The median of the last window_size samples: a lone spike doesn't move it, and a
    level that holds for more than half the window moves it all the way."""

    def __init__(self, window_size: int = 9, initial_value_ms: float = 0.0) -> None:
        self._window: deque[float] = deque(maxlen=window_size)
        self._initial_value_ms = initial_value_ms

    def update(self, new_sample: float) -> None:
        self._window.append(new_sample)

    def get_latency(self) -> float:
        if not self._window:
            return self._initial_value_ms
        return float(statistics.median(self._window))

    def reset(self) -> None:
        self._window.clear()


def make_strategy(name: str, latency_ms: float, window_size: int) -> ProbeStrategy:
    """The strategy a config names, seeded at latency_ms (a static one keeps it)."""
    if name == "static":
        return StaticLatency(latency_ms)
    if name == "ema":
        return EMALatency(initial_value_ms=latency_ms)
    if name == "windowed_mean":
        return WindowedMeanLatency(window_size=window_size, initial_value_ms=latency_ms)
    if name == "windowed_median":
        return WindowedMedianLatency(window_size=window_size, initial_value_ms=latency_ms)
    raise ValueError(f"Unknown latency strategy '{name}': one of {', '.join(STRATEGIES)}")
