"""The home map and the lights' placements (web spec §8.6, §12.3; engine spec §6).

Every edit goes through the HomeMap, whose listeners move the running zones with it.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response

from dj_ledfx.web import contract as api
from dj_ledfx.web.errors import answers
from dj_ledfx.web.state import get_home_map

router = APIRouter()


@router.get("/home")
async def get_home(request: Request) -> api.Home:
    home_map = get_home_map(request)
    return api.home_out(home_map.home, home_map.rooms_with_lights())


@router.put("/home")
async def update_home(request: Request, body: api.HomeSettings) -> api.Home:
    """North, ceiling, beams and location; only what's sent changes."""
    changes = body.model_dump(mode="json", by_alias=True, exclude_unset=True)
    home_map = get_home_map(request)
    with answers():
        home = await home_map.update(changes)
    return api.home_out(home, home_map.rooms_with_lights())


@router.post("/home/anchors", status_code=201)
async def add_anchor(request: Request, body: api.AnchorIn) -> api.Anchor:
    with answers():
        anchor = await get_home_map(request).add_anchor(body.name, body.position, body.points)
    return api.anchor_out(anchor)


@router.put("/home/anchors/{anchor_id}")
async def update_anchor(request: Request, anchor_id: str, body: api.AnchorUpdate) -> api.Anchor:
    with answers():
        anchor = await get_home_map(request).update_anchor(
            anchor_id,
            name=body.name,
            position=body.position,
            points=body.points,
            confirmed=body.confirmed,
        )
    return api.anchor_out(anchor)


@router.delete("/home/anchors/{anchor_id}", status_code=204)
async def delete_anchor(request: Request, anchor_id: str) -> Response:
    with answers():
        await get_home_map(request).delete_anchor(anchor_id)
    return Response(status_code=204)


@router.post("/home/subzones", status_code=201)
async def add_sub_zone(request: Request, body: api.SubZoneIn) -> api.SubZone:
    with answers():
        sub = await get_home_map(request).add_sub_zone(body.name, body.room, body.polygon)
    return api.sub_zone_out(sub)


@router.put("/home/subzones/{sub_zone_id}")
async def update_sub_zone(
    request: Request, sub_zone_id: str, body: api.SubZoneUpdate
) -> api.SubZone:
    with answers():
        sub = await get_home_map(request).update_sub_zone(
            sub_zone_id, name=body.name, room=body.room, polygon=body.polygon
        )
    return api.sub_zone_out(sub)


@router.delete("/home/subzones/{sub_zone_id}", status_code=204)
async def delete_sub_zone(request: Request, sub_zone_id: str) -> Response:
    """A running sub-zone is turned off and its lights put back (Review Focus 4)."""
    with answers():
        await get_home_map(request).delete_sub_zone(sub_zone_id)
    return Response(status_code=204)


@router.put("/lights/{light_id}/placement")
async def place_light(request: Request, light_id: str, body: api.PlacementIn) -> api.Placement:
    """Place or move a light, or a PC part by its device id (ruling 4). Moving a light
    doesn't confirm it (spec §6.2)."""
    with answers():
        placement = await get_home_map(request).set_placement(
            light_id, api.shape_in(body.shape), body.led_order
        )
    return api.placement_out(placement)


@router.post("/lights/{light_id}/placement/confirm")
async def confirm_placement(request: Request, light_id: str) -> api.Placement:
    with answers():
        placement = await get_home_map(request).confirm(light_id)
    return api.placement_out(placement)


@router.delete("/lights/{light_id}/placement", status_code=204)
async def remove_placement(request: Request, light_id: str) -> Response:
    """Take a light off the map (§8.6's "Remove from the map")."""
    with answers():
        await get_home_map(request).remove_placement(light_id)
    return Response(status_code=204)


@router.post("/lights/placement/guess")
async def guess_placements(request: Request) -> dict[str, api.Placement]:
    """Spread the unplaced lights around their rooms, unconfirmed (spec §6.2)."""
    with answers():
        guesses = await get_home_map(request).guess()
    return {target: api.placement_out(placement) for target, placement in guesses.items()}
