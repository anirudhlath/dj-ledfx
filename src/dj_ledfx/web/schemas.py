from __future__ import annotations
from pydantic import BaseModel
from typing import Any


class EffectSchema(BaseModel):
    name: str
    parameters: dict[str, Any]


class ActiveEffectResponse(BaseModel):
    effect: str
    params: dict[str, Any]


class SetEffectRequest(BaseModel):
    effect: str | None = None
    params: dict[str, Any] | None = None


class PresetResponse(BaseModel):
    name: str
    effect_class: str
    params: dict[str, Any]


class CreatePresetRequest(BaseModel):
    name: str


class DeviceResponse(BaseModel):
    name: str
    device_type: str
    led_count: int
    address: str
    group: str | None = None
    send_fps: float = 0.0
    effective_latency_ms: float = 0.0
    frames_dropped: int = 0
    connected: bool = True


class GroupRequest(BaseModel):
    name: str
    color: str = "#00e5ff"


class AssignGroupRequest(BaseModel):
    group: str


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
