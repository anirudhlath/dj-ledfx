"""Looks: built-in and saved ("Mine"), with stars (web spec §12.3)."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from dj_ledfx.web import contract as api
from dj_ledfx.web.errors import answers
from dj_ledfx.web.state import get_looks

router = APIRouter()


@router.get("/looks")
async def list_looks(request: Request) -> list[api.Look]:
    store = get_looks(request)
    return [api.look_out(look, store.is_starred(look.id)) for look in store.looks()]


@router.get("/looks/{look_id}")
async def get_look(request: Request, look_id: str) -> api.Look:
    store = get_looks(request)
    with answers():
        look = store.get(look_id)
    return api.look_out(look, store.is_starred(look_id))


@router.post("/looks", status_code=201)
async def create_look(request: Request, body: api.Look) -> api.Look:
    """Save a look as a new one ("Mine"). Built-ins are never overwritten."""
    with answers():
        look = await get_looks(request).create(api.look_in(body))
    return api.look_out(look, starred=False)


@router.put("/looks/{look_id}")
async def update_look(request: Request, look_id: str, body: api.Look) -> api.Look:
    store = get_looks(request)
    with answers():
        look = await store.update(look_id, api.look_in(body))
    return api.look_out(look, store.is_starred(look_id))


@router.delete("/looks/{look_id}", status_code=204)
async def delete_look(request: Request, look_id: str) -> Response:
    with answers():
        await get_looks(request).delete(look_id)
    return Response(status_code=204)


@router.put("/looks/{look_id}/starred")
async def set_starred(request: Request, look_id: str, body: api.Starred) -> api.Look:
    store = get_looks(request)
    with answers():
        await store.set_starred(look_id, body.starred)
    return api.look_out(store.get(look_id), body.starred)
