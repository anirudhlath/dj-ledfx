"""Configuration REST endpoints."""

from __future__ import annotations

import asyncio
import dataclasses
import tomllib
from typing import Any

import tomli_w
from fastapi import APIRouter, HTTPException, Request
from starlette.responses import JSONResponse, PlainTextResponse

from dj_ledfx.config import (
    AppConfig,
    DevicesConfig,
    EffectConfig,
    EngineConfig,
    GoveeConfig,
    LIFXConfig,
    NetworkConfig,
    OpenRGBConfig,
    WebConfig,
    save_config,
    strip_none,
)

router = APIRouter()


def _merge_config(existing: AppConfig, updates: dict[str, Any]) -> AppConfig:
    """Recursively merge partial updates into config, reconstructing dataclasses."""
    kwargs: dict[str, Any] = {}

    if "engine" in updates:
        merged = {**dataclasses.asdict(existing.engine), **updates["engine"]}
        kwargs["engine"] = EngineConfig(**merged)

    if "effect" in updates:
        merged = {**dataclasses.asdict(existing.effect), **updates["effect"]}
        kwargs["effect"] = EffectConfig(**merged)

    if "network" in updates:
        merged = {**dataclasses.asdict(existing.network), **updates["network"]}
        kwargs["network"] = NetworkConfig(**merged)

    if "web" in updates:
        merged = {**dataclasses.asdict(existing.web), **updates["web"]}
        kwargs["web"] = WebConfig(**merged)

    if "devices" in updates:
        dev_updates = updates["devices"]
        dev_kwargs: dict[str, Any] = {}
        if "openrgb" in dev_updates:
            merged = {**dataclasses.asdict(existing.devices.openrgb), **dev_updates["openrgb"]}
            dev_kwargs["openrgb"] = OpenRGBConfig(**merged)
        if "lifx" in dev_updates:
            merged = {**dataclasses.asdict(existing.devices.lifx), **dev_updates["lifx"]}
            dev_kwargs["lifx"] = LIFXConfig(**merged)
        if "govee" in dev_updates:
            merged = {**dataclasses.asdict(existing.devices.govee), **dev_updates["govee"]}
            dev_kwargs["govee"] = GoveeConfig(**merged)

        kwargs["devices"] = DevicesConfig(
            openrgb=dev_kwargs.get("openrgb", existing.devices.openrgb),
            lifx=dev_kwargs.get("lifx", existing.devices.lifx),
            govee=dev_kwargs.get("govee", existing.devices.govee),
        )

    # Reconstruct AppConfig with updates applied
    return AppConfig(
        engine=kwargs.get("engine", existing.engine),
        effect=kwargs.get("effect", existing.effect),
        network=kwargs.get("network", existing.network),
        web=kwargs.get("web", existing.web),
        devices=kwargs.get("devices", existing.devices),
        scene_config=existing.scene_config,
    )


@router.get("/config")
async def get_config(request: Request) -> dict[str, Any]:
    config = request.app.state.config
    data = dataclasses.asdict(config)
    strip_none(data)
    return data


@router.put("/config")
async def update_config(request: Request, body: dict[str, Any]) -> JSONResponse:
    config = request.app.state.config
    try:
        new_config = _merge_config(config, body)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except TypeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid config value type: {e}") from e
    request.app.state.config = new_config
    if request.app.state.config_path:
        await asyncio.to_thread(save_config, new_config, request.app.state.config_path)
    result = dataclasses.asdict(new_config)
    return JSONResponse(
        content=result,
        headers={"X-Requires-Restart": "true"},
    )


@router.get("/config/export")
async def export_config(request: Request) -> PlainTextResponse:
    config = request.app.state.config
    data = dataclasses.asdict(config)
    strip_none(data)
    dumped = tomli_w.dumps(data)
    return PlainTextResponse(dumped if isinstance(dumped, str) else dumped.decode())


@router.post("/config/import")
async def import_config(request: Request) -> dict[str, Any]:
    body = await request.body()
    try:
        data = tomllib.loads(body.decode())
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid TOML: {e}") from e
    config = request.app.state.config
    try:
        new_config = _merge_config(config, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except TypeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid config value type: {e}") from e
    request.app.state.config = new_config
    if request.app.state.config_path:
        await asyncio.to_thread(save_config, new_config, request.app.state.config_path)
    return JSONResponse(
        content=dataclasses.asdict(new_config),
        headers={"X-Requires-Restart": "true"},
    )
