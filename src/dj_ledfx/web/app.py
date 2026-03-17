"""FastAPI application factory."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

if TYPE_CHECKING:
    from dj_ledfx.beat.clock import BeatClock
    from dj_ledfx.config import AppConfig
    from dj_ledfx.devices.manager import DeviceManager
    from dj_ledfx.effects.deck import EffectDeck
    from dj_ledfx.effects.engine import EffectEngine
    from dj_ledfx.effects.presets import PresetStore
    from dj_ledfx.scheduling.scheduler import LookaheadScheduler


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

    from dj_ledfx.web.router_config import router as config_router
    from dj_ledfx.web.router_devices import router as devices_router
    from dj_ledfx.web.router_effects import router as effects_router

    app.include_router(effects_router, prefix="/api")
    app.include_router(devices_router, prefix="/api")
    app.include_router(config_router, prefix="/api")

    from dj_ledfx.web.ws import ws_endpoint

    app.add_api_websocket_route("/ws", ws_endpoint)

    return app
