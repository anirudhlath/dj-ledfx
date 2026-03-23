"""Transport state REST endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, field_validator

from dj_ledfx.transport import TransportState

router = APIRouter()


class TransportBody(BaseModel):
    state: str

    @field_validator("state")
    @classmethod
    def validate_state(cls, v: str) -> str:
        valid = {s.value for s in TransportState}
        if v not in valid:
            msg = f"Invalid state: {v!r}. Must be one of {sorted(valid)}"
            raise ValueError(msg)
        return v


class TransportResponse(BaseModel):
    state: str


@router.get("/transport")
async def get_transport(request: Request) -> TransportResponse:
    engine = request.app.state.effect_engine
    return TransportResponse(state=engine.transport_state.value)


@router.put("/transport")
async def put_transport(request: Request, body: TransportBody) -> TransportResponse:
    engine = request.app.state.effect_engine
    engine.set_transport_state(TransportState(body.state))
    return TransportResponse(state=engine.transport_state.value)
