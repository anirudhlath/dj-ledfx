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
from dj_ledfx.config import (
    AppConfig,
    DiscoveryConfig,
    EffectConfig,
    EngineConfig,
    NetworkConfig,
    WebConfig,
    filter_fields,
    load_config,
)
from dj_ledfx.devices.discovery import DiscoveryOrchestrator
from dj_ledfx.devices.manager import DeviceManager
from dj_ledfx.effects.beat_pulse import BeatPulse
from dj_ledfx.effects.deck import EffectDeck
from dj_ledfx.effects.engine import EffectEngine
from dj_ledfx.events import DeviceDiscoveredEvent, DeviceOfflineEvent, DeviceOnlineEvent, EventBus
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.persistence.state_db import StateDB
from dj_ledfx.persistence.toml_io import migrate_from_toml
from dj_ledfx.prodjlink.listener import BeatEvent, start_listener
from dj_ledfx.scheduling.scheduler import LookaheadScheduler
from dj_ledfx.spatial.pipeline_manager import PipelineManager
from dj_ledfx.status import SystemStatus
from dj_ledfx.types import DeviceInfo


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="dj-ledfx: Beat-synced LED effects")
    parser.add_argument("--demo", action="store_true", help="Run with simulated beats")
    parser.add_argument(
        "--config", type=Path, default=Path("config.toml"), help="Config file path"
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="SQLite state database path (default: <config-dir>/state.db)",
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
    parser.add_argument(
        "--web",
        nargs="?",
        const="prod",
        default=None,
        choices=["prod", "dev"],
        help="Enable web UI ('--web' for production, '--web dev' for hot-reload dev server)",
    )
    parser.add_argument("--web-port", type=int, default=None, help="Web UI port")
    parser.add_argument("--web-host", type=str, default=None, help="Web UI host")
    parser.add_argument(
        "--web-static-dir", type=str, default=None, help="Web UI static files directory"
    )
    return parser.parse_args()


async def _load_config_from_db(state_db: StateDB) -> AppConfig | None:
    """Build AppConfig from StateDB config table.

    Returns None if the config table is empty (fresh DB with no migrated config).
    """
    if await state_db.is_config_empty():
        return None

    all_config = await state_db.load_all_config()

    # Group by section
    sections: dict[str, dict[str, object]] = {}
    for (section, key), value in all_config.items():
        sections.setdefault(section, {})[key] = value

    engine = EngineConfig(**filter_fields(EngineConfig, sections.get("engine", {})))
    network = NetworkConfig(**filter_fields(NetworkConfig, sections.get("network", {})))
    web = WebConfig(**filter_fields(WebConfig, sections.get("web", {})))
    discovery = DiscoveryConfig(**filter_fields(DiscoveryConfig, sections.get("discovery", {})))
    effect = EffectConfig(**filter_fields(EffectConfig, sections.get("effect", {})))

    logger.info("Config loaded from StateDB")
    return AppConfig(
        engine=engine,
        effect=effect,
        network=network,
        web=web,
        discovery=discovery,
    )


async def _run(args: argparse.Namespace) -> None:
    metrics.init(enabled=args.metrics, port=args.metrics_port)

    db_path = args.db if args.db else args.config.parent / "state.db"
    state_db = StateDB(db_path)
    await state_db.open()

    presets_toml = args.config.parent / "presets.toml"
    if await state_db.is_config_empty():
        if args.config.exists() or presets_toml.exists():
            logger.info("Fresh DB detected — running TOML migration")
            await migrate_from_toml(
                state_db,
                config_path=args.config if args.config.exists() else None,
                presets_path=presets_toml if presets_toml.exists() else None,
            )

    config = await _load_config_from_db(state_db)
    if config is None:
        logger.info("No config in DB — loading from TOML ({})", args.config)
        config = load_config(args.config)

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
    device_manager.set_state_db(state_db)
    registered_devices = await state_db.load_devices()
    for dev_row in registered_devices:
        led_count = dev_row.get("led_count") or 60
        dev_info = DeviceInfo(
            name=dev_row["name"],
            device_type=dev_row.get("backend") or "",
            led_count=led_count,
            address=dev_row.get("ip") or "",
            mac=dev_row.get("mac"),
            stable_id=dev_row["id"],
        )
        last_latency = dev_row.get("last_latency_ms") or 50.0
        tracker = LatencyTracker(strategy=StaticLatency(last_latency))
        device_manager.add_device_from_info(
            device_info=dev_info,
            tracker=tracker,
            status="offline",
        )
    if registered_devices:
        logger.info("Loaded {} registered device(s) from DB", len(registered_devices))

    discovery_orchestrator = DiscoveryOrchestrator(
        config=config,
        device_manager=device_manager,
        event_bus=event_bus,
        state_db=state_db,
    )

    if registered_devices:
        await discovery_orchestrator.connect_known_devices(registered_devices)

    pipeline_manager = PipelineManager(
        device_manager=device_manager,
        state_db=state_db,
        event_bus=event_bus,
        config=config,
    )
    await pipeline_manager.load_active_scenes()

    default_deck = pipeline_manager.default_deck or EffectDeck(BeatPulse())
    default_pipeline = pipeline_manager.default_pipeline
    led_count = device_manager.max_led_count or 60
    logger.info("Using {} LEDs", led_count)

    engine = EffectEngine(
        clock=clock,
        deck=default_deck,
        led_count=led_count,
        fps=config.engine.fps,
        max_lookahead_s=config.engine.max_lookahead_ms / 1000.0,
        pipelines=pipeline_manager.all_pipelines if pipeline_manager.all_pipelines else None,
        event_bus=event_bus,
    )

    default_ring_buffer = default_pipeline.ring_buffer if default_pipeline else engine.ring_buffer
    default_compositor = default_pipeline.compositor if default_pipeline else None

    scheduler = LookaheadScheduler(
        ring_buffer=default_ring_buffer,
        devices=[],
        fps=config.engine.fps,
        compositor=default_compositor,
        event_bus=event_bus,
        state_db=state_db,
    )

    pipeline_manager.bind(engine, scheduler)

    for pipeline in pipeline_manager.all_pipelines:
        for managed in pipeline.devices:
            scheduler.add_device(managed, pipeline=pipeline)

    def _on_device_offline(event: DeviceOfflineEvent) -> None:
        if event.stable_id:
            try:
                device_manager.demote_device(event.stable_id)
            except KeyError:
                logger.debug(
                    "demote_device: stable_id '{}' not found (already removed?)",
                    event.stable_id,
                )
        scheduler.remove_device(event.stable_id)

    event_bus.subscribe(DeviceOfflineEvent, _on_device_offline)

    def _on_device_discovered(event: DeviceDiscoveredEvent) -> None:
        managed = device_manager.get_by_stable_id(event.stable_id)
        if managed is not None:
            pipeline_manager.reassign_devices()

    event_bus.subscribe(DeviceDiscoveredEvent, _on_device_discovered)

    def _on_device_online(event: DeviceOnlineEvent) -> None:
        managed = device_manager.get_by_stable_id(event.stable_id)
        if managed is not None:
            pipeline_manager.reassign_devices()

    event_bus.subscribe(DeviceOnlineEvent, _on_device_online)

    # Web setup
    async def _forward_vite_output(proc: asyncio.subprocess.Process) -> None:
        assert proc.stdout is not None
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            logger.info("[vite] {}", line.decode().rstrip())

    stop_event = asyncio.Event()
    web_server_task: asyncio.Task[None] | None = None
    vite_process: asyncio.subprocess.Process | None = None
    web_mode = args.web or ("prod" if config.web.enabled else None)

    if web_mode:
        from dj_ledfx.effects.presets import PresetStore
        from dj_ledfx.web.app import create_app

        host = args.web_host or config.web.host
        port = args.web_port or config.web.port

        # Use DB-backed PresetStore if StateDB is available
        preset_store = PresetStore(state_db=state_db)
        await preset_store.load_from_db()

        web_app = create_app(
            beat_clock=clock,
            effect_deck=default_deck,
            effect_engine=engine,
            device_manager=device_manager,
            scheduler=scheduler,
            preset_store=preset_store,
            scene_model=None,
            compositor=default_compositor,
            config=config,
            config_path=args.config,
            web_static_dir=None if web_mode == "dev" else args.web_static_dir,
            state_db=state_db,
            event_bus=event_bus,
            pipeline_manager=pipeline_manager,
        )

        try:
            from granian.constants import Interfaces
            from granian.server.embed import Server as GranianServer

            granian_server = GranianServer(
                target=web_app,
                address=host,
                port=port,
                interface=Interfaces.ASGI,
                websockets=True,
            )
            web_server_task = asyncio.create_task(granian_server.serve())
        except (ImportError, Exception) as e:
            logger.warning("Granian unavailable ({}), falling back to uvicorn", e)
            import uvicorn  # type: ignore[import-not-found]

            uvi_config = uvicorn.Config(web_app, host=host, port=port, loop="none")
            uvi_server = uvicorn.Server(uvi_config)
            web_server_task = asyncio.create_task(uvi_server.serve())

        logger.info("API server on http://{}:{}", host, port)

        if web_mode == "dev":
            frontend_dir = Path(__file__).parent.parent.parent / "frontend"
            if not (frontend_dir / "package.json").exists():
                logger.error("frontend/ directory not found at {}", frontend_dir)
            else:
                vite_process = await asyncio.create_subprocess_exec(
                    "npx",
                    "vite",
                    "dev",
                    cwd=str(frontend_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.STDOUT,
                )
                asyncio.create_task(_forward_vite_output(vite_process))
                logger.info("Dev UI (hot reload) at http://localhost:5173")
        else:
            logger.info("Web UI available at http://{}:{}", host, port)

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

    discovery_orchestrator.start()

    async def _status_loop() -> None:
        while not stop_event.is_set():
            beat_state = clock.get_state()
            status = SystemStatus(
                prodjlink_connected=beat_state.is_playing,
                current_bpm=beat_state.bpm or None,
                connected_devices=[d.adapter.device_info.name for d in device_manager.devices],
                buffer_fill_level=default_ring_buffer.fill_level,
                avg_frame_render_time_ms=engine.avg_render_time_ms,
                device_stats=scheduler.get_device_stats(),
            )
            metrics.RING_BUFFER_DEPTH.set(default_ring_buffer.fill_level)
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

    if vite_process is not None:
        vite_process.terminate()
        await vite_process.wait()

    if web_server_task is not None:
        web_server_task.cancel()
        await asyncio.gather(web_server_task, return_exceptions=True)

    scheduler.stop()
    engine.stop()
    if simulator is not None:
        simulator.stop()

    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)

    await discovery_orchestrator.shutdown()
    await device_manager.disconnect_all()
    await state_db.close()
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
