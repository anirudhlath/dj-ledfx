# src/dj_ledfx/devices/backend.py
from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, ClassVar

from dj_ledfx.config import AppConfig
from dj_ledfx.devices.adapter import DeviceAdapter
from dj_ledfx.latency.tracker import LatencyTracker


def configured_fps(config: AppConfig, max_fps: int) -> int:
    """The rate a backend builds its adapters with: its kind's max_fps, within the engine's
    rate (a light is never sent more frames than the engine renders)."""
    return min(config.engine.fps, max_fps)


@dataclass(frozen=True, slots=True)
class DiscoveredDevice:
    adapter: DeviceAdapter
    tracker: LatencyTracker
    max_fps: float | None  # the adapter's stream_fps; None: the scheduler's rate
    # Hands the tracker the light's round trips. The orchestrator calls it once it takes the
    # device in, so a duplicate it turns away never takes them from the live tracker.
    on_accepted: Callable[[], None] | None = None

    def accepted(self) -> None:
        if self.on_accepted is not None:
            self.on_accepted()


class DeviceBackend(ABC):
    _registry: ClassVar[list[type[DeviceBackend]]] = []

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if not inspect.isabstract(cls):
            DeviceBackend._registry.append(cls)

    @abstractmethod
    async def discover(
        self,
        config: AppConfig,
        on_found: Callable[[DiscoveredDevice], Any] | None = None,
        skip_ids: set[str] | None = None,
        known: Sequence[Mapping[str, Any]] = (),
    ) -> list[DiscoveredDevice]:
        """Discover, connect, and return all devices for this backend.

        If *on_found* is provided it is called synchronously for each device
        as soon as it is ready (before the full scan timeout elapses).  The
        full list is still returned at the end for logging / counting.

        If *skip_ids* is provided, devices whose stable_id is in the set
        should be silently skipped (already managed by the orchestrator).

        *known* holds the known devices' rows, for a setting a light keeps in its row (a
        Govee lamp's own output).

        Post-condition: all returned adapters are connected (is_connected=True).
        """
        ...

    @abstractmethod
    def is_enabled(self, config: AppConfig) -> bool: ...

    async def connect_known(
        self, device_rows: list[dict[str, Any]], config: AppConfig
    ) -> list[DiscoveredDevice]:
        """Directly connect to known devices from DB without network scanning.

        Override per backend to enable fast reconnect on startup.
        Default implementation returns an empty list.
        """
        return []

    def rebuild(
        self, row: Mapping[str, Any], config: AppConfig, tracker: LatencyTracker
    ) -> DiscoveredDevice | None:
        """Set an online light up again from its row, with no network and keeping its
        tracker, so that a setting kept in the row takes effect (a Govee lamp's own output).
        None: the light isn't this backend's, or it can't. Default: None."""
        return None

    async def shutdown(self) -> None:
        """Clean up backend resources. Default no-op."""
        return
