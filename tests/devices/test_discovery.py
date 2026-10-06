"""Tests for DiscoveryOrchestrator."""

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import numpy as np
import pytest
from conftest import events
from govee_fakes import LAMP, STATUS, TEST_MODEL, UPRIGHT, lamp_record, lamp_row, lamp_transport
from loguru import logger
from openrgb_fakes import PC, Listed, orgb_row, serve

from dj_ledfx.config import AppConfig, DiscoveryConfig
from dj_ledfx.devices.discovery import DiscoveryOrchestrator
from dj_ledfx.devices.govee.backend import GoveeBackend
from dj_ledfx.devices.govee.colour import GoveeColourAdapter
from dj_ledfx.devices.govee.output import OUTPUT_KEY, GoveeOutput, LampOutputReport, LampPlan
from dj_ledfx.devices.govee.razer import GoveeRazerAdapter
from dj_ledfx.devices.govee.sku_registry import SKU_REGISTRY
from dj_ledfx.devices.manager import DeviceManager, ManagedDevice
from dj_ledfx.devices.openrgb_backend import OpenRGBBackend
from dj_ledfx.events import DeviceOnlineEvent, EventBus
from dj_ledfx.latency.memory import LinkMemory
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.main import _trackers
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

    async def _fake_discover(config, on_found=None, skip_ids=None, known=()):
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

    async def _mock_discover(config, on_found=None, skip_ids=None, known=()):
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

    async def _mock_discover(config, on_found=None, skip_ids=None, known=()):
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

    async def _mock_discover(config, on_found=None, skip_ids=None, known=()):
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

    async def _mock_discover(config, on_found=None, skip_ids=None, known=()):
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
    async def _discover(config, on_found=None, skip_ids=None, known=()):  # type: ignore[no-untyped-def]
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


COLOUR = GoveeOutput(mode="colour")


