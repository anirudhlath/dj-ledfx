"""Lights with their status (web spec §9.1, §12.2): the PC is one light with parts (spec
§6.3). Device actions stay on /api/devices."""

from __future__ import annotations

from fastapi import APIRouter, Request

from dj_ledfx.web import contract as api
from dj_ledfx.web.state import get_light_monitor, light_index

router = APIRouter()


@router.get("/lights")
async def list_lights(request: Request) -> list[api.Light]:
    monitor = get_light_monitor(request)
    monitor.refresh()  # picks up lights found since the last poll
    devices = request.app.state.device_manager
    stats = {entry.device_id: entry for entry in request.app.state.scheduler.get_device_stats()}
    index = light_index(request.app)
    home_map = request.app.state.home_map
    states = {state.device_id: state for state in monitor.light_states(index)}
    lights: list[api.Light] = []
    for entry in index.entries:
        state = states.get(entry.id)
        parts = [m for d in entry.devices if (m := devices.get_by_stable_id(d)) is not None]
        if state is None or not parts:
            continue
        if entry.is_pc:
            lights.append(api.pc_out(entry, parts, state, stats, home_map=home_map))
        else:
            lights.append(api.light_out(parts[0], state, stats.get(entry.id), home_map=home_map))
    return lights
