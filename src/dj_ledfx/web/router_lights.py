"""Lights with their status (web spec §9.1, §12.2): the PC is one light with parts (spec
§6.3). A Govee lamp's own output is here too (the light-output plan's ruling 17). Device
actions stay on /api/devices."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from dj_ledfx.devices.govee.output import OUTPUT_KEY, GoveeOutput
from dj_ledfx.web import contract as api
from dj_ledfx.web.state import get_db, get_discovery, get_light_monitor, light_index

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
        lights.append(api.light_out(entry, parts, state, stats, home_map=home_map))
    return lights


@router.get("/lights/{light_id}/output")
async def get_lamp_output(request: Request, light_id: str) -> api.LampOutput:
    """A Govee lamp's output: how it plays now (razer segments or one colour, and how many
    segments), and its own setting, which the config and its model fill in."""
    row = await _lamp_row(request, light_id)
    managed = request.app.state.device_manager.get_by_stable_id(light_id)
    online = managed is not None and managed.status == "online"
    return _lamp_output(request, row, GoveeOutput.from_extra(row.get("extra")), online)


@router.put("/lights/{light_id}/output")
async def set_lamp_output(
    request: Request, light_id: str, body: api.LampOutputSetting
) -> api.LampOutput:
    """Set a Govee lamp's own output; a field left null goes back to the default. The lamp
    is reconnected at once to take it. One that doesn't answer goes offline (online is
    false) and takes the output when a scan finds it."""
    discovery = get_discovery(request)
    row = await _lamp_row(request, light_id)
    own = GoveeOutput(mode=body.mode, segments=body.segments)
    await get_db(request).set_device_extra(light_id, OUTPUT_KEY, own.to_extra())
    online = await discovery.reconnect(light_id)
    return _lamp_output(request, row, own, online)


async def _lamp_row(request: Request, light_id: str) -> dict[str, Any]:
    row = await get_db(request).load_device(light_id)
    if row is None or row.get("backend") != "govee":
        raise HTTPException(404, f"No Govee lamp '{light_id}'")
    return row


def _lamp_output(
    request: Request, row: dict[str, Any], own: GoveeOutput, online: bool
) -> api.LampOutput:
    override = request.app.state.config.devices.govee.segment_override
    return api.lamp_output_out(row["id"], row.get("sku") or "", own, override, online)
