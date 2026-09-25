"""Home maps for tests.

tiny_home() is two 4 x 4 m rooms side by side, west and east, with a desk corner in the
west one, a sofa anchor and a speaker pair in the east one. Task 20 adds this home's
lights from the vendored home.json.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from dj_ledfx.home.model import Anchor, Box2, Furniture, Home, Location, Room, SubZone, Wall

WEST = ((0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0))
EAST = ((4.0, 0.0), (8.0, 0.0), (8.0, 4.0), (4.0, 4.0))
DESK = ((0.0, 3.0), (2.0, 3.0), (2.0, 4.0), (0.0, 4.0))


def tiny_home(**changes: Any) -> Home:
    home = Home(
        outline=((0.0, 0.0), (8.0, 0.0), (8.0, 4.0), (0.0, 4.0)),
        rooms=(
            Room("west", "West room", WEST, (2.0, 2.0)),
            Room("east", "East room", EAST, (6.0, 2.0)),
        ),
        sub_zones=(SubZone("desk", "Desk", "west", DESK),),
        walls=(
            Wall((0.0, 0.0), (0.0, 4.0), "window", west_facing=True, exterior=True, thickness=0.2),
            Wall((4.0, 0.0), (4.0, 4.0), "wall", west_facing=False, exterior=False, thickness=0.1),
        ),
        columns=(Box2((3.9, 0.0), (4.1, 0.2)),),
        furniture=(Furniture("table", "Table", 0.7, box=(5.0, 1.0, 6.0, 2.0)),),
        anchors=(
            Anchor("sofa", "Sofa", (6.0, 2.0, 0.5)),
            Anchor("speakers", "Speakers", (7.5, 2.0, 1.0), ((7.5, 1.0, 1.0), (7.5, 3.0, 1.0))),
        ),
        ceiling=3.0,
        beams=2.8,
        wall_cut_height=1.0,
        location=Location("Test", 10.0, 20.0),
    )
    return replace(home, **changes)
