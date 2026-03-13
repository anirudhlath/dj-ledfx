# src/dj_ledfx/devices/backend.py
from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar

from dj_ledfx.config import AppConfig
from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.latency.tracker import LatencyTracker


@dataclass(frozen=True, slots=True)
class DiscoveredDevice:
    adapter: DeviceAdapter
    tracker: LatencyTracker
    max_fps: int


class DeviceBackend(ABC):
    _registry: ClassVar[list[type[DeviceBackend]]] = []
    _instances: ClassVar[list[DeviceBackend]] = []

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if not inspect.isabstract(cls):
            DeviceBackend._registry.append(cls)

    @abstractmethod
    async def discover(self, config: AppConfig) -> list[DiscoveredDevice]:
        """Discover, connect, and return all devices for this backend.

        Post-condition: all returned adapters are connected (is_connected=True).
        """
        ...

    @abstractmethod
    def is_enabled(self, config: AppConfig) -> bool: ...

    async def shutdown(self) -> None:
        """Clean up backend resources. Default no-op."""
        return

    @classmethod
    async def discover_all(cls, config: AppConfig) -> list[DiscoveredDevice]:
        # Single-call assumption — startup-only code.
        results: list[DiscoveredDevice] = []
        cls._instances = []
        for backend_cls in cls._registry:
            backend = backend_cls()
            cls._instances.append(backend)
            if backend.is_enabled(config):
                results.extend(await backend.discover(config))
        return results

    @classmethod
    async def shutdown_all(cls) -> None:
        for backend in cls._instances:
            await backend.shutdown()
        cls._instances = []
