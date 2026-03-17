"""Effects and presets REST endpoints."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from dj_ledfx.effects.registry import create_effect, get_effect_classes, get_effect_schemas
from dj_ledfx.effects.presets import Preset
from dj_ledfx.web.schemas import (
    ActiveEffectResponse,
    CreatePresetRequest,
    PresetResponse,
    SetEffectRequest,
)

router = APIRouter()


@router.get("/effects")
def list_effects() -> dict[str, Any]:
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
def get_active_effect(request: Request) -> ActiveEffectResponse:
    deck = request.app.state.effect_deck
    return ActiveEffectResponse(
        effect=deck.effect_name,
        params=deck.effect.get_params(),
    )


@router.put("/effects/active")
def set_active_effect(request: Request, body: SetEffectRequest) -> ActiveEffectResponse:
    deck = request.app.state.effect_deck
    if body.effect and body.effect != deck.effect_name:
        try:
            params = body.params or {}
            new_effect = create_effect(body.effect, **params)
            deck.swap_effect(new_effect)
        except KeyError:
            raise HTTPException(status_code=404, detail=f"Unknown effect: {body.effect}")
    elif body.params:
        try:
            deck.effect.set_params(**body.params)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
    return ActiveEffectResponse(
        effect=deck.effect_name,
        params=deck.effect.get_params(),
    )


@router.get("/presets")
def list_presets(request: Request) -> list[PresetResponse]:
    store = request.app.state.preset_store
    return [
        PresetResponse(name=p.name, effect_class=p.effect_class, params=p.params)
        for p in store.list()
    ]


@router.post("/presets")
def save_preset(request: Request, body: CreatePresetRequest) -> PresetResponse:
    deck = request.app.state.effect_deck
    store = request.app.state.preset_store
    preset = Preset(
        name=body.name,
        effect_class=deck.effect_name,
        params=deck.effect.get_params(),
    )
    store.save(preset)
    return PresetResponse(name=preset.name, effect_class=preset.effect_class, params=preset.params)


@router.put("/presets/{name}")
def update_preset(request: Request, name: str, body: SetEffectRequest) -> PresetResponse:
    store = request.app.state.preset_store
    try:
        existing = store.load(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Preset not found: {name}")
    params = dict(existing.params)
    if body.params:
        params.update(body.params)
    updated = Preset(name=name, effect_class=body.effect or existing.effect_class, params=params)
    store.save(updated)
    return PresetResponse(name=updated.name, effect_class=updated.effect_class, params=updated.params)


@router.post("/presets/{name}/load")
def load_preset(request: Request, name: str) -> ActiveEffectResponse:
    deck = request.app.state.effect_deck
    store = request.app.state.preset_store
    try:
        preset = store.load(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Preset not found: {name}")
    try:
        new_effect = create_effect(preset.effect_class, **preset.params)
        deck.swap_effect(new_effect)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown effect: {preset.effect_class}")
    return ActiveEffectResponse(
        effect=deck.effect_name,
        params=deck.effect.get_params(),
    )


@router.delete("/presets/{name}")
def delete_preset(request: Request, name: str) -> dict[str, str]:
    store = request.app.state.preset_store
    try:
        store.delete(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Preset not found: {name}")
    return {"status": "deleted"}
