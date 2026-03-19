"""Scene REST endpoints for 3D device placement and spatial mapping."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Request

from dj_ledfx.config import save_config
from dj_ledfx.spatial.compositor import SpatialCompositor
from dj_ledfx.spatial.geometry import (
    MatrixGeometry,
    PointGeometry,
    StripGeometry,
)
from dj_ledfx.spatial.mapping import LinearMapping, mapping_from_config
from dj_ledfx.web.schemas import (
    GeometrySchema,
    MappingResponse,
    PlacementResponse,
    SceneResponse,
    UpdateMappingRequest,
    UpdatePlacementRequest,
)

if TYPE_CHECKING:
    from dj_ledfx.spatial.scene import DevicePlacement, SceneModel

router = APIRouter(prefix="/scene", tags=["scene"])


def _placements_to_config(scene: SceneModel) -> list[dict]:
    devices = []
    for p in scene.placements.values():
        entry: dict = {
            "name": p.device_id,
            "position": list(p.position),
        }
        if isinstance(p.geometry, PointGeometry):
            entry["geometry"] = "point"
        elif isinstance(p.geometry, StripGeometry):
            entry["geometry"] = "strip"
            entry["direction"] = list(p.geometry.direction)
            entry["length"] = p.geometry.length
        elif isinstance(p.geometry, MatrixGeometry):
            entry["geometry"] = "matrix"
        devices.append(entry)
    return devices


async def _persist_scene_config(request: Request) -> None:
    """Persist current scene placements back to the TOML config file."""
    config = request.app.state.config
    config_path = request.app.state.config_path
    if config_path is None:
        return
    scene = request.app.state.scene_model
    if config.scene_config is None:
        config.scene_config = {}
    if scene is not None:
        config.scene_config["devices"] = _placements_to_config(scene)
    await asyncio.to_thread(save_config, config, config_path)


def _get_scene(request: Request) -> SceneModel | None:
    return request.app.state.scene_model


def _ensure_scene(request: Request) -> SceneModel:
    """Return the scene model, creating an empty one if none exists."""
    scene = request.app.state.scene_model
    if scene is None:
        from dj_ledfx.spatial.scene import SceneModel as SM

        scene = SM(placements={})
        request.app.state.scene_model = scene
    return scene


def _placement_to_response(
    p: DevicePlacement,
    strip_index: float | None = None,
) -> PlacementResponse:
    geo = p.geometry
    if isinstance(geo, PointGeometry):
        geo_schema = GeometrySchema(type="point")
    elif isinstance(geo, StripGeometry):
        geo_schema = GeometrySchema(
            type="strip",
            direction=list(geo.direction),
            length=geo.length,
        )
    elif isinstance(geo, MatrixGeometry):
        geo_schema = GeometrySchema(
            type="matrix",
            pixel_pitch=geo.pixel_pitch,
            tiles=[
                {
                    "offset_x": t.offset_x,
                    "offset_y": t.offset_y,
                    "width": t.width,
                    "height": t.height,
                }
                for t in geo.tiles
            ],
        )
    else:
        geo_schema = GeometrySchema(type="unknown")

    return PlacementResponse(
        device_id=p.device_id,
        position=list(p.position),
        geometry=geo_schema,
        led_count=p.led_count,
        strip_index=strip_index,
    )


def _rebuild_compositor(request: Request, scene: SceneModel) -> None:
    """Rebuild the spatial compositor after a scene mutation."""
    scheduler = request.app.state.scheduler
    if not scene.placements:
        scheduler.compositor = None
        request.app.state.compositor = None
        return

    config = request.app.state.config
    scene_cfg = config.scene_config or {}
    mapping = mapping_from_config(scene_cfg)

    new_compositor = SpatialCompositor(scene, mapping)
    scheduler.compositor = new_compositor
    request.app.state.compositor = new_compositor


@router.get("", response_model=SceneResponse)
async def get_scene(request: Request) -> SceneResponse:
    scene = _get_scene(request)
    if scene is None or not scene.placements:
        return SceneResponse(placements=[], mapping=None, bounds=None)

    compositor: SpatialCompositor | None = request.app.state.compositor
    strip_indices: dict[str, float] = {}
    if compositor is not None:
        for device_id, indices in compositor.get_strip_indices().items():
            strip_indices[device_id] = float(indices.mean())

    placements = [
        _placement_to_response(p, strip_index=strip_indices.get(p.device_id))
        for p in scene.placements.values()
    ]
    bounds_min, bounds_max = scene.get_bounds()

    mapping_resp = None
    config = request.app.state.config
    if config.scene_config is not None:
        mapping_name = config.scene_config.get("mapping", "linear")
        mapping_params = config.scene_config.get("mapping_params", {})
        mapping_resp = MappingResponse(type=mapping_name, params=mapping_params)

    return SceneResponse(
        placements=placements,
        mapping=mapping_resp,
        bounds=[bounds_min.tolist(), bounds_max.tolist()],
    )


@router.get("/devices", response_model=list[PlacementResponse])
async def get_scene_devices(request: Request) -> list[PlacementResponse]:
    scene = _get_scene(request)
    if scene is None:
        return []
    return [_placement_to_response(p) for p in scene.placements.values()]


@router.put("/devices/{device_name}", response_model=PlacementResponse)
async def update_scene_device(
    request: Request, device_name: str, body: UpdatePlacementRequest
) -> PlacementResponse:
    """Add or update a device placement."""
    scene = _ensure_scene(request)

    geometry = None
    if body.geometry == "point":
        geometry = PointGeometry()
    elif body.geometry == "strip":
        direction = tuple(body.direction) if body.direction else (1.0, 0.0, 0.0)
        length = body.length if body.length is not None else 1.0
        geometry = StripGeometry(direction=direction, length=length)
    elif body.geometry == "matrix":
        geometry = MatrixGeometry()

    if device_name in scene.placements:
        position = tuple(body.position) if body.position is not None else None
        scene.update_placement(device_name, position=position, geometry=geometry)
    else:
        if body.position is None:
            raise HTTPException(
                status_code=400,
                detail="position is required when adding a new device",
            )
        from dj_ledfx.spatial.scene import DevicePlacement

        # Look up real LED count from device manager
        led_count = body.led_count or 1
        device_manager = request.app.state.device_manager
        managed = device_manager.get_device(device_name)
        if managed is not None:
            led_count = managed.adapter.led_count
            if geometry is None and hasattr(managed.adapter, "geometry") and managed.adapter.geometry is not None:
                geometry = managed.adapter.geometry

        scene.add_placement(
            DevicePlacement(
                device_id=device_name,
                position=tuple(body.position),
                geometry=geometry or PointGeometry(),
                led_count=led_count,
            )
        )

    _rebuild_compositor(request, scene)
    await _persist_scene_config(request)
    return _placement_to_response(scene.placements[device_name])


@router.delete("/devices/{device_name}")
async def delete_scene_device(request: Request, device_name: str) -> dict:
    scene = _ensure_scene(request)
    if device_name not in scene.placements:
        raise HTTPException(status_code=404, detail=f"Device '{device_name}' not in scene")
    scene.remove_placement(device_name)
    _rebuild_compositor(request, scene)
    await _persist_scene_config(request)
    return {"removed": device_name}


@router.put("/mapping", response_model=MappingResponse)
async def update_mapping(request: Request, body: UpdateMappingRequest) -> MappingResponse:
    scene = _ensure_scene(request)

    config = request.app.state.config
    if config.scene_config is None:
        config.scene_config = {}
    config.scene_config["mapping"] = body.type
    config.scene_config["mapping_params"] = body.params

    _rebuild_compositor(request, scene)
    await _persist_scene_config(request)

    return MappingResponse(type=body.type, params=body.params)
