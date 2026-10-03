"""Lights with their status (web spec §9.1, §12.2): the PC is one light with parts (spec
§6.3). A Govee lamp's own output is here too (the light-output plan's ruling 17). Device
actions stay on /api/devices."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from dj_ledfx.devices.govee.output import GoveeOutput, LampOutputReport
from dj_ledfx.web import contract as api
from dj_ledfx.web.state import get_discovery, get_light_monitor, light_index

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
    """A Govee lamp's output: how it plays (razer segments or one colour, and how many
    segments), as its adapter plays while it's online and as a scan will set it up while
    it's offline; and its own setting, which the config and its model fill in."""
    report = await get_discovery(request).output_of(light_id)
    return api.lamp_output_out(_found(report, light_id))


@router.put("/lights/{light_id}/output")
async def set_lamp_output(
    request: Request, light_id: str, body: api.LampOutputSetting
) -> api.LampOutput:
    """Set a Govee lamp's own output; a field left null goes back to the default. A lamp
    that's online plays it at once; one that's offline (online is false) takes it when a
    scan finds it."""
    own = GoveeOutput(mode=body.mode, segments=body.segments)
    report = await get_discovery(request).set_output(light_id, own)
    return api.lamp_output_out(_found(report, light_id))


def _found(report: LampOutputReport | None, light_id: str) -> LampOutputReport:
    if report is None:
        raise HTTPException(404, f"No Govee lamp '{light_id}'")
    return report
