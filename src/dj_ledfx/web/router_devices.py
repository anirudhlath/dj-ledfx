"""Device management REST endpoints."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from starlette.responses import JSONResponse

from dj_ledfx.web.schemas import (
    AssignGroupRequest,
    DeviceResponse,
    GroupRequest,
)
from dj_ledfx.web.state import get_db

router = APIRouter()


@router.get("/devices")
async def list_devices(request: Request) -> list[DeviceResponse]:
    manager = request.app.state.device_manager
    scheduler = request.app.state.scheduler
    stats_list = scheduler.get_device_stats() if hasattr(scheduler, "get_device_stats") else []
    stats_by_name = {s.device_name: s for s in stats_list}

    devices = []
    for d in manager.devices:
        info = d.adapter.device_info
        stats = stats_by_name.get(info.name)
        devices.append(
            DeviceResponse(
                name=info.name,
                device_type=info.device_type,
                led_count=d.adapter.led_count,
                address=info.address,
                group=manager.get_device_group(info.name),
                send_fps=stats.send_fps if stats else 0.0,
                effective_latency_ms=stats.effective_latency_ms if stats else 0.0,
                frames_dropped=stats.frames_dropped if stats else 0,
                status=d.status,
            )
        )
    return devices


@router.post("/devices/discover")
async def discover_devices(request: Request) -> dict[str, Any]:
    manager = request.app.state.device_manager
    config = request.app.state.config
    new_names = await manager.rediscover(config)
    return {"discovered": new_names}


@router.post("/devices/scan")
async def scan_devices(request: Request) -> dict[str, Any]:
    """Trigger device discovery via DiscoveryOrchestrator if available, else fallback."""
    orchestrator = getattr(request.app.state, "discovery_orchestrator", None)
    if orchestrator is not None:
        found = await orchestrator.run_scan()
        return {"discovered": found}
    # Fallback to legacy rediscover
    manager = request.app.state.device_manager
    config = request.app.state.config
    new_names = await manager.rediscover(config)
    return {"discovered": len(new_names)}


# --- Group routes registered before parameterized /devices/{name} routes ---


@router.get("/devices/groups")
async def list_groups(request: Request) -> dict[str, Any]:
    manager = request.app.state.device_manager
    return {name: {"name": g.name, "color": g.color} for name, g in manager.get_groups().items()}


@router.post("/devices/groups")
async def create_group(request: Request, body: GroupRequest) -> dict[str, Any]:
    manager = request.app.state.device_manager
    group = manager.create_group(body.name, body.color)
    return {"name": group.name, "color": group.color}


@router.delete("/devices/groups/{name}")
async def delete_group(request: Request, name: str) -> dict[str, str]:
    manager = request.app.state.device_manager
    manager.delete_group(name)
    return {"status": "deleted"}


# --- Parameterized /devices/{name} routes ---


@router.post("/devices/{name}/identify")
async def identify_device(request: Request, name: str) -> JSONResponse:
    manager = request.app.state.device_manager
    device = manager.get_device(name)
    if device is None:
        raise HTTPException(status_code=404, detail=f"Device not found: {name}")
    if not device.adapter.is_connected:
        raise HTTPException(status_code=503, detail=f"Device not connected: {name}")
    asyncio.create_task(manager.identify_device(name))
    return JSONResponse(status_code=202, content={"status": "identifying"})


@router.put("/devices/{name}/latency")
async def update_device_latency(
    request: Request, name: str, body: dict[str, Any]
) -> dict[str, str]:
    manager = request.app.state.device_manager
    device = manager.get_device(name)
    if device is None:
        raise HTTPException(status_code=404, detail=f"Device not found: {name}")
    # Update manual offset if provided
    if "manual_offset_ms" in body:
        device.tracker.manual_offset_ms = float(body["manual_offset_ms"])
    return {"status": "ok"}


@router.put("/devices/{name}/group")
async def assign_device_group(
    request: Request, name: str, body: AssignGroupRequest
) -> dict[str, str]:
    manager = request.app.state.device_manager
    try:
        manager.assign_to_group(name, body.group)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"status": "ok"}


@router.delete("/devices/{name}")
async def unregister_device(request: Request, name: str) -> dict[str, str]:
    """Unregister (remove) a device by name."""
    manager = request.app.state.device_manager
    managed = manager.get_device(name)
    if managed is None:
        raise HTTPException(status_code=404, detail=f"Device not found: {name}")
    stable_id = managed.adapter.device_info.effective_id
    if managed.adapter.device_info.stable_id:
        manager.remove_device(managed.adapter.device_info.stable_id)
    else:
        # Fallback: remove by name (device has no stable_id)
        manager.remove_by_name(name)
    # Persist removal to DB if available
    try:
        db = get_db(request)
        await db.delete_device(stable_id)
    except HTTPException:
        pass  # DB not available — skip persistence
    return {"status": "removed"}
