"""What needs the owner's attention, derived on the server (web spec §9.5)."""

from __future__ import annotations

from fastapi import APIRouter, Request

from dj_ledfx.web import contract as api
from dj_ledfx.web.state import get_attention

router = APIRouter()


@router.get("/attention")
async def list_attention(request: Request) -> list[api.AttentionItem]:
    return [api.attention_out(item) for item in get_attention(request).items()]
