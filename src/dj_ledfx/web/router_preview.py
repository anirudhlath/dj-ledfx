"""Show a look on a zone in the web app only (spec §4.1; web spec §12.3).

The frames go out on the WebSocket's preview stream (frame v2). Nothing reaches a light.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from dj_ledfx.web import contract as api
from dj_ledfx.web.errors import answers
from dj_ledfx.web.router_zones import requested_look
from dj_ledfx.web.state import get_previews

router = APIRouter()


@router.post("/preview", status_code=201)
async def start_preview(request: Request, body: api.PreviewRequest) -> api.PreviewStarted:
    """Replaces any previous preview. A request that fails leaves it as it was."""
    with answers():
        look = requested_look(request, body.look_id, body.look)
        preview_id = get_previews(request).start(body.zone_id, look)
    return api.PreviewStarted(preview_id=preview_id)


@router.put("/preview/{preview_id}", status_code=204)
async def update_preview(request: Request, preview_id: str, body: api.PreviewUpdate) -> Response:
    """The editor's live edits: taken in place where the layers allow."""
    with answers():
        look = requested_look(request, None, body.look)
        get_previews(request).update(preview_id, look)
    return Response(status_code=204)


@router.delete("/preview/{preview_id}", status_code=204)
async def stop_preview(request: Request, preview_id: str) -> Response:
    with answers():
        get_previews(request).stop(preview_id)
    return Response(status_code=204)
