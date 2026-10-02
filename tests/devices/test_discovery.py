"""Tests for DiscoveryOrchestrator."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from conftest import FakeLight

from dj_ledfx.config import AppConfig, DiscoveryConfig
from dj_ledfx.devices.backend import DiscoveredDevice
from dj_ledfx.devices.capabilities import DeviceCapabilities
from dj_ledfx.devices.discovery import DiscoveryOrchestrator
from dj_ledfx.devices.manager import DeviceManager
from dj_ledfx.events import DeviceOfflineEvent, DeviceOnlineEvent, EventBus
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.persistence.state_db import StateDB


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def device_manager(event_bus):
    return DeviceManager()


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

    discovered_device = DiscoveredDevice(adapter=real_adapter, tracker=_make_tracker(), max_fps=30)

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


@pytest.mark.asyncio
async def test_devices_that_share_a_name_are_each_managed(config, device_manager, event_bus):
    """The PC's four RAM sticks share one OpenRGB name; each is its own light (spec §6.3, §6.6)."""
    from dj_ledfx.devices.backend import DiscoveredDevice
    from dj_ledfx.events import DeviceDiscoveredEvent
    from dj_ledfx.types import DeviceInfo

    discovered: list[DeviceDiscoveredEvent] = []
    event_bus.subscribe(DeviceDiscoveredEvent, discovered.append)
    ids = [f"openrgb:127.0.0.1:6742:{index}" for index in range(4)]
    sticks = []
    for stable_id in ids:
        adapter = MagicMock()
        adapter.device_info = DeviceInfo(
            name="Corsair Vengeance RGB Pro DDR4",
            device_type="openrgb",
            led_count=10,
            address="127.0.0.1:6742",
            backend="openrgb",
            stable_id=stable_id,
        )
        adapter.led_count = 10
        adapter.is_connected = True
        sticks.append(DiscoveredDevice(adapter=adapter, tracker=_make_tracker(), max_fps=60))

    async def _mock_discover(config, on_found=None, skip_ids=None):
        for stick in sticks:
            on_found(stick)
        return sticks

    mock_backend = MagicMock()
    mock_backend.discover = _mock_discover
    orchestrator = DiscoveryOrchestrator(config, device_manager, event_bus)
    orchestrator._backends = [mock_backend]
    await orchestrator.run_scan()

    assert [d.adapter.device_info.stable_id for d in device_manager.devices] == ids
    assert all(d.status == "online" for d in device_manager.devices)
    assert [event.stable_id for event in discovered] == ids


RAM = "Corsair Vengeance RGB Pro DDR4"


def _found(name: str, stable_id: str):  # type: ignore[no-untyped-def]
    from dj_ledfx.devices.backend import DiscoveredDevice
    from dj_ledfx.types import DeviceInfo

    adapter = MagicMock()
    adapter.device_info = DeviceInfo(
        name=name,
        device_type="openrgb",
        led_count=10,
        address="127.0.0.1:6742",
        backend="openrgb",
        stable_id=stable_id,
    )
    adapter.led_count = 10
    adapter.is_connected = True
    return DiscoveredDevice(adapter=adapter, tracker=_make_tracker(), max_fps=60)


def _ghost(device_manager, name: str, stable_id: str) -> None:  # type: ignore[no-untyped-def]
    from dj_ledfx.types import DeviceInfo

    info = DeviceInfo(
        name=name,
        device_type="openrgb",
        led_count=10,
        address="127.0.0.1:6742",
        backend="openrgb",
        stable_id=stable_id,
    )
    device_manager.add_device_from_info(info, tracker=_make_tracker(), status="offline")


def _backend(found):  # type: ignore[no-untyped-def]
    async def _discover(config, on_found=None, skip_ids=None):  # type: ignore[no-untyped-def]
        for device in found:
            on_found(device)
        return found

    backend = MagicMock()
    backend.discover = _discover
    backend.connect_known = AsyncMock(return_value=found)
    return backend


# B19: a stick whose id changed isn't promoted over a sibling's ghost when two managed
# devices share its name; both siblings keep their ids.
@pytest.mark.parametrize("path", ["scan", "connect_known"])
async def test_a_changed_id_beside_same_named_ghosts_is_a_new_light(
    config, device_manager, event_bus, path
):
    _ghost(device_manager, RAM, "openrgb:ram:0")
    _ghost(device_manager, RAM, "openrgb:ram:1")
    orchestrator = DiscoveryOrchestrator(config, device_manager, event_bus)
    orchestrator._backends = [_backend([_found(RAM, "openrgb:ram:9")])]

    if path == "scan":
        await orchestrator.run_scan()
    else:
        await orchestrator.connect_known_devices([])

    ids = [d.adapter.device_info.stable_id for d in device_manager.devices]
    assert ids == ["openrgb:ram:0", "openrgb:ram:1", "openrgb:ram:9"]
    assert [d.status for d in device_manager.devices] == ["offline", "offline", "online"]


