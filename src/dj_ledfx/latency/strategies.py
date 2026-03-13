from __future__ import annotations

import math
from collections import deque
from typing import Protocol


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

    def update(self, new_sample: float) -> None:
        if len(self._samples) >= 5:
            mean = sum(self._samples) / len(self._samples)
            variance = sum((s - mean) ** 2 for s in self._samples) / len(self._samples)
            std = math.sqrt(variance) if variance > 0 else 0.0
            # When std is 0 (all samples identical), use 10% of mean as threshold
            threshold = 2.0 * std if std > 0 else mean * 0.1
            if threshold > 0 and abs(new_sample - mean) > threshold:
                return

        self._samples.append(new_sample)
        if len(self._samples) > 100:
            self._samples.pop(0)

        if not self._initialized:
            self._value = new_sample
            self._initialized = True
        else:
            self._value = self._alpha * new_sample + (1.0 - self._alpha) * self._value

    def get_latency(self) -> float:
        if not self._initialized:
            return self._initial_value_ms
        return self._value

    def reset(self) -> None:
        self._value = self._initial_value_ms
        self._initialized = False
        self._samples.clear()


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
