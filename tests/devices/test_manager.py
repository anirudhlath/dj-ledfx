import pytest
from unittest.mock import AsyncMock, MagicMock, PropertyMock

from dj_ledfx.devices.manager import DeviceManager, ManagedDevice
from dj_ledfx.events import EventBus
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.types import DeviceInfo


def _make_mock_adapter(name: str = "TestDevice", led_count: int = 10) -> AsyncMock:
    adapter = AsyncMock()
    type(adapter).is_connected = PropertyMock(return_value=True)
    type(adapter).led_count = PropertyMock(return_value=led_count)
    type(adapter).device_info = PropertyMock(
        return_value=DeviceInfo(name=name, device_type="mock", led_count=led_count, address="mock")
    )
    return adapter


def test_device_manager_add_device() -> None:
    bus = EventBus()
    manager = DeviceManager(event_bus=bus)
    adapter = _make_mock_adapter()
    tracker = LatencyTracker(strategy=StaticLatency(10.0))
    manager.add_device(adapter, tracker, max_fps=60)  # type: ignore[arg-type]
    assert len(manager.devices) == 1


def test_device_manager_max_led_count() -> None:
    bus = EventBus()
    manager = DeviceManager(event_bus=bus)

    a1 = _make_mock_adapter("Dev1", led_count=10)
    a2 = _make_mock_adapter("Dev2", led_count=30)
    t1 = LatencyTracker(strategy=StaticLatency(10.0))
    t2 = LatencyTracker(strategy=StaticLatency(10.0))

    manager.add_device(a1, t1, max_fps=60)  # type: ignore[arg-type]
    manager.add_device(a2, t2, max_fps=60)  # type: ignore[arg-type]

    assert manager.max_led_count == 30


def test_managed_device_max_fps() -> None:
    """ManagedDevice stores max_fps."""
    md = ManagedDevice(adapter=MagicMock(), tracker=MagicMock(), max_fps=30)
    assert md.max_fps == 30


def test_device_manager_get_device_by_name() -> None:
    bus = EventBus()
    manager = DeviceManager(event_bus=bus)
    adapter = _make_mock_adapter("MyDevice")
    tracker = LatencyTracker(strategy=StaticLatency(10.0))
    manager.add_device(adapter, tracker, max_fps=60)  # type: ignore[arg-type]

    result = manager.get_device("MyDevice")
    assert result is not None
    assert result.adapter.device_info.name == "MyDevice"

    missing = manager.get_device("NoSuchDevice")
    assert missing is None


def test_device_manager_groups() -> None:
    bus = EventBus()
    manager = DeviceManager(event_bus=bus)

    group = manager.create_group("DJ Booth", "#00e5ff")
    assert group.name == "DJ Booth"
    assert group.color == "#00e5ff"

    groups = manager.get_groups()
    assert "DJ Booth" in groups

    manager.delete_group("DJ Booth")
    assert "DJ Booth" not in manager.get_groups()


def test_device_manager_assign_group() -> None:
    bus = EventBus()
    manager = DeviceManager(event_bus=bus)

    adapter = _make_mock_adapter("Dev1")
    tracker = LatencyTracker(strategy=StaticLatency(10.0))
    manager.add_device(adapter, tracker, max_fps=60)  # type: ignore[arg-type]

    manager.create_group("Stage", "#ff0000")
    manager.assign_to_group("Dev1", "Stage")

    assert manager.get_device_group("Dev1") == "Stage"
    assert manager.get_device_group("Dev2") is None


def test_device_manager_assign_group_missing_group() -> None:
    bus = EventBus()
    manager = DeviceManager(event_bus=bus)

    with pytest.raises(KeyError, match="Group not found"):
        manager.assign_to_group("Dev1", "NonExistent")


def test_device_manager_delete_group_clears_assignments() -> None:
    bus = EventBus()
    manager = DeviceManager(event_bus=bus)

    adapter = _make_mock_adapter("Dev1")
    tracker = LatencyTracker(strategy=StaticLatency(10.0))
    manager.add_device(adapter, tracker, max_fps=60)  # type: ignore[arg-type]

    manager.create_group("Stage", "#ff0000")
    manager.assign_to_group("Dev1", "Stage")
    assert manager.get_device_group("Dev1") == "Stage"

    manager.delete_group("Stage")
    assert manager.get_device_group("Dev1") is None
