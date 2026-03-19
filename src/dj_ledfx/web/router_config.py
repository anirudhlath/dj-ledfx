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


def _merge_section(cls: type, existing: object, updates: dict[str, Any]) -> object:
    """Merge partial updates into a dataclass instance."""
    merged = {**dataclasses.asdict(existing), **updates}  # type: ignore[arg-type]
    return cls(**merged)


def _merge_config(existing: AppConfig, updates: dict[str, Any]) -> AppConfig:
    """Recursively merge partial updates into config, reconstructing dataclasses."""
    kwargs: dict[str, Any] = {}

    section_map = {
        "engine": (EngineConfig, existing.engine),
        "effect": (EffectConfig, existing.effect),
        "network": (NetworkConfig, existing.network),
        "web": (WebConfig, existing.web),
    }
    for key, (cls, current) in section_map.items():
        if key in updates:
            kwargs[key] = _merge_section(cls, current, updates[key])

    if "devices" in updates:
        dev_updates = updates["devices"]
        dev_section_map = {
            "openrgb": (OpenRGBConfig, existing.devices.openrgb),
            "lifx": (LIFXConfig, existing.devices.lifx),
            "govee": (GoveeConfig, existing.devices.govee),
        }
        dev_kwargs: dict[str, Any] = {}
        for key, (cls, current) in dev_section_map.items():
            if key in dev_updates:
                dev_kwargs[key] = _merge_section(cls, current, dev_updates[key])

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
