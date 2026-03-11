import asyncio

from dj_ledfx.beat.simulator import BeatSimulator
from dj_ledfx.events import EventBus
from dj_ledfx.prodjlink.listener import BeatEvent


async def test_simulator_emits_beats() -> None:
    bus = EventBus()
    events: list[BeatEvent] = []
    bus.subscribe(BeatEvent, events.append)

    sim = BeatSimulator(event_bus=bus, bpm=300.0)
    task = asyncio.create_task(sim.run())

    await asyncio.sleep(0.5)
    sim.stop()
    await task

    assert len(events) >= 2
    assert all(e.bpm == 300.0 for e in events)


async def test_simulator_cycles_beat_positions() -> None:
    bus = EventBus()
    events: list[BeatEvent] = []
    bus.subscribe(BeatEvent, events.append)

    sim = BeatSimulator(event_bus=bus, bpm=600.0)
    task = asyncio.create_task(sim.run())

    await asyncio.sleep(0.5)
    sim.stop()
    await task

    positions = [e.beat_position for e in events]
    assert positions[0] == 1
    if len(positions) >= 4:
        assert positions[3] == 4
    if len(positions) >= 5:
        assert positions[4] == 1


async def test_simulator_stop() -> None:
    bus = EventBus()
    sim = BeatSimulator(event_bus=bus, bpm=120.0)
    task = asyncio.create_task(sim.run())
    await asyncio.sleep(0.01)  # let task start
    sim.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
