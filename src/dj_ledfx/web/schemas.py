from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


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
    status: str = "online"


class GroupRequest(BaseModel):
    name: str
    color: str = "#00e5ff"


class AssignGroupRequest(BaseModel):
    group: str


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None


# Scene schemas


class GeometrySchema(BaseModel):
    type: Literal["point", "strip", "matrix", "unknown"]
    direction: list[float] | None = None
    length: float | None = None
    pixel_pitch: float | None = None
    tiles: list[dict[str, Any]] | None = None


class PlacementResponse(BaseModel):
    device_id: str
    position: list[float]
    geometry: GeometrySchema
    led_count: int
    strip_index: float | None = None


class MappingResponse(BaseModel):
    type: Literal["linear", "radial"]
    params: dict[str, Any]


class SceneResponse(BaseModel):
    placements: list[PlacementResponse]
    mapping: MappingResponse | None = None
    bounds: list[list[float]] | None = None


class UpdatePlacementRequest(BaseModel):
    position: list[float] | None = None
    geometry: Literal["point", "strip", "matrix"] | None = None
    direction: list[float] | None = None
    length: float | None = None
    led_count: int | None = None


class UpdateMappingRequest(BaseModel):
    type: Literal["linear", "radial"]
    params: dict[str, Any] = {}
