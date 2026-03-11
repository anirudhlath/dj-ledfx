import asyncio
from unittest.mock import AsyncMock, PropertyMock

import numpy as np

from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.beat.simulator import BeatSimulator
from dj_ledfx.devices.manager import ManagedDevice
from dj_ledfx.effects.beat_pulse import BeatPulse
from dj_ledfx.effects.engine import EffectEngine
from dj_ledfx.events import EventBus
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.prodjlink.listener import BeatEvent
from dj_ledfx.scheduling.scheduler import LookaheadScheduler
from dj_ledfx.types import DeviceInfo


async def test_full_pipeline_simulator_to_mock_device() -> None:
    """Integration test: BeatSimulator -> BeatClock -> EffectEngine -> Scheduler -> MockDevice."""
    event_bus = EventBus()
    clock = BeatClock()

    def on_beat(event: BeatEvent) -> None:
        clock.on_beat(
            bpm=event.bpm,
            beat_number=event.beat_position,
            next_beat_ms=event.next_beat_ms,
            timestamp=event.timestamp,
        )

    event_bus.subscribe(BeatEvent, on_beat)

    mock_adapter = AsyncMock()
    type(mock_adapter).is_connected = PropertyMock(return_value=True)
    type(mock_adapter).led_count = PropertyMock(return_value=10)
    type(mock_adapter).device_info = PropertyMock(
        return_value=DeviceInfo(
            name="MockLED", device_type="mock", led_count=10, address="mock"
        )
    )

    tracker = LatencyTracker(strategy=StaticLatency(10.0))
    managed = ManagedDevice(adapter=mock_adapter, tracker=tracker)

    effect = BeatPulse()
    engine = EffectEngine(
        clock=clock,
        effect=effect,
        led_count=10,
        fps=60,
        max_lookahead_s=1.0,
    )

    scheduler = LookaheadScheduler(
        ring_buffer=engine.ring_buffer,
        devices=[managed],
        fps=60,
    )

    simulator = BeatSimulator(event_bus=event_bus, bpm=300.0)

    sim_task = asyncio.create_task(simulator.run())
    engine_task = asyncio.create_task(engine.run())
    sched_task = asyncio.create_task(scheduler.run())

    await asyncio.sleep(1.0)

    simulator.stop()
    engine.stop()
    scheduler.stop()
    await asyncio.gather(sim_task, engine_task, sched_task, return_exceptions=True)

    assert mock_adapter.send_frame.call_count > 0

    first_call = mock_adapter.send_frame.call_args_list[0]
    sent_colors = first_call[0][0]
    assert isinstance(sent_colors, np.ndarray)
    assert sent_colors.shape == (10, 3)
