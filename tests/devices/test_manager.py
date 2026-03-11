from unittest.mock import AsyncMock, PropertyMock

from dj_ledfx.devices.manager import DeviceManager
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
    manager.add_device(adapter, tracker)  # type: ignore[arg-type]
    assert len(manager.devices) == 1


def test_device_manager_max_led_count() -> None:
    bus = EventBus()
    manager = DeviceManager(event_bus=bus)

    a1 = _make_mock_adapter("Dev1", led_count=10)
    a2 = _make_mock_adapter("Dev2", led_count=30)
    t1 = LatencyTracker(strategy=StaticLatency(10.0))
    t2 = LatencyTracker(strategy=StaticLatency(10.0))

    manager.add_device(a1, t1)  # type: ignore[arg-type]
    manager.add_device(a2, t2)  # type: ignore[arg-type]

    assert manager.max_led_count == 30
