# tests/devices/test_backend.py
from __future__ import annotations

import pytest

from dj_ledfx.config import AppConfig
from dj_ledfx.devices.backend import DeviceBackend, DiscoveredDevice


@pytest.fixture(autouse=True)
def _isolate_registry() -> None:
    """Save and restore DeviceBackend._registry around each test."""
    saved_registry = DeviceBackend._registry.copy()
    yield  # type: ignore[misc]
    DeviceBackend._registry = saved_registry


class FakeBackendA(DeviceBackend):
    async def discover(self, config: AppConfig) -> list[DiscoveredDevice]:
        return []

    def is_enabled(self, config: AppConfig) -> bool:
        return True


class FakeBackendB(DeviceBackend):
    async def discover(self, config: AppConfig) -> list[DiscoveredDevice]:
        return []

    def is_enabled(self, config: AppConfig) -> bool:
        return False


def test_subclass_auto_registers() -> None:
    assert FakeBackendA in DeviceBackend._registry
    assert FakeBackendB in DeviceBackend._registry


def test_discovered_device_dataclass() -> None:
    from unittest.mock import MagicMock

    dd = DiscoveredDevice(
        adapter=MagicMock(),
        tracker=MagicMock(),
        max_fps=30,
    )
    assert dd.max_fps == 30
