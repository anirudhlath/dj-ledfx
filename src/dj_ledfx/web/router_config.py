"""Configuration REST endpoints."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import tomllib
from typing import Any

import tomli_w
from fastapi import APIRouter, HTTPException, Request
from starlette.responses import JSONResponse, PlainTextResponse, Response

from dj_ledfx.config import (
    AppConfig,
    DevicesConfig,
    DiscoveryConfig,
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
from dj_ledfx.web.state import get_db, get_looks, get_zones

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
        "discovery": (DiscoveryConfig, existing.discovery),
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
        discovery=kwargs.get("discovery", existing.discovery),
        scene_config=existing.scene_config,
    )


def _check_preview_only(body: dict[str, Any]) -> None:
    engine = body.get("engine")
    value = engine.get("preview_only") if isinstance(engine, dict) else None
    if value is not None and not isinstance(value, bool):
        raise HTTPException(status_code=400, detail="engine.preview_only must be true or false")


def _requires_restart(old: AppConfig, new: AppConfig) -> str:
    """Preview only applies at once; every other change at the next start."""

    def rest(config: AppConfig) -> AppConfig:
        return dataclasses.replace(
            config, engine=dataclasses.replace(config.engine, preview_only=False)
        )

    return "true" if rest(old) != rest(new) else "false"


async def _apply_live(request: Request, config: AppConfig) -> None:
    zones = getattr(request.app.state, "zone_manager", None)
    if zones is not None:
        await zones.set_preview_only(config.engine.preview_only)


@router.get("/config")
async def get_config(request: Request) -> dict[str, Any]:
    config = request.app.state.config
    data = dataclasses.asdict(config)
    strip_none(data)
    return data


@router.put("/config")
async def update_config(request: Request, body: dict[str, Any]) -> JSONResponse:
    _check_preview_only(body)
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
    # Persist to StateDB when available
    try:
        db = get_db(request)
        for section, value in result.items():
            if isinstance(value, dict):
                str_kv = {k: json.dumps(v) for k, v in value.items() if not isinstance(v, dict)}
                if str_kv:
                    await db.save_config_bulk(section, str_kv)
    except HTTPException:
        pass
    await _apply_live(request, new_config)
    return JSONResponse(
        content=result,
        headers={"X-Requires-Restart": _requires_restart(config, new_config)},
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
    _check_preview_only(data)
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
    await _apply_live(request, new_config)
    return JSONResponse(
        content=dataclasses.asdict(new_config),
        headers={"X-Requires-Restart": _requires_restart(config, new_config)},
    )


@router.get("/state/export")
async def export_state(request: Request) -> Response:
    from dj_ledfx.persistence.toml_io import export_toml

    db = get_db(request)
    toml_str = await export_toml(db)
    return Response(content=toml_str, media_type="application/toml")


@router.post("/state/import")
async def import_state(request: Request) -> dict[str, str]:
    """Restore a backup: the running looks give way to the file's, which start as a Start
    would (ZoneManager.replace_state)."""
    from dj_ledfx.persistence.toml_io import import_toml

    db = get_db(request)
    try:
        text = (await request.body()).decode()
        tomllib.loads(text)
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid TOML: {exc}") from exc
    looks = get_looks(request)
    home_map = request.app.state.home_map  # None where the app has no map
    previews = request.app.state.previews

    async def restore() -> None:
        try:
            await import_toml(db, text)
        finally:
            await looks.load()
            if home_map is not None:
                await home_map.load()  # before the zones resume on the backup's map

    await get_zones(request).replace_state(restore)
    if previews is not None:
        await previews.home_changed()  # a preview moves to its zone's lights, or ends
    return {"status": "ok"}
