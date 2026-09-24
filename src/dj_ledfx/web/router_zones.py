"""Zones, running zones and groups (web spec §11.3, §12.3)."""

from __future__ import annotations

from dataclasses import replace

from fastapi import APIRouter, HTTPException, Request, Response

from dj_ledfx.web import contract as api
from dj_ledfx.web.errors import answers
from dj_ledfx.web.state import get_looks, get_zones

router = APIRouter()


@router.get("/zones")
async def list_zones(request: Request) -> list[api.Zone]:
    return [api.zone_out(zone) for zone in get_zones(request).zones()]


@router.post("/zones/groups", status_code=201)
async def create_group(request: Request, body: api.CreateGroup) -> api.Zone:
    with answers():
        zone = await get_zones(request).create_group(body.name, body.lights)
    return api.zone_out(zone)


@router.put("/zones/groups/{zone_id}")
async def update_group(request: Request, zone_id: str, body: api.UpdateGroup) -> api.Zone:
    with answers():
        zone = await get_zones(request).update_group(zone_id, name=body.name, lights=body.lights)
    return api.zone_out(zone)


@router.delete("/zones/groups/{zone_id}", status_code=204)
async def delete_group(request: Request, zone_id: str) -> Response:
    """Delete a group. A running group is turned off first."""
    with answers():
        await get_zones(request).delete_group(zone_id)
    return Response(status_code=204)


@router.get("/running")
async def list_running(request: Request) -> api.Running:
    return api.running_out(get_zones(request).running())


@router.post("/zones/{zone_id}/start")
async def start_zone(request: Request, zone_id: str, body: api.StartRequest) -> api.StartResponse:
    """Put a look on a zone: a saved look by id, or an unsaved draft."""
    with answers():
        if body.look_id is not None and body.look is None:
            look = get_looks(request).get(body.look_id)
        elif body.look is not None and body.look_id is None:
            look = api.look_in(body.look)
            if not look.id:
                look = replace(look, id="draft")
        else:
            raise HTTPException(status_code=400, detail="Send either lookId or look")
        result = await get_zones(request).start(zone_id, look)
    return api.start_out(result)


@router.put("/zones/{zone_id}/brightness")
async def set_brightness(request: Request, zone_id: str, body: api.Brightness) -> api.RunningZone:
    with answers():
        info = await get_zones(request).set_brightness(zone_id, body.value)
    return api.running_zone_out(info)


@router.post("/zones/{zone_id}/off", status_code=204)
async def turn_off(request: Request, zone_id: str) -> Response:
    """Stop the zone's look and put its lights back how they were. Idempotent."""
    with answers():
        await get_zones(request).off(zone_id)
    return Response(status_code=204)


@router.post("/zones/{zone_id}/restart")
async def restart_zone(request: Request, zone_id: str) -> api.RunningZone:
    with answers():
        info = await get_zones(request).restart(zone_id)
    return api.running_zone_out(info)


@router.post("/running/stop-all", status_code=204)
async def stop_all(request: Request) -> Response:
    await get_zones(request).stop_all()
    return Response(status_code=204)