@pytest.fixture
def lamp_model(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(SKU_REGISTRY, TEST_MODEL, UPRIGHT)


@pytest.fixture
def lamps(lamp_model, config, device_manager, event_bus, db):  # type: ignore[no-untyped-def]
    """An orchestrator whose one backend is Govee's, over a transport that hears the test
    lamp, and that transport."""
    govee = GoveeBackend()
    transport = govee._transport = lamp_transport()
    orchestrator = DiscoveryOrchestrator(config, device_manager, event_bus, state_db=db)
    orchestrator._backends = [govee]
    return orchestrator, transport


async def _online_lamp(
    orchestrator: DiscoveryOrchestrator, db: StateDB, output: dict[str, Any] | None = None
) -> ManagedDevice:
    """The test lamp, known by its row and set up from it, as a start does."""
    await db.upsert_device(lamp_row(output=output))
    await orchestrator.connect_known_devices(await db.load_devices())
    managed = orchestrator._manager.get_by_stable_id(LAMP)
    assert managed is not None and managed.status == "online"
    return managed


async def _stored(db: StateDB) -> Any:
    row = await db.load_device(LAMP)
    assert row is not None
    return json.loads(row["extra"]) if row["extra"] is not None else None


# The light-output plan's ruling 17: a lamp whose output changed plays it at once.
async def test_an_output_change_plays_at_once_without_asking_the_lamp(lamps, event_bus, db):
    orchestrator, transport = lamps
    managed = await _online_lamp(orchestrator, db)
    old, tracker = managed.adapter, managed.tracker
    online = events(event_bus, DeviceOnlineEvent)
    transport.query_status.reset_mock()

    report = await orchestrator.set_output(LAMP, COLOUR)
    await asyncio.sleep(0)  # the old adapter's disconnect

    assert report == LampOutputReport(LAMP, COLOUR, LampPlan(15, razer=False), online=True)
    assert isinstance(managed.adapter, GoveeColourAdapter) and managed.adapter.is_connected
    assert managed.tracker is tracker  # it keeps the lamp's round trips
    assert old.is_connected is False
    transport.query_status.assert_not_awaited()  # no network
    assert [event.stable_id for event in online] == [LAMP]
    assert await _stored(db) == {"output": {"mode": "colour"}}


async def test_two_quick_output_changes_leave_one_adapter_on_the_newer(
    lamps, device_manager, event_bus, db
):
    orchestrator, _ = lamps
    await _online_lamp(orchestrator, db)
    adapters: list[Any] = []

    def _swapped(event: DeviceOnlineEvent) -> None:
        adapters.append(device_manager.get_by_stable_id(event.stable_id).adapter)

    event_bus.subscribe(DeviceOnlineEvent, _swapped)

    await asyncio.gather(
        orchestrator.set_output(LAMP, GoveeOutput(segments=10)),
        orchestrator.set_output(LAMP, GoveeOutput(segments=12)),
    )
    await asyncio.sleep(0)

    [managed] = device_manager.devices
    assert managed.adapter is adapters[-1]
    assert [adapter.led_count for adapter in adapters] == [10, 12]
    assert [adapter.is_connected for adapter in adapters] == [False, True]
    assert await _stored(db) == {"output": {"segments": 12}}


async def test_an_output_change_waits_for_a_scan(lamps, device_manager, db):
    """A scan sets a lamp up from the rows it read when it began, so an output change made
    meanwhile waits for it: the lamp ends on the newer output."""
    orchestrator, transport = lamps
    await db.upsert_device(lamp_row())  # known, and offline
    held = asyncio.Event()

    async def discover(timeout_s: float = 10.0, on_record: Any = None) -> None:
        await held.wait()
        on_record(lamp_record())

    transport.discover = discover
    scan = asyncio.create_task(orchestrator.run_scan())
    await asyncio.sleep(0.01)
    change = asyncio.create_task(orchestrator.set_output(LAMP, COLOUR))
    await asyncio.sleep(0.01)
    assert not change.done() and await _stored(db) is None
    held.set()

    assert await scan == 1
    report = await change
    managed = device_manager.get_by_stable_id(LAMP)
    assert managed is not None and isinstance(managed.adapter, GoveeColourAdapter)
    assert report is not None and (report.plays, report.online) == (LampPlan(15, False), True)


async def test_a_duplicate_a_scan_sets_up_never_takes_the_live_tracker(
    lamps, config, device_manager, db
):
    """A scan that began while the lamp was offline sets it up a second time; the light's
    round trips still go to the tracker of the lamp that's online."""
    orchestrator, transport = lamps
    managed = await _online_lamp(orchestrator, db)
    [govee] = orchestrator._backends

    await govee.discover(config, on_found=orchestrator._merge)

    [registered] = transport.register_device.call_args_list
    record, rtt = registered.args
    assert record == lamp_record() and rtt.__self__ is managed.tracker
    assert len(device_manager.devices) == 1


async def _remembering(config, device_manager, event_bus, db, row=None):  # type: ignore[no-untyped-def]
    """An orchestrator over the Govee backend, as `lamps` gives, whose link memory holds the
    test lamp's row (latency_ms, dozing) when one is given."""
    if row is not None:
        await db.write(
            "INSERT INTO link_memory (stable_id, latency_ms, dozing, updated_at) "
            "VALUES (?, ?, ?, '2026-10-06T00:00:00+00:00')",
            (LAMP, *row),
        )
    memory = LinkMemory(db)
    await memory.load()
    govee = GoveeBackend()
    govee._transport = lamp_transport()
    orchestrator = DiscoveryOrchestrator(
        config, device_manager, event_bus, state_db=db, link_memory=memory
    )
    orchestrator._backends = [govee]
    return orchestrator


# The light-sync spec's §7: a light taken in starts from the latency and mode it last had,
# whether it's new to this run or an offline light found again.
@pytest.mark.parametrize("offline", [False, True], ids=["new", "offline"])
async def test_a_lamp_taken_in_starts_from_the_latency_and_mode_it_last_had(
    lamp_model, config, device_manager, event_bus, db, offline
):
    if offline:
        _ghost(device_manager, "Test lamp", LAMP)
    orchestrator = await _remembering(config, device_manager, event_bus, db, (250.0, 1))

    managed = await _online_lamp(orchestrator, db)

    assert (managed.tracker.link_latency_ms, managed.tracker.dozing) == (250.0, True)
    assert not managed.tracker.measured  # estimated until it streams


async def test_a_lamp_with_no_row_starts_at_the_config_s_seed_awake(
    lamp_model, config, device_manager, event_bus, db
):
    orchestrator = await _remembering(config, device_manager, event_bus, db)
    managed = await _online_lamp(orchestrator, db)
    seed = config.devices.govee.latency_ms
    assert (managed.tracker.link_latency_ms, managed.tracker.dozing) == (seed, False)


async def test_an_output_change_keeps_the_latency_the_lamp_has_now(
    lamp_model, config, device_manager, event_bus, db
):
    """The lamp is set up again with its own tracker: its row isn't read again."""
    orchestrator = await _remembering(config, device_manager, event_bus, db, (250.0, 1))
    managed = await _online_lamp(orchestrator, db)
    managed.tracker.recall(180.0, dozing=False)  # what it measured since

    await orchestrator.set_output(LAMP, COLOUR)

    assert (managed.tracker.link_latency_ms, managed.tracker.dozing) == (180.0, False)


# The light-sync spec's §7, "within a run": a lamp that drops out and is found again starts
# from what its tracker measured, which is newer than its row (written at most every 30 s).
async def test_a_lamp_found_again_starts_from_what_it_measured_not_its_older_row(
    lamp_model, config, device_manager, event_bus, db
):
    orchestrator = await _remembering(config, device_manager, event_bus, db, (250.0, 1))
    managed = await _online_lamp(orchestrator, db)
    old = managed.tracker
    old.recall(120.0, dozing=False)
    old.note_send()
    old.update_rtt(240.0)  # measured while it streams, awake: half its round trip
    assert old.measured and old.link_latency_ms == 120.0
    device_manager.demote_device(LAMP)  # it dropped out
    await asyncio.sleep(0)  # the old adapter's disconnect
    records: list[Any] = []
    sink = logger.add(lambda message: records.append(message.record), level="INFO")
    try:
        await orchestrator.run_scan()  # and a scan finds it again
    finally:
        logger.remove(sink)

    assert managed.status == "online" and managed.tracker is not old
    assert (managed.tracker.link_latency_ms, managed.tracker.dozing) == (120.0, False)
    assert not managed.tracker.measured  # estimated until it streams again
    recalls = [(r["level"].name, r["message"]) for r in records if "last had" in r["message"]]
    line = f"{managed.tracker.name} starts from the latency it last had: 120 ms, awake"
    assert recalls == [("INFO", line)]  # the line a recall from its row logs


# main's writer keys each light's row by the id the orchestrator recalls it by, so the row
# it saves is the one the next start reads.
async def test_the_row_main_s_writer_saves_is_the_one_the_next_start_recalls(
    lamp_model, config, device_manager, event_bus, db
):
    orchestrator = await _remembering(config, device_manager, event_bus, db)
    managed = await _online_lamp(orchestrator, db)
    managed.tracker.recall(250.0, dozing=True)
    managed.tracker.note_send()
    managed.tracker.update_rtt(250.0)  # measured while it streams, dozing: its whole round trip

    assert await LinkMemory(db).save(_trackers(device_manager)) == 1

    devices = DeviceManager()  # the next start, as main has it: the lamp a ghost of its row
    _ghost(devices, "Test lamp", LAMP)
    restarted = await _remembering(config, devices, EventBus(), db)
    lamp = await _online_lamp(restarted, db)

    assert (lamp.tracker.link_latency_ms, lamp.tracker.dozing) == (250.0, True)
    assert not lamp.tracker.measured


async def test_only_a_known_govee_lamp_takes_an_output(config, device_manager, event_bus, db):
    orchestrator = DiscoveryOrchestrator(config, device_manager, event_bus, state_db=db)
    await db.upsert_device({"id": "lifx:test", "name": "Test bulb", "backend": "lifx"})

    assert await orchestrator.set_output("lifx:test", COLOUR) is None
    assert await orchestrator.set_output("govee:nobody", COLOUR) is None
    assert await orchestrator.output_of("lifx:test") is None
    row = await db.load_device("lifx:test")
    assert row is not None and row["extra"] is None


async def test_an_offline_lamp_takes_its_output_when_a_scan_finds_it(lamps, device_manager, db):
    orchestrator, transport = lamps
    await db.upsert_device(lamp_row())
    transport.query_status.return_value = None  # silent at the start
    await orchestrator.connect_known_devices(await db.load_devices())

    report = await orchestrator.set_output(LAMP, COLOUR)
    transport.query_status.return_value = STATUS  # it's back
    await orchestrator.run_scan()

    assert report == LampOutputReport(LAMP, COLOUR, LampPlan(15, razer=False), online=False)
    managed = device_manager.get_by_stable_id(LAMP)
    assert managed is not None and isinstance(managed.adapter, GoveeColourAdapter)


async def test_a_deleted_lamp_found_again_plays_as_its_model_says(lamps, device_manager, db):
    orchestrator, _ = lamps
    managed = await _online_lamp(orchestrator, db, output={"mode": "colour"})
    assert isinstance(managed.adapter, GoveeColourAdapter)
    device_manager.remove_device(LAMP)  # as DELETE /api/devices/{name} does
    await db.delete_device(LAMP)

    await orchestrator.run_scan()

    found = device_manager.get_by_stable_id(LAMP)
    assert found is not None and isinstance(found.adapter, GoveeRazerAdapter)
    assert found.adapter.led_count == 15


async def test_a_lamp_no_backend_can_set_up_again_plays_as_it_did(lamps, db):
    orchestrator, _ = lamps
    managed = await _online_lamp(orchestrator, db)
    old = managed.adapter
    orchestrator._backends = []

    report = await orchestrator.set_output(LAMP, COLOUR)

    assert managed.adapter is old
    assert report == LampOutputReport(LAMP, COLOUR, LampPlan(15, razer=True), online=True)


async def test_outputs_changed_under_the_lamps_apply_at_once(lamps, event_bus, db):
    """As a restored backup changes them: a lamp is set up again only when its row says
    otherwise than it plays."""
    orchestrator, _ = lamps
    managed = await _online_lamp(orchestrator, db)
    online = events(event_bus, DeviceOnlineEvent)

    await orchestrator.apply_outputs()
    assert online == []  # nothing changed
    await db.set_device_extra(LAMP, OUTPUT_KEY, COLOUR.to_extra())
    await orchestrator.apply_outputs()

    assert isinstance(managed.adapter, GoveeColourAdapter)
    assert [event.stable_id for event in online] == [LAMP]


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


async def test_a_device_s_row_keeps_what_it_is_so_the_next_start_finds_it_wherever_it_sits(
    monkeypatch: pytest.MonkeyPatch, config, event_bus, db
):
    """Four sticks of one name, known from rows that keep only their names: the first start
    keeps each stick's location in its row, and the next start finds each stick by it."""
    sticks = [Listed("RAM", location=f"bus-0 slot-{n}") for n in range(4)]
    server = serve(monkeypatch, *sticks)
    for n in range(4):
        await db.upsert_device(orgb_row(n, "RAM"))

    first = DiscoveryOrchestrator(config, DeviceManager(), event_bus, state_db=db)
    first._backends = [OpenRGBBackend()]
    await first.connect_known_devices(await db.load_devices())
    await first.shutdown()

    stored = json.loads((await db.load_device(f"{PC}:2"))["extra"])
    assert stored == {"identity": {"serial": "", "location": "bus-0 slot-2"}}

    server.devices = [sticks[3], sticks[1], sticks[0], sticks[2]]  # listed in another order
    manager = DeviceManager()
    restart = DiscoveryOrchestrator(config, manager, event_bus, state_db=db)
    restart._backends = [OpenRGBBackend()]
    await restart.connect_known_devices(await db.load_devices())

    for n, stick in enumerate(sticks):
        managed = manager.get_by_stable_id(f"{PC}:{n}")
        assert managed is not None
        await managed.adapter.send_frame(np.full((2, 3), n + 1, dtype=np.uint8))
        assert stick.frames == [[(n + 1, n + 1, n + 1)] * 2]