# B19: a light whose id changed takes over the offline ghost of its name when that ghost
# is the only device with the name.
@pytest.mark.parametrize("path", ["scan", "connect_known"])
async def test_a_changed_id_takes_over_the_only_ghost_of_its_name(
    config, device_manager, event_bus, path
):
    from dj_ledfx.events import DeviceOnlineEvent

    online: list[DeviceOnlineEvent] = []
    event_bus.subscribe(DeviceOnlineEvent, online.append)
    _ghost(device_manager, RAM, "openrgb:ram:0")
    orchestrator = DiscoveryOrchestrator(config, device_manager, event_bus)
    found = _found(RAM, "openrgb:ram:9")
    orchestrator._backends = [_backend([found])]

    if path == "scan":
        await orchestrator.run_scan()
    else:
        await orchestrator.connect_known_devices([])

    [managed] = device_manager.devices
    assert managed.adapter is found.adapter and managed.status == "online"
    assert device_manager.get_by_stable_id("openrgb:ram:9") is managed
    assert [event.stable_id for event in online] == ["openrgb:ram:9"]


# B19: an online light of the same name leaves the name fallback alone.
async def test_an_online_namesake_is_not_a_reason_to_promote(config, device_manager, event_bus):
    _ghost(device_manager, RAM, "openrgb:ram:0")
    device_manager.add_device(_found(RAM, "openrgb:ram:1").adapter, _make_tracker())
    orchestrator = DiscoveryOrchestrator(config, device_manager, event_bus)
    orchestrator._backends = [_backend([_found(RAM, "openrgb:ram:9")])]

    await orchestrator.connect_known_devices([])

    ids = [d.adapter.device_info.stable_id for d in device_manager.devices]
    assert ids == ["openrgb:ram:0", "openrgb:ram:1", "openrgb:ram:9"]


LAMP = "govee:test-lamp"
COLOUR = '{"output": {"mode": "colour"}}'


def _lamp(led_count: int = 15) -> FakeLight:
    caps = DeviceCapabilities(protocol="Govee")
    return FakeLight(LAMP, name="Test lamp", led_count=led_count, caps=caps)


async def _known_lamp(db: StateDB, device_manager: DeviceManager) -> FakeLight:
    lamp = _lamp()
    device_manager.add_device(lamp, _make_tracker())
    await db.upsert_device({"id": LAMP, "name": "Test lamp", "backend": "govee", "extra": COLOUR})
    return lamp


# The light-output plan's ruling 17: a lamp whose output changed is set up again at once.
async def test_a_reconnect_sets_a_known_light_up_again_from_its_row(
    config, device_manager, event_bus, db
) -> None:
    online: list[DeviceOnlineEvent] = []
    event_bus.subscribe(DeviceOnlineEvent, online.append)
    await _known_lamp(db, device_manager)
    new = _lamp(led_count=10)
    backend = _backend([DiscoveredDevice(adapter=new, tracker=_make_tracker(), max_fps=10)])
    orchestrator = DiscoveryOrchestrator(config, device_manager, event_bus, state_db=db)
    orchestrator._backends = [backend]

    assert await orchestrator.reconnect(LAMP) is True

    rows, _ = backend.connect_known.await_args.args
    assert [row["extra"] for row in rows] == [COLOUR]
    managed = device_manager.get_by_stable_id(LAMP)
    assert managed is not None and managed.adapter is new
    assert (managed.max_fps, managed.status) == (10, "online")
    assert [event.stable_id for event in online] == [LAMP]
    row = await db.load_device(LAMP)
    assert row is not None and (row["led_count"], row["extra"]) == (10, COLOUR)


async def test_a_light_that_misses_its_reconnect_goes_offline(
    config, device_manager, event_bus, db
) -> None:
    offline: list[DeviceOfflineEvent] = []
    event_bus.subscribe(DeviceOfflineEvent, offline.append)
    lamp = await _known_lamp(db, device_manager)
    orchestrator = DiscoveryOrchestrator(config, device_manager, event_bus, state_db=db)
    orchestrator._backends = [_backend([])]

    assert await orchestrator.reconnect(LAMP) is False

    assert [event.stable_id for event in offline] == [LAMP]  # main demotes it
    managed = device_manager.get_by_stable_id(LAMP)
    assert managed is not None and managed.adapter is lamp


async def test_only_a_known_light_with_a_row_is_reconnected(
    config, device_manager, event_bus, db
) -> None:
    device_manager.add_device(_lamp(), _make_tracker())  # known, but with no row
    backend = _backend([])
    orchestrator = DiscoveryOrchestrator(config, device_manager, event_bus, state_db=db)
    orchestrator._backends = [backend]

    assert await orchestrator.reconnect(LAMP) is False
    assert await orchestrator.reconnect("govee:nobody") is False
    backend.connect_known.assert_not_awaited()


@pytest.mark.asyncio
async def test_scans_take_turns(config, device_manager, event_bus):
    """A scan asked for while one runs waits for it (POST /api/devices/scan beside the loop)."""
    orchestrator = DiscoveryOrchestrator(
        config=config, device_manager=device_manager, event_bus=event_bus
    )
    running = most = 0

    async def discover(*args: object, **kwargs: object) -> None:
        nonlocal running, most
        running += 1
        most = max(most, running)
        await asyncio.sleep(0.01)
        running -= 1

    backend = MagicMock()
    backend.discover = discover
    orchestrator._backends = [backend]

    await asyncio.gather(orchestrator.run_scan(), orchestrator.run_scan())

    assert most == 1
