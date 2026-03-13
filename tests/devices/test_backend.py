# tests/devices/test_backend.py
from __future__ import annotations

import pytest

from dj_ledfx.config import AppConfig
from dj_ledfx.devices.backend import DeviceBackend, DiscoveredDevice


@pytest.fixture(autouse=True)
def _isolate_registry() -> None:
    """Save and restore DeviceBackend._registry and _instances around each test."""
    saved_registry = DeviceBackend._registry.copy()
    saved_instances = DeviceBackend._instances.copy()
    yield  # type: ignore[misc]
    DeviceBackend._registry = saved_registry
    DeviceBackend._instances = saved_instances


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


@pytest.mark.asyncio
async def test_discover_all_skips_disabled() -> None:
    # Reset to only our test backends
    DeviceBackend._registry = [FakeBackendA, FakeBackendB]
    config = AppConfig()
    devices = await DeviceBackend.discover_all(config)
    assert devices == []
    assert len(DeviceBackend._instances) == 2


@pytest.mark.asyncio
async def test_shutdown_all_calls_shutdown() -> None:
    shutdown_called = False

    class ShutdownTracker(DeviceBackend):
        async def discover(self, config: AppConfig) -> list[DiscoveredDevice]:
            return []

        def is_enabled(self, config: AppConfig) -> bool:
            return True

        async def shutdown(self) -> None:
            nonlocal shutdown_called
            shutdown_called = True

    DeviceBackend._registry = [ShutdownTracker]
    config = AppConfig()
    await DeviceBackend.discover_all(config)
    await DeviceBackend.shutdown_all()
    assert shutdown_called


def test_discovered_device_dataclass() -> None:
    from unittest.mock import MagicMock

    dd = DiscoveredDevice(
        adapter=MagicMock(),
        tracker=MagicMock(),
        max_fps=30,
    )
    assert dd.max_fps == 30
