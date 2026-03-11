from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import Any

from loguru import logger


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[type, list[Callable[..., Any]]] = defaultdict(list)

    def subscribe(self, event_type: type, callback: Callable[..., Any]) -> None:
        self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: type, callback: Callable[..., Any]) -> None:
        try:
            self._subscribers[event_type].remove(callback)
        except ValueError:
            pass

    def emit(self, event: object) -> None:
        for callback in self._subscribers.get(type(event), []):
            try:
                callback(event)
            except Exception:
                logger.exception("Event callback failed for {}", type(event).__name__)
