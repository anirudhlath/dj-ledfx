"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import importlib.resources
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI, HTTPException
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse
from starlette.staticfiles import StaticFiles

if TYPE_CHECKING:
    from dj_ledfx.beat.clock import BeatClock
    from dj_ledfx.config import AppConfig
    from dj_ledfx.devices.manager import DeviceManager
    from dj_ledfx.effects.deck import EffectDeck
    from dj_ledfx.effects.engine import EffectEngine
    from dj_ledfx.effects.presets import PresetStore
    from dj_ledfx.events import EventBus
    from dj_ledfx.persistence.state_db import StateDB
    from dj_ledfx.scheduling.scheduler import LookaheadScheduler


def _resolve_static_dir(explicit: str | None, config_dir: str | None) -> Path | None:
    """4-tier static directory resolution."""
    for candidate in [
        Path(explicit) if explicit else None,
        Path(config_dir) if config_dir else None,
        Path(__file__).parent.parent.parent.parent / "frontend" / "dist",
    ]:
        if candidate and candidate.is_dir():
            return candidate
    try:
        pkg_path = importlib.resources.files("dj_ledfx") / "web" / "static"
        resolved = Path(str(pkg_path))
        if resolved.is_dir():
            return resolved
    except (TypeError, FileNotFoundError):
        pass
    return None


def create_app(
    *,
    beat_clock: BeatClock,
    effect_deck: EffectDeck,
    effect_engine: EffectEngine,
    device_manager: DeviceManager,
    scheduler: LookaheadScheduler,
    preset_store: PresetStore,
    scene_model: object | None,
    compositor: object | None,
    config: AppConfig,
    config_path: Path | None,
    web_static_dir: str | None = None,
    state_db: StateDB | None = None,
    event_bus: EventBus | None = None,
) -> FastAPI:
    app = FastAPI(title="dj-ledfx")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.web.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store references for routers
    app.state.beat_clock = beat_clock
    app.state.effect_deck = effect_deck
    app.state.effect_engine = effect_engine
    app.state.device_manager = device_manager
    app.state.scheduler = scheduler
    app.state.preset_store = preset_store
    app.state.scene_model = scene_model
    app.state.compositor = compositor
    app.state.config = config
    app.state.config_path = config_path
    app.state.state_db = state_db
    app.state.event_bus = event_bus
    app.state.connected_websockets: set = set()

    @app.on_event("startup")
    async def _start_transport_broadcast() -> None:
        if app.state.event_bus is not None:
            from dj_ledfx.web.ws import transport_broadcast

            app.state._transport_broadcast_task = asyncio.create_task(
                transport_broadcast(app)
            )

    @app.on_event("shutdown")
    async def _stop_transport_broadcast() -> None:
        task = getattr(app.state, "_transport_broadcast_task", None)
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    from dj_ledfx.web.router_config import router as config_router
    from dj_ledfx.web.router_devices import router as devices_router
    from dj_ledfx.web.router_effects import router as effects_router
    from dj_ledfx.web.router_scene import router as scene_router
    from dj_ledfx.web.router_scene import router_scenes
    from dj_ledfx.web.router_transport import router as transport_router

    app.include_router(effects_router, prefix="/api")
    app.include_router(devices_router, prefix="/api")
    app.include_router(config_router, prefix="/api")
    app.include_router(scene_router, prefix="/api")
    app.include_router(router_scenes, prefix="/api")
    app.include_router(transport_router, prefix="/api")

    from dj_ledfx.web.ws import ws_endpoint

    app.add_api_websocket_route("/ws", ws_endpoint)

    static_dir = _resolve_static_dir(web_static_dir, config.web.static_dir)
    if static_dir and static_dir.is_dir():
        index_html = static_dir / "index.html"

        # Mount assets directory for hashed static files
        assets_dir = static_dir / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str) -> FileResponse:
            """Serve index.html for all non-API routes (SPA client-side routing)."""
            if full_path.startswith("api/"):
                raise HTTPException(status_code=404, detail="Not found")
            file_path = static_dir / full_path
            if full_path and file_path.is_file():
                return FileResponse(str(file_path))
            return FileResponse(str(index_html))

    return app
