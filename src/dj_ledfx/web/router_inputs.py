"""The tempo clock's controls and the inputs it reads (web spec §12.3; engine spec §7.2).

Each control is saved before it's answered.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from dj_ledfx.web import contract as api
from dj_ledfx.web.errors import answers
from dj_ledfx.web.state import get_tempo, listening

router = APIRouter()


@router.get("/inputs")
async def get_inputs(request: Request) -> api.Inputs:
    return api.inputs_out(get_tempo(request), listening(request.app))


@router.put("/inputs/tempo")
async def set_tempo(request: Request, body: api.TempoRequest) -> api.TempoInput:
    """Pin a source or go back to Auto. A BPM sets the internal clock."""
    tempo = get_tempo(request)
    with answers():
        tempo.set_tempo(body.lock, body.bpm)
    await tempo.save()
    return api.tempo_out(tempo)


@router.post("/inputs/tempo/tap")
async def tap(request: Request, body: api.TapRequest | None = None) -> api.TempoInput:
    tempo = get_tempo(request)
    with answers():
        tempo.tap(None if body is None else body.client_time)
    await tempo.save()
    return api.tempo_out(tempo)


@router.post("/inputs/tempo/nudge")
async def nudge(request: Request, body: api.NudgeRequest) -> api.TempoInput:
    tempo = get_tempo(request)
    with answers():
        tempo.nudge(body.delta)
    await tempo.save()
    return api.tempo_out(tempo)
