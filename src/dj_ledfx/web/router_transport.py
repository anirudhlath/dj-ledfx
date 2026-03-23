"""Transport state REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request

from dj_ledfx.web.schemas import TransportBody, TransportResponse

router = APIRouter()


@router.get("/transport")
async def get_transport(request: Request) -> TransportResponse:
    engine = request.app.state.effect_engine
    return TransportResponse(state=engine.transport_state)


@router.put("/transport")
async def put_transport(request: Request, body: TransportBody) -> TransportResponse:
    engine = request.app.state.effect_engine
    engine.set_transport_state(body.state)
    return TransportResponse(state=engine.transport_state)
