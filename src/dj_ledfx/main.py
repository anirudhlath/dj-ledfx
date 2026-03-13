from __future__ import annotations

import argparse
import asyncio
import signal
import sys
from pathlib import Path

from loguru import logger

from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.beat.simulator import BeatSimulator
from dj_ledfx.config import load_config
from dj_ledfx.devices.heuristics import estimate_device_latency_ms
from dj_ledfx.devices.manager import DeviceManager
from dj_ledfx.devices.openrgb import OpenRGBAdapter
from dj_ledfx.effects.beat_pulse import BeatPulse
from dj_ledfx.effects.engine import EffectEngine
from dj_ledfx.events import EventBus
from dj_ledfx.latency.strategies import EMALatency, StaticLatency, WindowedMeanLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.prodjlink.listener import BeatEvent, start_listener
from dj_ledfx.scheduling.scheduler import LookaheadScheduler
from dj_ledfx.status import SystemStatus


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="dj-ledfx: Beat-synced LED effects")
    parser.add_argument("--demo", action="store_true", help="Run with simulated beats")
    parser.add_argument(
        "--config", type=Path, default=Path("config.toml"), help="Config file path"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["TRACE", "DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level",
    )
    parser.add_argument("--bpm", type=float, default=128.0, help="Demo mode BPM")
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> None:
    config = load_config(args.config)

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

    simulator: BeatSimulator | None = None
    if args.demo:
        logger.info("Starting in demo mode at {:.1f} BPM", args.bpm)
        simulator = BeatSimulator(event_bus=event_bus, bpm=args.bpm)
    else:
        logger.info("Starting Pro DJ Link listener")
        await start_listener(event_bus=event_bus)

    device_manager = DeviceManager(event_bus=event_bus)

    if config.openrgb_enabled:
        discovered = await OpenRGBAdapter.discover(
            host=config.openrgb_host, port=config.openrgb_port
        )
        logger.info("Discovered {} OpenRGB devices", len(discovered))
        for i in range(len(discovered)):
            try:
                adapter = OpenRGBAdapter(
                    host=config.openrgb_host,
                    port=config.openrgb_port,
                    device_index=i,
                )
                await adapter.connect()
                heuristic_ms = estimate_device_latency_ms(adapter.device_info.name)

                strategy: StaticLatency | EMALatency | WindowedMeanLatency
                if config.openrgb_latency_strategy == "static":
                    strategy = StaticLatency(config.openrgb_latency_ms)
                elif config.openrgb_latency_strategy == "ema":
                    strategy = EMALatency(initial_value_ms=heuristic_ms)
                else:  # "windowed_mean"
                    strategy = WindowedMeanLatency(
                        window_size=config.openrgb_latency_window_size,
                        initial_value_ms=heuristic_ms,
                    )

                tracker = LatencyTracker(
                    strategy=strategy,
                    manual_offset_ms=config.openrgb_manual_offset_ms,
                )
                device_manager.add_device(adapter, tracker)
            except Exception:
                logger.exception("Failed to connect to OpenRGB device {}", i)

    led_count = device_manager.max_led_count or 60
    logger.info("Using {} LEDs", led_count)

    effect = BeatPulse(
        palette=config.beat_pulse_palette,
        gamma=config.beat_pulse_gamma,
    )

    engine = EffectEngine(
        clock=clock,
        effect=effect,
        led_count=led_count,
        fps=config.engine_fps,
        max_lookahead_s=config.max_lookahead_ms / 1000.0,
    )

    scheduler = LookaheadScheduler(
        ring_buffer=engine.ring_buffer,
        devices=device_manager.devices,
        fps=config.engine_fps,
        max_fps=config.openrgb_max_fps,
    )

    stop_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    tasks: list[asyncio.Task[None]] = []
    if simulator is not None:
        tasks.append(asyncio.create_task(simulator.run()))
    tasks.append(asyncio.create_task(engine.run()))
    tasks.append(asyncio.create_task(scheduler.run()))

    async def _status_loop() -> None:
        while not stop_event.is_set():
            status = SystemStatus(
                prodjlink_connected=clock.get_state().is_playing,
                current_bpm=clock.get_state().bpm or None,
                connected_devices=[d.adapter.device_info.name for d in device_manager.devices],
                buffer_fill_level=engine.ring_buffer.fill_level,
                avg_frame_render_time_ms=engine.avg_render_time_ms,
                device_stats=scheduler.get_device_stats(),
            )
            logger.info("Status: {}", status.summary())
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=10.0)
            except TimeoutError:
                pass

    tasks.append(asyncio.create_task(_status_loop()))

    logger.info("dj-ledfx started")
    await stop_event.wait()

    logger.info("Shutting down...")
    scheduler.stop()
    engine.stop()
    if simulator is not None:
        simulator.stop()

    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

    await device_manager.disconnect_all()
    logger.info("dj-ledfx stopped")


def main() -> None:
    args = _parse_args()

    logger.remove()
    logger.add(sys.stderr, level=args.log_level)

    try:
        asyncio.run(_run(args))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
