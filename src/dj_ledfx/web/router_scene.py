"""Scene REST endpoints for 3D device placement and spatial mapping."""

from __future__ import annotations

import asyncio
import uuid
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from dj_ledfx.config import save_config
from dj_ledfx.spatial.compositor import SpatialCompositor
from dj_ledfx.spatial.geometry import (
    MatrixGeometry,
    PointGeometry,
    StripGeometry,
)
from dj_ledfx.spatial.mapping import mapping_from_config
from dj_ledfx.web.schemas import (
    CreateSceneRequest,
    GeometrySchema,
    MappingResponse,
    PlacementResponse,
    SceneListItem,
    SceneResponse,
    UpdateMappingRequest,
    UpdatePlacementRequest,
    UpdateSceneRequest,
)
from dj_ledfx.web.state import get_db

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


# ---------------------------------------------------------------------------
# Legacy single-scene endpoints (backward-compatible)
# ---------------------------------------------------------------------------


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
            has_geometry = hasattr(managed.adapter, "geometry")
            if geometry is None and has_geometry and managed.adapter.geometry is not None:
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


# ---------------------------------------------------------------------------
# Multi-scene CRUD endpoints (requires StateDB on app.state)
# ---------------------------------------------------------------------------


async def _get_scene_row(db: Any, scene_id: str) -> dict[str, Any]:
    """Load a single scene row by ID or raise 404."""
    row = await db.load_scene_by_id(scene_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Scene not found: {scene_id}")
    return row


router_scenes = APIRouter(prefix="/scenes", tags=["scenes"])


@router_scenes.get("", response_model=list[SceneListItem])
async def list_scenes(request: Request) -> list[SceneListItem]:
    """List all scenes from DB if available, else return current in-memory scene."""
    try:
        db = get_db(request)
    except HTTPException:
        db = None
    if db is not None:
        rows = await db.load_scenes()
        return [
            SceneListItem(
                id=row["id"],
                name=row["name"],
                is_active=bool(row.get("is_active", 0)),
                mapping_type=row.get("mapping_type"),
                effect_mode=row.get("effect_mode"),
            )
            for row in rows
        ]
    # Fallback: return in-memory scene as "default"
    scene = _get_scene(request)
    if scene is not None:
        return [SceneListItem(id="default", name="Default", is_active=True)]
    return []


@router_scenes.post("", response_model=SceneListItem)
async def create_scene(request: Request, body: CreateSceneRequest) -> SceneListItem:
    db = get_db(request)
    scene_id = str(uuid.uuid4())
    await db.save_scene(
        {
            "id": scene_id,
            "name": body.name,
            "mapping_type": body.mapping_type,
            "effect_mode": body.effect_mode,
            "is_active": 0,
        }
    )
    return SceneListItem(
        id=scene_id,
        name=body.name,
        is_active=False,
        mapping_type=body.mapping_type,
        effect_mode=body.effect_mode,
    )


@router_scenes.get("/{scene_id}", response_model=SceneListItem)
async def get_scene_by_id(request: Request, scene_id: str) -> SceneListItem:
    db = get_db(request)
    row = await _get_scene_row(db, scene_id)
    return SceneListItem(
        id=row["id"],
        name=row["name"],
        is_active=bool(row.get("is_active", 0)),
        mapping_type=row.get("mapping_type"),
        effect_mode=row.get("effect_mode"),
    )


@router_scenes.put("/{scene_id}", response_model=SceneListItem)
async def update_scene(request: Request, scene_id: str, body: UpdateSceneRequest) -> SceneListItem:
    db = get_db(request)
    existing = await _get_scene_row(db, scene_id)

    # Guard: can't change effect_mode while scene is active
    if (
        existing.get("is_active")
        and body.effect_mode is not None
        and body.effect_mode != existing.get("effect_mode")
    ):
        raise HTTPException(409, "Cannot change effect_mode while scene is active. Deactivate first.")

    updated: dict[str, Any] = {"id": scene_id}
    updated["name"] = body.name if body.name is not None else existing["name"]
    updated["mapping_type"] = (
        body.mapping_type if body.mapping_type is not None else existing.get("mapping_type")
    )
    updated["effect_mode"] = (
        body.effect_mode if body.effect_mode is not None else existing.get("effect_mode")
    )
    updated["is_active"] = existing.get("is_active", 0)

    await db.save_scene(updated)
    return SceneListItem(
        id=scene_id,
        name=updated["name"],
        is_active=bool(updated["is_active"]),
        mapping_type=updated["mapping_type"],
        effect_mode=updated["effect_mode"],
    )


@router_scenes.delete("/{scene_id}")
async def delete_scene(request: Request, scene_id: str) -> dict[str, str]:
    db = get_db(request)
    scene = await _get_scene_row(db, scene_id)
    if scene.get("is_active"):
        pm = getattr(request.app.state, "pipeline_manager", None)
        if pm is not None:
            await pm.deactivate_scene(scene_id)
        await db.set_scene_inactive(scene_id)
    await db.delete_scene(scene_id)
    return {"status": "deleted", "scene_id": scene_id}


@router_scenes.post("/{scene_id}/activate")
async def activate_scene(request: Request, scene_id: str) -> dict[str, str]:
    db = get_db(request)
    await _get_scene_row(db, scene_id)

    # Conflict detection: check if any device in this scene is already in another active scene.
    target_placements = await db.load_scene_placements(scene_id)
    target_device_ids = {p["device_id"] for p in target_placements}

    if target_device_ids:
        all_scenes = await db.load_scenes()
        conflicting_devices: list[str] = []
        for scene_row in all_scenes:
            other_id = scene_row["id"]
            if other_id == scene_id:
                continue
            if not bool(scene_row.get("is_active", 0)):
                continue
            other_placements = await db.load_scene_placements(other_id)
            for p in other_placements:
                if p["device_id"] in target_device_ids:
                    conflicting_devices.append(p["device_id"])
        if conflicting_devices:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "device_conflict",
                    "conflicting_devices": sorted(set(conflicting_devices)),
                },
            )

    await db.set_scene_active(scene_id)
    pm = getattr(request.app.state, "pipeline_manager", None)
    if pm is not None:
        await pm.activate_scene(scene_id)
    return {"status": "activated", "scene_id": scene_id}


