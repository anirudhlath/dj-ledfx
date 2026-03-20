"""Tests for DiscoveryOrchestrator."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from dj_ledfx.config import AppConfig, DiscoveryConfig
from dj_ledfx.devices.discovery import DiscoveryOrchestrator
from dj_ledfx.devices.manager import DeviceManager
from dj_ledfx.events import EventBus, DiscoveryWaveCompleteEvent, DiscoveryCompleteEvent


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def device_manager(event_bus):
    return DeviceManager(event_bus=event_bus)


@pytest.fixture
def config():
    return AppConfig(discovery=DiscoveryConfig(waves=2, wave_interval_s=0.1))


@pytest.mark.asyncio
async def test_orchestrator_runs_waves(config, device_manager, event_bus):
    """Orchestrator runs configured number of waves."""
    wave_events = []
    event_bus.subscribe(DiscoveryWaveCompleteEvent, wave_events.append)

    complete_events = []
    event_bus.subscribe(DiscoveryCompleteEvent, complete_events.append)

    orchestrator = DiscoveryOrchestrator(
        config=config,
        device_manager=device_manager,
        event_bus=event_bus,
    )
    orchestrator._backends = []

    await orchestrator.run_discovery()

    assert len(wave_events) == 2
    assert wave_events[0].wave == 1
    assert wave_events[1].wave == 2
    assert len(complete_events) == 1


@pytest.mark.asyncio
async def test_orchestrator_single_wave(config, device_manager, event_bus):
    """Single-wave mode."""
    config.discovery.waves = 1
    orchestrator = DiscoveryOrchestrator(
        config=config,
        device_manager=device_manager,
        event_bus=event_bus,
    )
    orchestrator._backends = []

    wave_events = []
    event_bus.subscribe(DiscoveryWaveCompleteEvent, wave_events.append)
    await orchestrator.run_discovery(waves=1)
    assert len(wave_events) == 1


@pytest.mark.asyncio
async def test_orchestrator_complete_event_total(config, device_manager, event_bus):
    """DiscoveryCompleteEvent carries total devices found across all waves."""
    complete_events = []
    event_bus.subscribe(DiscoveryCompleteEvent, complete_events.append)

    orchestrator = DiscoveryOrchestrator(
        config=config,
        device_manager=device_manager,
        event_bus=event_bus,
    )
    orchestrator._backends = []

    await orchestrator.run_discovery()

    assert len(complete_events) == 1
    assert complete_events[0].total_devices == 0


@pytest.mark.asyncio
async def test_orchestrator_wave_interval(config, device_manager, event_bus):
    """Wave interval is respected between waves."""
    import time

    config.discovery.wave_interval_s = 0.05
    config.discovery.waves = 2

    orchestrator = DiscoveryOrchestrator(
        config=config,
        device_manager=device_manager,
        event_bus=event_bus,
    )
    orchestrator._backends = []

    start = time.monotonic()
    await orchestrator.run_discovery()
    elapsed = time.monotonic() - start

    # Should have waited at least the wave_interval_s between waves
    assert elapsed >= 0.05


@pytest.mark.asyncio
async def test_orchestrator_backend_exception_does_not_abort(config, device_manager, event_bus):
    """A backend that raises still allows other waves/backends to complete."""
    wave_events = []
    event_bus.subscribe(DiscoveryWaveCompleteEvent, wave_events.append)

    orchestrator = DiscoveryOrchestrator(
        config=config,
        device_manager=device_manager,
        event_bus=event_bus,
    )

    # Create a failing mock backend
    failing_backend = MagicMock()
    failing_backend.discover = AsyncMock(side_effect=RuntimeError("backend crash"))
    orchestrator._backends = [failing_backend]

    # Should not raise; just logs the error
    result = await orchestrator.run_discovery(waves=1)

    assert len(wave_events) == 1
    assert result == 0


@pytest.mark.asyncio
async def test_orchestrator_shutdown_clears_backends(config, device_manager, event_bus):
    """Shutdown cancels reconnect loop and clears backends."""
    orchestrator = DiscoveryOrchestrator(
        config=config,
        device_manager=device_manager,
        event_bus=event_bus,
    )

    mock_backend = MagicMock()
    mock_backend.shutdown = AsyncMock()
    orchestrator._backends = [mock_backend]

    await orchestrator.shutdown()

    mock_backend.shutdown.assert_awaited_once()
    assert orchestrator._backends == []


@pytest.mark.asyncio
async def test_orchestrator_discovers_new_devices(config, device_manager, event_bus):
    """Devices returned by backend are added to manager and emits DeviceDiscoveredEvent."""
    from dj_ledfx.devices.backend import DiscoveredDevice
    from dj_ledfx.events import DeviceDiscoveredEvent
    from dj_ledfx.types import DeviceInfo

    discovered_events = []
    event_bus.subscribe(DeviceDiscoveredEvent, discovered_events.append)

    # Build a mock DiscoveredDevice
    mock_info = DeviceInfo(
        name="Test LED Strip",
        device_type="govee",
        led_count=60,
        address="192.168.1.100",
        stable_id="govee:aabbccddeeff",
    )
    mock_adapter = MagicMock()
    mock_adapter.device_info = mock_info
    mock_adapter.led_count = 60

    mock_tracker = MagicMock()
    mock_tracker.effective_latency_ms = 100.0

    discovered_device = DiscoveredDevice(
        adapter=mock_adapter, tracker=mock_tracker, max_fps=40
    )

    mock_backend = MagicMock()
    mock_backend.discover = AsyncMock(return_value=[discovered_device])

    orchestrator = DiscoveryOrchestrator(
        config=config,
        device_manager=device_manager,
        event_bus=event_bus,
    )
    orchestrator._backends = [mock_backend]

    total = await orchestrator.run_discovery(waves=1)

    assert total == 1
    assert len(discovered_events) == 1
    assert discovered_events[0].stable_id == "govee:aabbccddeeff"
    assert discovered_events[0].name == "Test LED Strip"
    assert device_manager.get_by_stable_id("govee:aabbccddeeff") is not None
