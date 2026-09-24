"""Looks: built-in and saved ("Mine"), with stars (web spec §12.3)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response

from dj_ledfx.looks.model import BuiltInLookError, LookError, LookNotFoundError
from dj_ledfx.web import contract as api
from dj_ledfx.web.state import get_looks

router = APIRouter()


def _not_found(look_id: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"No look '{look_id}'")


@router.get("/looks")
async def list_looks(request: Request) -> list[api.Look]:
    store = get_looks(request)
    return [api.look_out(look, store.is_starred(look.id)) for look in store.looks()]


@router.get("/looks/{look_id}")
async def get_look(request: Request, look_id: str) -> api.Look:
    store = get_looks(request)
    try:
        look = store.get(look_id)
    except LookNotFoundError:
        raise _not_found(look_id) from None
    return api.look_out(look, store.is_starred(look_id))


@router.post("/looks", status_code=201)
async def create_look(request: Request, body: api.Look) -> api.Look:
    """Save a look as a new one ("Mine"). Built-ins are never overwritten."""
    store = get_looks(request)
    try:
        look = await store.create(api.look_in(body))
    except LookError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return api.look_out(look, starred=False)


@router.put("/looks/{look_id}")
async def update_look(request: Request, look_id: str, body: api.Look) -> api.Look:
    store = get_looks(request)
    try:
        look = await store.update(look_id, api.look_in(body))
    except LookNotFoundError:
        raise _not_found(look_id) from None
    except BuiltInLookError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LookError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return api.look_out(look, store.is_starred(look_id))


@router.delete("/looks/{look_id}", status_code=204)
async def delete_look(request: Request, look_id: str) -> Response:
    store = get_looks(request)
    try:
        await store.delete(look_id)
    except LookNotFoundError:
        raise _not_found(look_id) from None
    except BuiltInLookError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(status_code=204)


@router.put("/looks/{look_id}/starred")
async def set_starred(request: Request, look_id: str, body: api.Starred) -> api.Look:
    store = get_looks(request)
    try:
        await store.set_starred(look_id, body.starred)
    except LookNotFoundError:
        raise _not_found(look_id) from None
    return api.look_out(store.get(look_id), body.starred)
