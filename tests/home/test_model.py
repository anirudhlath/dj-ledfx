from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from map_home import tiny_home

from dj_ledfx.home.model import HomeError, home_from_dict, home_to_dict

HANDOFF = Path(__file__).parents[2] / "docs" / "design" / "web-app" / "home.json"
MODELLED = (
    "outline",
    "subZones",
    "walls",
    "columns",
    "furniture",
    "anchors",
    "ceiling",
    "beams",
    "wallCutHeight",
    "size",
    "northOffsetDeg",
    "location",
    "outdoor",
)


def _handoff() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(HANDOFF.read_bytes())
    return data


def test_the_handoff_map_reads_and_writes_back_in_its_own_shape() -> None:
    raw = _handoff()
    out = home_to_dict(home_from_dict(raw))
    for key in MODELLED:
        assert out[key] == raw[key], key
    room_keys = ("id", "name", "polygon", "labelAt")
    assert out["rooms"] == [{key: room[key] for key in room_keys} for room in raw["rooms"]]


def test_a_map_survives_a_round_trip() -> None:
    home = tiny_home()
    assert home_from_dict(home_to_dict(home)) == home


def test_a_map_without_a_location_writes_none() -> None:
    out = home_to_dict(tiny_home(location=None))
    assert "location" not in out
    assert home_from_dict(out).location is None


def test_lookups_by_id() -> None:
    home = tiny_home()
    assert home.room("west") is not None and home.room("nope") is None
    assert home.sub_zone("desk") is not None and home.sub_zone("west") is None
    speakers = home.anchor("speakers")
    assert speakers is not None and len(speakers.points) == 2


def test_the_north_offset_is_kept_within_a_turn() -> None:
    data = home_to_dict(tiny_home())
    data["northOffsetDeg"] = -90
    assert home_from_dict(data).north_offset_deg == 270.0


Change = Callable[[dict[str, Any]], object]


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        (lambda d: d.pop("rooms"), "'rooms' must be a list"),
        (lambda d: d.update(rooms=[]), "at least one room"),
        (lambda d: d["rooms"][0].update(polygon=[[0, 0], [1, 1]]), "at least 3 points"),
        (lambda d: d.update(ceiling=float("nan")), "finite number"),
        (lambda d: d.update(ceiling=0), "greater than 0"),
        (lambda d: d["subZones"][0].update(room="attic"), "unknown room"),
        (lambda d: d["rooms"].append(dict(d["rooms"][0])), "share the id"),
        (lambda d: d["subZones"][0].update(id="west"), "share the id"),
        (lambda d: d["anchors"][0].update(position=[1, 2]), "3 numbers"),
        (lambda d: d["walls"][0].update(kind="door"), "wall kind"),
        (lambda d: d["furniture"][0].pop("box"), "box or a polygon"),
        (lambda d: d.update(location={"name": "Home", "lat": 91, "lon": 0}), "latitude"),
        (lambda d: d.update(outline="square"), "at least 3 points"),
        (lambda d: d.update(size={"eastWest": 0, "northSouth": 4}), "greater than 0"),
        (lambda d: d.update(size=[8, 4]), "The size must be an object"),
    ],
)
def test_bad_maps_are_refused_with_the_reason(change: Change, reason: str) -> None:
    data = home_to_dict(tiny_home())
    change(data)
    with pytest.raises(HomeError, match=reason):
        home_from_dict(data)


def test_a_map_that_is_not_an_object_is_refused() -> None:
    with pytest.raises(HomeError, match="must be an object"):
        home_from_dict([])  # type: ignore[arg-type]


def test_a_map_without_a_size_takes_its_outlines_extent() -> None:
    data = home_to_dict(tiny_home())
    del data["size"]
    assert home_from_dict(data).size == (8.0, 4.0)  # tiny_home's outline, east-west first
