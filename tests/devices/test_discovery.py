"""Tests for DiscoveryOrchestrator."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from dj_ledfx.config import AppConfig, DiscoveryConfig
from dj_ledfx.devices.discovery import DiscoveryOrchestrator
from dj_ledfx.devices.manager import DeviceManager
from dj_ledfx.events import EventBus
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def device_manager(event_bus):
    return DeviceManager(event_bus=event_bus)


@pytest.fixture
def config():
    return AppConfig(discovery=DiscoveryConfig(broadcast_interval_s=0.1))


@pytest.mark.asyncio
async def test_orchestrator_run_scan_no_backends(config, device_manager, event_bus):
    """run_scan with no backends returns 0."""
    orchestrator = DiscoveryOrchestrator(
        config=config,
        device_manager=device_manager,
        event_bus=event_bus,
    )
    orchestrator._backends = []

    result = await orchestrator.run_scan()
    assert result == 0


@pytest.mark.asyncio
async def test_orchestrator_backend_exception_does_not_abort(config, device_manager, event_bus):
    """A backend that raises still allows other backends to complete."""
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
    result = await orchestrator.run_scan()
    assert result == 0


@pytest.mark.asyncio
async def test_orchestrator_shutdown_clears_backends(config, device_manager, event_bus):
    """Shutdown cancels discovery loop and clears backends."""
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

    discovered_device = DiscoveredDevice(adapter=mock_adapter, tracker=mock_tracker, max_fps=40)

    mock_backend = MagicMock()

    async def _fake_discover(config, on_found=None, skip_ids=None):
        if callable(on_found):
            on_found(discovered_device)
        return [discovered_device]

    mock_backend.discover = _fake_discover

    orchestrator = DiscoveryOrchestrator(
        config=config,
        device_manager=device_manager,
        event_bus=event_bus,
    )
    orchestrator._backends = [mock_backend]

    total = await orchestrator.run_scan()

    assert total == 1
    assert len(discovered_events) == 1
    assert discovered_events[0].stable_id == "govee:aabbccddeeff"
    assert discovered_events[0].name == "Test LED Strip"
    assert device_manager.get_by_stable_id("govee:aabbccddeeff") is not None


@pytest.mark.asyncio
async def test_orchestrator_continuous_loop_runs(config, device_manager, event_bus):
    """Continuous discovery loop runs and can be stopped."""
    import asyncio

    orchestrator = DiscoveryOrchestrator(
        config=config,
        device_manager=device_manager,
        event_bus=event_bus,
    )
    orchestrator._backends = []

    orchestrator.start()
    assert orchestrator._task is not None

    # Let it run briefly
    await asyncio.sleep(0.05)
    assert orchestrator._running is True

    await orchestrator.shutdown()
    assert orchestrator._running is False


# ---------------------------------------------------------------------------
# New tests: skip_ids, name-based fallback promotion, offline re-promotion
# ---------------------------------------------------------------------------


def _make_tracker() -> LatencyTracker:
    return LatencyTracker(strategy=StaticLatency(5.0))


@pytest.mark.asyncio
async def test_skip_ids_excludes_offline_devices(config, device_manager, event_bus):
    """Offline (ghost) devices should NOT be in skip_ids, allowing re-promotion."""
    from dj_ledfx.types import DeviceInfo

    # Add an online device (real adapter mock)
    online_info = DeviceInfo(
        name="Online",
        device_type="lifx_bulb",
        led_count=10,
        address="192.168.1.1:56700",
        backend="lifx",
        stable_id="lifx:online",
    )
    online_adapter = MagicMock()
    online_adapter.device_info = online_info
    online_adapter.led_count = 10
    online_adapter.is_connected = True
    device_manager.add_device(online_adapter, _make_tracker())

    # Add an offline (ghost) device
    offline_info = DeviceInfo(
        name="Offline",
        device_type="lifx_bulb",
        led_count=10,
        address="192.168.1.2:56700",
        backend="lifx",
        stable_id="lifx:offline",
    )
    device_manager.add_device_from_info(offline_info, tracker=_make_tracker(), status="offline")

    received_skip_ids: set[str] | None = None

    async def _mock_discover(config, on_found=None, skip_ids=None):
        nonlocal received_skip_ids
        received_skip_ids = skip_ids
        return []

    mock_backend = MagicMock()
    mock_backend.discover = _mock_discover
    mock_backend.is_enabled = MagicMock(return_value=True)

    orchestrator = DiscoveryOrchestrator(config, device_manager, event_bus)
    orchestrator._backends = [mock_backend]
    await orchestrator.run_scan()

    assert received_skip_ids is not None
    assert "lifx:online" in received_skip_ids
    assert "lifx:offline" not in received_skip_ids


@pytest.mark.asyncio
async def test_name_fallback_promotes_offline_instead_of_duplicate(
    config, device_manager, event_bus
):
    """Discovering a device with same name as an offline ghost promotes instead of duplicating."""
    from dj_ledfx.devices.backend import DiscoveredDevice
    from dj_ledfx.events import DeviceOnlineEvent
    from dj_ledfx.types import DeviceInfo

    online_events: list[DeviceOnlineEvent] = []
    event_bus.subscribe(DeviceOnlineEvent, online_events.append)

    # Pre-register an offline ghost with stable_id="lifx:old"
    ghost_info = DeviceInfo(
        name="MyStrip",
        device_type="lifx_strip",
        led_count=30,
        address="192.168.1.10:56700",
        backend="lifx",
        stable_id="lifx:old",
    )
    device_manager.add_device_from_info(ghost_info, tracker=_make_tracker(), status="offline")
    assert len(device_manager.devices) == 1

    # Backend discovers same device name but with a NEW stable_id
    new_info = DeviceInfo(
        name="MyStrip",
        device_type="lifx_strip",
        led_count=30,
        address="192.168.1.10:56700",
        backend="lifx",
        stable_id="lifx:new",
    )
    new_adapter = MagicMock()
    new_adapter.device_info = new_info
    new_adapter.led_count = 30
    new_adapter.is_connected = True

    new_tracker = _make_tracker()
    discovered_device = DiscoveredDevice(adapter=new_adapter, tracker=new_tracker, max_fps=40)

    async def _mock_discover(config, on_found=None, skip_ids=None):
        if callable(on_found):
            on_found(discovered_device)
        return [discovered_device]

    mock_backend = MagicMock()
    mock_backend.discover = _mock_discover
    mock_backend.is_enabled = MagicMock(return_value=True)

    orchestrator = DiscoveryOrchestrator(config, device_manager, event_bus)
    orchestrator._backends = [mock_backend]
    await orchestrator.run_scan()

    # Should still be exactly 1 device (promoted, not duplicated)
    assert len(device_manager.devices) == 1
    # The device should now be online
    managed = device_manager.devices[0]
    assert managed.status == "online"
    assert managed.adapter is new_adapter
    # DeviceOnlineEvent should have been emitted
    assert len(online_events) == 1
    assert online_events[0].name == "MyStrip"


@pytest.mark.asyncio
async def test_offline_device_repromotion_via_discovery(config, device_manager, event_bus):
    """A ghost device with matching stable_id gets promoted when rediscovered."""
    from dj_ledfx.devices.backend import DiscoveredDevice
    from dj_ledfx.events import DeviceOnlineEvent
    from dj_ledfx.types import DeviceInfo

    online_events: list[DeviceOnlineEvent] = []
    event_bus.subscribe(DeviceOnlineEvent, online_events.append)

    # Register as offline ghost
    ghost_info = DeviceInfo(
        name="BulbA",
        device_type="lifx_bulb",
        led_count=1,
        address="192.168.1.20:56700",
        backend="lifx",
        stable_id="lifx:bulba",
    )
    device_manager.add_device_from_info(ghost_info, tracker=_make_tracker(), status="offline")
    assert device_manager.get_by_stable_id("lifx:bulba").status == "offline"  # type: ignore[union-attr]

    # Backend discovers the same stable_id again
    real_info = DeviceInfo(
        name="BulbA",
        device_type="lifx_bulb",
        led_count=1,
        address="192.168.1.20:56700",
        backend="lifx",
        stable_id="lifx:bulba",
    )
    real_adapter = MagicMock()
    real_adapter.device_info = real_info
    real_adapter.led_count = 1
    real_adapter.is_connected = True

    discovered_device = DiscoveredDevice(
        adapter=real_adapter, tracker=_make_tracker(), max_fps=30
    )

    async def _mock_discover(config, on_found=None, skip_ids=None):
        if callable(on_found):
            on_found(discovered_device)
        return [discovered_device]

    mock_backend = MagicMock()
    mock_backend.discover = _mock_discover
    mock_backend.is_enabled = MagicMock(return_value=True)

    orchestrator = DiscoveryOrchestrator(config, device_manager, event_bus)
    orchestrator._backends = [mock_backend]
    await orchestrator.run_scan()

    managed = device_manager.get_by_stable_id("lifx:bulba")
    assert managed is not None
    assert managed.status == "online"
    assert managed.adapter is real_adapter
    assert len(online_events) == 1
    assert online_events[0].stable_id == "lifx:bulba"
