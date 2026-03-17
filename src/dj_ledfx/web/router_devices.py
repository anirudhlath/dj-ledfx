"""Device management REST endpoints."""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from dj_ledfx.web.schemas import (
    AssignGroupRequest,
    DeviceResponse,
    GroupRequest,
)

router = APIRouter()


@router.get("/devices")
def list_devices(request: Request) -> list[DeviceResponse]:
    manager = request.app.state.device_manager
    scheduler = request.app.state.scheduler
    stats_list = scheduler.get_device_stats() if hasattr(scheduler, 'get_device_stats') else []
    stats_by_name = {s.device_name: s for s in stats_list}

    devices = []
    for d in manager.devices:
        info = d.adapter.device_info
        stats = stats_by_name.get(info.name)
        devices.append(DeviceResponse(
            name=info.name,
            device_type=info.device_type,
            led_count=d.adapter.led_count,
            address=info.address,
            group=manager.get_device_group(info.name),
            send_fps=stats.send_fps if stats else 0.0,
            effective_latency_ms=stats.effective_latency_ms if stats else 0.0,
            frames_dropped=stats.frames_dropped if stats else 0,
            connected=d.adapter.is_connected,
        ))
    return devices


@router.post("/devices/discover")
async def discover_devices(request: Request) -> dict[str, Any]:
    manager = request.app.state.device_manager
    config = request.app.state.config
    new_names = await manager.rediscover(config)
    return {"discovered": new_names}


@router.post("/devices/{name}/identify")
async def identify_device(request: Request, name: str) -> dict[str, str]:
    manager = request.app.state.device_manager
    try:
        await manager.identify_device(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Device not found: {name}")
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {"status": "ok"}


@router.put("/devices/{name}/latency")
def update_device_latency(
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
def assign_device_group(
    request: Request, name: str, body: AssignGroupRequest
) -> dict[str, str]:
    manager = request.app.state.device_manager
    try:
        manager.assign_to_group(name, body.group)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return {"status": "ok"}


@router.get("/devices/groups")
def list_groups(request: Request) -> dict[str, Any]:
    manager = request.app.state.device_manager
    return {
        name: {"name": g.name, "color": g.color}
        for name, g in manager.get_groups().items()
    }


@router.post("/devices/groups")
def create_group(request: Request, body: GroupRequest) -> dict[str, Any]:
    manager = request.app.state.device_manager
    group = manager.create_group(body.name, body.color)
    return {"name": group.name, "color": group.color}


@router.delete("/devices/groups/{name}")
def delete_group(request: Request, name: str) -> dict[str, str]:
    manager = request.app.state.device_manager
    manager.delete_group(name)
    return {"status": "deleted"}
