"""Lights with their status (web spec §9.1, §12.2). Device actions stay on /api/devices."""

from __future__ import annotations

from fastapi import APIRouter, Request

from dj_ledfx.web import contract as api
from dj_ledfx.web.state import get_light_monitor

router = APIRouter()


@router.get("/lights")
async def list_lights(request: Request) -> list[api.Light]:
    monitor = get_light_monitor(request)
    monitor.refresh()  # picks up lights found since the last poll
    scheduler = request.app.state.scheduler
    stats = {entry.device_id: entry for entry in scheduler.get_device_stats()}
    lights = []
    for managed in request.app.state.device_manager.devices:
        state = monitor.state(managed.adapter.device_info.stable_id or "")
        if state is not None:
            lights.append(api.light_out(managed, state, stats.get(state.device_id)))
    return lights
