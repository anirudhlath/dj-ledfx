"""The old UI's effect controls and presets, aimed at a zone's classic effect (spec §6.5).

Deleted with the old UI in F11.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Request

from dj_ledfx.effects.presets import Preset
from dj_ledfx.effects.registry import get_effect_schemas
from dj_ledfx.web.errors import answers
from dj_ledfx.web.schemas import (
    ActiveEffectResponse,
    CreatePresetRequest,
    PresetResponse,
    SetEffectRequest,
)
from dj_ledfx.web.state import get_zones

router = APIRouter()

ZoneQuery = Annotated[str, Query(description="The zone whose classic effect this is")]


def _known_effect(effect: str | None) -> None:
    if effect is not None and effect not in get_effect_schemas():
        raise HTTPException(status_code=404, detail=f"Unknown effect: {effect}")


def _classic(request: Request, zone: str) -> tuple[str, dict[str, Any]]:
    """The classic effect a zone plays, with its settings; 404 when it plays none."""
    zones = get_zones(request)
    with answers():
        name = zones.get_zone(zone).name
    current = zones.classic_layer(zone)
    if current is None:
        raise HTTPException(status_code=404, detail=f"{name} isn't playing a classic effect")
    return current


@router.get("/effects")
async def list_effects() -> dict[str, Any]:
    schemas = get_effect_schemas()
    result = {}
    for name, params in schemas.items():
        result[name] = {
            k: {
                "type": p.type,
                "default": p.default,
                "min": p.min,
                "max": p.max,
                "step": p.step,
                "choices": p.choices,
                "label": p.label,
                "description": p.description,
            }
            for k, p in params.items()
        }
    return result


@router.get("/effects/active")
async def get_active_effect(request: Request, zone: ZoneQuery) -> ActiveEffectResponse:
    effect, params = _classic(request, zone)
    return ActiveEffectResponse(effect=effect, params=params)


@router.put("/effects/active")
async def set_active_effect(
    request: Request, zone: ZoneQuery, body: SetEffectRequest
) -> ActiveEffectResponse:
    """New settings apply in place; another effect starts its classic look on the zone."""
    _known_effect(body.effect)
    with answers():
        effect, params = await get_zones(request).set_classic_effect(
            zone, body.effect, body.params or {}
        )
    return ActiveEffectResponse(effect=effect, params=params)


@router.get("/presets")
async def list_presets(request: Request) -> list[PresetResponse]:
    store = request.app.state.preset_store
    return [
        PresetResponse(name=p.name, effect_class=p.effect_class, params=p.params)
        for p in store.list()
    ]


@router.post("/presets")
async def save_preset(
    request: Request, zone: ZoneQuery, body: CreatePresetRequest
) -> PresetResponse:
    """Save the classic effect the zone plays, with its settings."""
    effect, params = _classic(request, zone)
    preset = Preset(name=body.name, effect_class=effect, params=params)
    await request.app.state.preset_store.save_async(preset)
    return PresetResponse(name=preset.name, effect_class=preset.effect_class, params=preset.params)


@router.put("/presets/{name}")
async def update_preset(request: Request, name: str, body: SetEffectRequest) -> PresetResponse:
    store = request.app.state.preset_store
    try:
        existing = store.load(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Preset not found: {name}") from exc
    params = dict(existing.params)
    if body.params:
        params.update(body.params)
    updated = Preset(name=name, effect_class=body.effect or existing.effect_class, params=params)
    await store.save_async(updated)
    return PresetResponse(
        name=updated.name, effect_class=updated.effect_class, params=updated.params
    )


@router.post("/presets/{name}/load")
async def load_preset(request: Request, name: str, zone: ZoneQuery) -> ActiveEffectResponse:
    """Play the preset's effect, with its settings, on the zone."""
    try:
        preset = request.app.state.preset_store.load(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Preset not found: {name}") from exc
    _known_effect(preset.effect_class)
    with answers():
        effect, params = await get_zones(request).set_classic_effect(
            zone, preset.effect_class, preset.params
        )
    return ActiveEffectResponse(effect=effect, params=params)


@router.delete("/presets/{name}")
async def delete_preset(request: Request, name: str) -> dict[str, str]:
    store = request.app.state.preset_store
    try:
        await store.delete_async(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Preset not found: {name}") from exc
    return {"status": "deleted"}
