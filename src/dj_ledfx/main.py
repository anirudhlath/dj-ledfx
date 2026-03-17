from __future__ import annotations

import argparse
import asyncio
import signal
import sys
import time
from pathlib import Path

from loguru import logger

import dj_ledfx.devices  # noqa: F401  # triggers backend auto-registration
from dj_ledfx import metrics
from dj_ledfx.beat.clock import BeatClock
from dj_ledfx.beat.simulator import BeatSimulator
from dj_ledfx.config import load_config
from dj_ledfx.devices.backend import DeviceBackend
from dj_ledfx.devices.manager import DeviceManager
from dj_ledfx.effects.beat_pulse import BeatPulse
from dj_ledfx.effects.deck import EffectDeck
from dj_ledfx.effects.engine import EffectEngine
from dj_ledfx.events import EventBus
from dj_ledfx.prodjlink.listener import BeatEvent, start_listener
from dj_ledfx.scheduling.scheduler import LookaheadScheduler
from dj_ledfx.spatial.compositor import SpatialCompositor
from dj_ledfx.spatial.mapping import LinearMapping, RadialMapping
from dj_ledfx.spatial.scene import SceneModel
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
    parser.add_argument(
        "--profile",
        nargs="?",
        const="sampling",
        default=None,
        choices=["sampling", "deep"],
        help="Enable profiling: 'sampling' (default, py-spy) or 'deep' (VizTracer)",
    )
    parser.add_argument(
        "--metrics", action="store_true", help="Enable Prometheus metrics endpoint"
    )
    parser.add_argument(
        "--metrics-port",
        type=int,
        default=9091,
        help="Prometheus metrics port (default: 9091)",
    )
    return parser.parse_args()


async def _run(args: argparse.Namespace) -> None:
    config = load_config(args.config)
    metrics.init(enabled=args.metrics, port=args.metrics_port)

    event_bus = EventBus()
    clock = BeatClock()

    def on_beat(event: BeatEvent) -> None:
        metrics.BEATS_RECEIVED.inc()
        clock.on_beat(
            bpm=event.bpm,
            beat_number=event.beat_position,
            next_beat_ms=event.next_beat_ms,
            timestamp=event.timestamp,
            pitch_percent=event.pitch_percent,
            device_number=event.device_number,
            device_name=event.device_name,
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

    devices = await DeviceBackend.discover_all(config)
    for device in devices:
        device_manager.add_device(device.adapter, device.tracker, device.max_fps)

    # Build spatial scene if configured
    compositor: SpatialCompositor | None = None
    if config.scene_config is not None:
        adapters = [d.adapter for d in device_manager.devices]
        scene = SceneModel.from_config(config.scene_config, adapters)
        if scene.placements:
            mapping_name = config.scene_config.get("mapping", "linear")
            mapping_params = config.scene_config.get("mapping_params", {})
            mapping: LinearMapping | RadialMapping
            if mapping_name == "radial":
                center = mapping_params.get("center", [0.0, 0.0, 0.0])
                max_radius = mapping_params.get("max_radius")
                mapping = RadialMapping(
                    center=(float(center[0]), float(center[1]), float(center[2])),
                    max_radius=float(max_radius) if max_radius is not None else None,
                )
            else:
                direction = mapping_params.get("direction", [1.0, 0.0, 0.0])
                origin = mapping_params.get("origin")
                origin_tuple = (
                    (float(origin[0]), float(origin[1]), float(origin[2])) if origin else None
                )
                mapping = LinearMapping(
                    direction=(float(direction[0]), float(direction[1]), float(direction[2])),
                    origin=origin_tuple,
                )
            compositor = SpatialCompositor(scene, mapping)
            logger.info(
                "Spatial compositor active: {} mapping, {} devices",
                mapping_name,
                len(scene.placements),
            )

    led_count = device_manager.max_led_count or 60
    logger.info("Using {} LEDs", led_count)

    effect = BeatPulse(
        palette=config.effect.beat_pulse_palette,
        gamma=config.effect.beat_pulse_gamma,
    )
    deck = EffectDeck(effect)

    engine = EffectEngine(
        clock=clock,
        deck=deck,
        led_count=led_count,
        fps=config.engine.fps,
        max_lookahead_s=config.engine.max_lookahead_ms / 1000.0,
    )

    scheduler = LookaheadScheduler(
        ring_buffer=engine.ring_buffer,
        devices=device_manager.devices,
        fps=config.engine.fps,
        compositor=compositor,
    )

    stop_event = asyncio.Event()

    async def _event_loop_lag_loop() -> None:
        interval = 0.1
        while not stop_event.is_set():
            t0 = time.monotonic()
            await asyncio.sleep(interval)
            lag = time.monotonic() - t0 - interval
            metrics.EVENT_LOOP_LAG.observe(max(0.0, lag))

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
            metrics.RING_BUFFER_DEPTH.set(engine.ring_buffer.fill_level)
            summary = status.summary()
            await asyncio.to_thread(logger.info, "Status: {}", summary)
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=10.0)
            except TimeoutError:
                pass

    tasks.append(asyncio.create_task(_status_loop()))
    if args.metrics:
        tasks.append(asyncio.create_task(_event_loop_lag_loop()))

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
    await DeviceBackend.shutdown_all()
    logger.info("dj-ledfx stopped")


def main() -> None:
    args = _parse_args()

    logger.remove()
    logger.add(sys.stderr, level=args.log_level)

    if args.profile == "deep":
        from datetime import datetime

        try:
            from viztracer import VizTracer
        except ImportError:
            logger.error("VizTracer not installed. Install with: uv pip install viztracer")
            sys.exit(1)

        profiles_dir = Path("profiles")
        profiles_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_path = profiles_dir / f"profile-{timestamp}.json"

        tracer = VizTracer(
            tracer_entries=1_000_000,
            include_files=["*/dj_ledfx/*"],
            min_duration=50,
            log_async=True,
        )
        tracer.start()
        try:
            asyncio.run(_run(args))
        except KeyboardInterrupt:
            pass
        finally:
            tracer.stop()
            tracer.save(str(output_path))
            logger.info("VizTracer profile saved to {}", output_path)
            print(f"\nProfile saved to: {output_path}")
            print("Open at: https://ui.perfetto.dev/ (load local file)")
    else:
        try:
            asyncio.run(_run(args))
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