@router_scenes.post("/{scene_id}/deactivate")
async def deactivate_scene(request: Request, scene_id: str) -> dict[str, str]:
    db = get_db(request)
    await _get_scene_row(db, scene_id)
    await db.set_scene_inactive(scene_id)
    pm = getattr(request.app.state, "pipeline_manager", None)
    if pm is not None:
        await pm.deactivate_scene(scene_id)
    return {"status": "deactivated", "scene_id": scene_id}


class SetSceneEffectRequest(BaseModel):
    effect_name: str
    params: dict[str, Any] = {}


@router_scenes.get("/{scene_id}/effect")
async def get_scene_effect(request: Request, scene_id: str) -> dict:
    pm = getattr(request.app.state, "pipeline_manager", None)
    if pm is None:
        raise HTTPException(501, "Pipeline manager not available")
    try:
        return pm.get_scene_effect(scene_id)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e


@router_scenes.put("/{scene_id}/effect")
async def set_scene_effect(
    request: Request, scene_id: str, body: SetSceneEffectRequest
) -> dict:
    pm = getattr(request.app.state, "pipeline_manager", None)
    if pm is None:
        raise HTTPException(501, "Pipeline manager not available")
    try:
        pm.set_scene_effect(scene_id, body.effect_name, body.params)
    except ValueError as e:
        raise HTTPException(404, str(e)) from e
    return {"status": "ok", "scene_id": scene_id, "effect_name": body.effect_name}


@router_scenes.put("/{scene_id}/devices/{device_name}", response_model=PlacementResponse)
async def add_or_update_scene_placement(
    request: Request, scene_id: str, device_name: str, body: UpdatePlacementRequest
) -> PlacementResponse:
    """Add or update a device placement in a scene (stored in DB)."""
    db = get_db(request)
    await _get_scene_row(db, scene_id)

    # Resolve display name to stable_id via DeviceManager, falling back to display name.
    device_stable_id: str = device_name
    try:
        device_manager = request.app.state.device_manager
        from dj_ledfx.devices.manager import ManagedDevice as _MD

        managed_for_id = device_manager.get_device(device_name)
        if managed_for_id is not None and isinstance(managed_for_id, _MD):
            device_stable_id = managed_for_id.adapter.device_info.effective_id
    except Exception:
        pass

    # Ensure the device exists in the DB (required by FK constraint)
    if not await db.device_exists(device_stable_id):
        # Auto-register device with a minimal record
        device_record: dict[str, Any] = {
            "id": device_stable_id,
            "name": device_name,
            "backend": "unknown",
        }
        # Try to get more info from device manager
        try:
            device_manager = request.app.state.device_manager
            from dj_ledfx.devices.manager import ManagedDevice as _MD

            managed = device_manager.get_device(device_name)
            if managed is not None and isinstance(managed, _MD):
                info = managed.adapter.device_info
                device_record["name"] = str(info.name)
                device_record["backend"] = (
                    info.device_type.split("_")[0] if info.device_type else "unknown"
                )
                device_record["led_count"] = int(managed.adapter.led_count)
                if info.address:
                    ip = info.address.split(":")[0] if ":" in info.address else info.address
                    device_record["ip"] = str(ip)
        except Exception:
            pass
        await db.upsert_device(device_record)

    placement_data: dict[str, Any] = {
        "scene_id": scene_id,
        "device_id": device_stable_id,
    }
    if body.position is not None:
        placement_data["position_x"] = body.position[0]
        placement_data["position_y"] = body.position[1]
        placement_data["position_z"] = body.position[2]
    if body.geometry is not None:
        placement_data["geometry_type"] = body.geometry
    if body.direction is not None:
        placement_data["direction_x"] = body.direction[0]
        placement_data["direction_y"] = body.direction[1]
        placement_data["direction_z"] = body.direction[2]
    if body.length is not None:
        placement_data["length"] = body.length

    await db.save_placement(placement_data)

    # Build a PlacementResponse from the stored data
    geo: PointGeometry | StripGeometry | MatrixGeometry = PointGeometry()
    if body.geometry == "strip":
        direction = tuple(body.direction) if body.direction else (1.0, 0.0, 0.0)
        length = body.length if body.length is not None else 1.0
        geo = StripGeometry(direction=direction, length=length)
    elif body.geometry == "matrix":
        geo = MatrixGeometry()

    led_count = body.led_count or 1
    device_manager = request.app.state.device_manager
    managed = device_manager.get_device(device_name)
    if managed is not None:
        led_count = managed.adapter.led_count

    from dj_ledfx.spatial.scene import DevicePlacement as DP

    placement = DP(
        device_id=device_stable_id,
        position=tuple(body.position) if body.position else (0.0, 0.0, 0.0),
        geometry=geo,
        led_count=led_count,
    )
    return _placement_to_response(placement)


@router_scenes.delete("/{scene_id}/devices/{device_name}")
async def remove_scene_placement(
    request: Request, scene_id: str, device_name: str
) -> dict[str, str]:
    """Remove a device placement from a scene."""
    db = get_db(request)
    await _get_scene_row(db, scene_id)

    await db.delete_placement(scene_id, device_name)
    return {"status": "removed", "device_name": device_name}
