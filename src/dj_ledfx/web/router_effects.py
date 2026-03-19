"""Effects and presets REST endpoints."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from dj_ledfx.effects.presets import Preset
from dj_ledfx.effects.registry import create_effect, get_effect_schemas
from dj_ledfx.web.schemas import (
    ActiveEffectResponse,
    CreatePresetRequest,
    PresetResponse,
    SetEffectRequest,
)

router = APIRouter()


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
async def get_active_effect(request: Request) -> ActiveEffectResponse:
    deck = request.app.state.effect_deck
    return ActiveEffectResponse(
        effect=deck.effect_name,
        params=deck.effect.get_params(),
    )


@router.put("/effects/active")
async def set_active_effect(request: Request, body: SetEffectRequest) -> ActiveEffectResponse:
    deck = request.app.state.effect_deck
    try:
        deck.apply_update(body.effect, body.params or {})
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown effect: {body.effect}") from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ActiveEffectResponse(
        effect=deck.effect_name,
        params=deck.effect.get_params(),
    )


@router.get("/presets")
async def list_presets(request: Request) -> list[PresetResponse]:
    store = request.app.state.preset_store
    return [
        PresetResponse(name=p.name, effect_class=p.effect_class, params=p.params)
        for p in store.list()
    ]


@router.post("/presets")
async def save_preset(request: Request, body: CreatePresetRequest) -> PresetResponse:
    deck = request.app.state.effect_deck
    store = request.app.state.preset_store
    preset = Preset(
        name=body.name,
        effect_class=deck.effect_name,
        params=deck.effect.get_params(),
    )
    await asyncio.to_thread(store.save, preset)
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
    await asyncio.to_thread(store.save, updated)
    return PresetResponse(
        name=updated.name, effect_class=updated.effect_class, params=updated.params
    )


@router.post("/presets/{name}/load")
async def load_preset(request: Request, name: str) -> ActiveEffectResponse:
    deck = request.app.state.effect_deck
    store = request.app.state.preset_store
    try:
        preset = store.load(name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Preset not found: {name}") from exc
    try:
        new_effect = create_effect(preset.effect_class, **preset.params)
        deck.swap_effect(new_effect)
    except KeyError as exc:
        raise HTTPException(
            status_code=404, detail=f"Unknown effect: {preset.effect_class}"
        ) from exc
    except TypeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid preset params: {exc}") from exc
    return ActiveEffectResponse(
        effect=deck.effect_name,
        params=deck.effect.get_params(),
    )


@router.delete("/presets/{name}")
async def delete_preset(request: Request, name: str) -> dict[str, str]:
    store = request.app.state.preset_store
    try:
        await asyncio.to_thread(store.delete, name)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Preset not found: {name}") from exc
    return {"status": "deleted"}
