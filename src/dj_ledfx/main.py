from __future__ import annotations

import argparse
import asyncio
import dataclasses
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
    load_config,
)
from dj_ledfx.devices.discovery import DiscoveryOrchestrator
from dj_ledfx.devices.manager import DeviceManager
from dj_ledfx.effects.beat_pulse import BeatPulse
from dj_ledfx.effects.deck import EffectDeck
from dj_ledfx.effects.engine import EffectEngine
from dj_ledfx.events import EventBus
from dj_ledfx.latency.strategies import StaticLatency
from dj_ledfx.latency.tracker import LatencyTracker
from dj_ledfx.persistence.state_db import StateDB
from dj_ledfx.prodjlink.listener import BeatEvent, start_listener
from dj_ledfx.scheduling.scheduler import LookaheadScheduler
from dj_ledfx.spatial.compositor import SpatialCompositor
from dj_ledfx.spatial.mapping import mapping_from_config
from dj_ledfx.spatial.scene import SceneModel
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

    # Load each config section from DB
    engine_data = await state_db.load_config("engine")
    effect_data = await state_db.load_config("effect")
    network_data = await state_db.load_config("network")
    web_data = await state_db.load_config("web")
    discovery_data = await state_db.load_config("discovery")

    def _coerce(raw: dict[str, str]) -> dict[str, object]:
        """Try to parse each string value as JSON (handles int, float, bool)."""
        import json

        result: dict[str, object] = {}
        for k, v in raw.items():
            try:
                result[k] = json.loads(v)
            except (json.JSONDecodeError, ValueError):
                result[k] = v
        return result

    def _filter(cls: type, data: dict[str, object]) -> dict[str, object]:
        valid = {f.name for f in dataclasses.fields(cls)}  # type: ignore[arg-type]
        return {k: v for k, v in data.items() if k in valid}

    engine = EngineConfig(**_filter(EngineConfig, _coerce(engine_data)))  # type: ignore[arg-type]
    network = NetworkConfig(**_filter(NetworkConfig, _coerce(network_data)))  # type: ignore[arg-type]
    web = WebConfig(**_filter(WebConfig, _coerce(web_data)))  # type: ignore[arg-type]
    discovery = DiscoveryConfig(**_filter(DiscoveryConfig, _coerce(discovery_data)))  # type: ignore[arg-type]

    # Effect config: keep active_effect only (params come from scene_effect_state)
    effect_coerced = _coerce(effect_data)
    effect = EffectConfig(**_filter(EffectConfig, effect_coerced))  # type: ignore[arg-type]

    logger.info("Config loaded from StateDB")
    return AppConfig(
        engine=engine,
        effect=effect,
        network=network,
        web=web,
        discovery=discovery,
    )


async def _save_config_to_db(config: AppConfig, state_db: StateDB) -> None:
    """Persist AppConfig to StateDB config table.

    Intended for use by the config router when config is updated at runtime.
    """
    import json

    def _str_dict(obj: object) -> dict[str, str]:
        return {k: json.dumps(v) for k, v in dataclasses.asdict(obj).items()}  # type: ignore[call-overload]

    await state_db.save_config_bulk("engine", _str_dict(config.engine))
    await state_db.save_config_bulk("network", _str_dict(config.network))
    await state_db.save_config_bulk("web", _str_dict(config.web))
    await state_db.save_config_bulk("discovery", _str_dict(config.discovery))

    effect_plain = {
        k: v
        for k, v in dataclasses.asdict(config.effect).items()
        if not isinstance(v, (dict, list))
    }
    await state_db.save_config_bulk("effect", {k: json.dumps(v) for k, v in effect_plain.items()})

    logger.debug("Config saved to StateDB")


async def _run(args: argparse.Namespace) -> None:
    metrics.init(enabled=args.metrics, port=args.metrics_port)

    # --- Step 1: Open StateDB ---
    db_path = args.db if args.db else args.config.parent / "state.db"
    state_db = StateDB(db_path)
    await state_db.open()

    # --- Step 2: TOML migration (if DB is fresh and TOML files exist) ---
    presets_toml = args.config.parent / "presets.toml"
    if await state_db.is_config_empty():
        if args.config.exists() or presets_toml.exists():
            logger.info("Fresh DB detected — running TOML migration")
            await state_db.migrate_from_toml(
                config_path=args.config if args.config.exists() else None,
                presets_path=presets_toml if presets_toml.exists() else None,
            )

    # --- Step 3: Load config (DB first, then TOML fallback) ---
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

    # --- Step 4: Load registered devices from DB → GhostAdapter entries ---
    device_manager = DeviceManager(event_bus=event_bus)
    registered_devices = await state_db.load_devices()
    for dev_row in registered_devices:
        dev_info = DeviceInfo(
            name=dev_row["name"],
            device_type=dev_row.get("backend") or "",
            led_count=dev_row.get("led_count") or 0,
            address=dev_row.get("ip") or "",
            mac=dev_row.get("mac"),
            stable_id=dev_row["id"],
        )
        led_count = dev_row.get("led_count") or 60
        last_latency = dev_row.get("last_latency_ms") or 50.0
        tracker = LatencyTracker(strategy=StaticLatency(last_latency))
        device_manager.add_device_from_info(
            device_info=dev_info,
            led_count=led_count,
            tracker=tracker,
            status="offline",
        )
    if registered_devices:
        logger.info("Loaded {} registered device(s) from DB", len(registered_devices))

    # --- Step 5: Build spatial scene if configured ---
    scene: SceneModel | None = None
    compositor: SpatialCompositor | None = None
    if config.scene_config is not None:
        adapters = [d.adapter for d in device_manager.devices]
        scene = SceneModel.from_config(config.scene_config, adapters)
        if scene.placements:
            mapping = mapping_from_config(config.scene_config)
            compositor = SpatialCompositor(scene, mapping)
            logger.info(
                "Spatial compositor active: {} mapping, {} devices",
                config.scene_config.get("mapping", "linear"),
                len(scene.placements),
            )

    led_count = device_manager.max_led_count or 60
    logger.info("Using {} LEDs", led_count)

    effect = BeatPulse(
        palette=config.effect.beat_pulse_palette,
        gamma=config.effect.beat_pulse_gamma,
    )
    deck = EffectDeck(effect)

    # --- Step 6: Start engine and scheduler ---
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

    # --- Step 7: Build DiscoveryOrchestrator ---
    discovery_orchestrator = DiscoveryOrchestrator(
        config=config,
        device_manager=device_manager,
        event_bus=event_bus,
        state_db=state_db,
    )

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
            effect_deck=deck,
            effect_engine=engine,
            device_manager=device_manager,
            scheduler=scheduler,
            preset_store=preset_store,
            scene_model=scene,
            compositor=compositor,
            config=config,
            config_path=args.config,
            web_static_dir=None if web_mode == "dev" else args.web_static_dir,
            state_db=state_db,
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

    # --- Step 8: Launch background discovery + reconnect loop ---
    tasks.append(asyncio.create_task(discovery_orchestrator.run_discovery()))
    await discovery_orchestrator.start_reconnect_loop()

    async def _status_loop() -> None:
        while not stop_event.is_set():
            beat_state = clock.get_state()
            status = SystemStatus(
                prodjlink_connected=beat_state.is_playing,
                current_bpm=beat_state.bpm or None,
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
