"""The home map (engine spec §6.1; web spec §7.1, §12.2), in home.json's own shape.

Metres on the plan's axes: x east, y south, z up, with the origin at the plan's north-west
corner. home_from_dict reads everything the handoff's home.json holds apart from its
lights, which only seed placements (home/seed.py). home_to_dict writes the same shape back,
so the stored map and the file read the same way.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, cast, get_args

Vec2 = tuple[float, float]
Vec3 = tuple[float, float, float]
WallKind = Literal["wall", "window", "glass-door"]


class HomeError(ValueError):
    """A home map, or a change to it, that can't be used, with the reason."""


class HomeNotFoundError(KeyError):
    """No room, sub-zone, anchor or light has that id; args[0] says what was asked for."""


@dataclass(frozen=True, slots=True)
class Room:
    id: str
    name: str
    polygon: tuple[Vec2, ...]
    label_at: Vec2  # a point inside the room: its label, and its centre for guesses


@dataclass(frozen=True, slots=True)
class SubZone:
    id: str
    name: str
    room: str
    polygon: tuple[Vec2, ...]


@dataclass(frozen=True, slots=True)
class Anchor:
    id: str
    name: str
    position: Vec3
    points: tuple[Vec3, ...] = ()  # a pair like the speakers; empty for one point
    confirmed: bool = False


@dataclass(frozen=True, slots=True)
class Wall:
    a: Vec2
    b: Vec2
    kind: WallKind
    west_facing: bool
    exterior: bool
    thickness: float


@dataclass(frozen=True, slots=True)
class Box2:
    min: Vec2
    max: Vec2


@dataclass(frozen=True, slots=True)
class Furniture:
    id: str
    name: str
    height: float
    z0: float = 0.0
    confirmed: bool = False
    box: tuple[float, float, float, float] | None = None  # x0, y0, x1, y1
    polygon: tuple[Vec2, ...] | None = None


@dataclass(frozen=True, slots=True)
class Location:
    name: str
    lat: float
    lon: float
    confirmed: bool = False


@dataclass(frozen=True, slots=True)
class Outdoor:
    courtyard: tuple[Vec2, ...] = ()
    balcony: tuple[Vec2, ...] = ()
    courtyard_opens_to: str = ""
    balcony_off_room: str = ""


@dataclass(frozen=True, slots=True)
class Home:
    outline: tuple[Vec2, ...]
    rooms: tuple[Room, ...]
    sub_zones: tuple[SubZone, ...]
    walls: tuple[Wall, ...]
    columns: tuple[Box2, ...]
    furniture: tuple[Furniture, ...]
    anchors: tuple[Anchor, ...]
    ceiling: float
    beams: float
    wall_cut_height: float
    size: Vec2  # east-west, north-south, in metres
    north_offset_deg: float = 0.0
    location: Location | None = None
    outdoor: Outdoor = Outdoor()

    def room(self, room_id: str) -> Room | None:
        return next((room for room in self.rooms if room.id == room_id), None)

    def sub_zone(self, sub_zone_id: str) -> SubZone | None:
        return next((sub for sub in self.sub_zones if sub.id == sub_zone_id), None)

    def anchor(self, anchor_id: str) -> Anchor | None:
        return next((anchor for anchor in self.anchors if anchor.id == anchor_id), None)


# --- reading -------------------------------------------------------------------------


def finite(value: Any, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise HomeError(f"{what} must be a finite number")
    return float(value)


def _positive(value: Any, what: str) -> float:
    number = finite(value, what)
    if number <= 0.0:
        raise HomeError(f"{what} must be greater than 0")
    return number


def _text(value: Any, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise HomeError(f"{what} must be a non-empty string")
    return value.strip()


def _numbers(value: Any, size: int, what: str) -> tuple[float, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence) or len(value) != size:
        raise HomeError(f"{what} must be {size} numbers")
    return tuple(finite(item, what) for item in value)


def vec2(value: Any, what: str) -> Vec2:
    x, y = _numbers(value, 2, what)
    return (x, y)


def vec3(value: Any, what: str) -> Vec3:
    x, y, z = _numbers(value, 3, what)
    return (x, y, z)


def polygon_of(value: Any, what: str) -> tuple[Vec2, ...]:
    if isinstance(value, str) or not isinstance(value, Sequence) or len(value) < 3:
        raise HomeError(f"{what} needs at least 3 points")
    return tuple(vec2(point, what) for point in value)


def _object(value: Any, what: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise HomeError(f"{what} must be an object")
    return value


def _list(data: Mapping[str, Any], key: str, *, required: bool = False) -> list[Any]:
    value = data.get(key)
    if value is None and not required:
        return []
    if not isinstance(value, list):
        raise HomeError(f"'{key}' must be a list")
    return value


def _unique(ids: Sequence[str], what: str) -> None:
    seen: set[str] = set()
    for item in ids:
        if item in seen:
            raise HomeError(f"Two {what}s share the id '{item}'")
        seen.add(item)


def _room(data: Mapping[str, Any]) -> Room:
    room_id = _text(data.get("id"), "A room's id")
    return Room(
        id=room_id,
        name=_text(data.get("name"), f"Room '{room_id}'s name"),
        polygon=polygon_of(data.get("polygon"), f"Room '{room_id}'"),
        label_at=vec2(data.get("labelAt"), f"Room '{room_id}'s label point"),
    )


def _sub_zone(data: Mapping[str, Any]) -> SubZone:
    sub_id = _text(data.get("id"), "A sub-zone's id")
    return SubZone(
        id=sub_id,
        name=_text(data.get("name"), f"Sub-zone '{sub_id}'s name"),
        room=_text(data.get("room"), f"Sub-zone '{sub_id}'s room"),
        polygon=polygon_of(data.get("polygon"), f"Sub-zone '{sub_id}'"),
    )


def _anchor(data: Mapping[str, Any]) -> Anchor:
    anchor_id = _text(data.get("id"), "An anchor's id")
    what = f"Anchor '{anchor_id}'s position"
    points = data.get("points") or []
    if not isinstance(points, list):
        raise HomeError(f"Anchor '{anchor_id}'s points must be a list")
    return Anchor(
        id=anchor_id,
        name=_text(data.get("name"), f"Anchor '{anchor_id}'s name"),
        position=vec3(data.get("position"), what),
        points=tuple(vec3(point, what) for point in points),
        confirmed=bool(data.get("confirmed", False)),
    )


def _wall(data: Mapping[str, Any]) -> Wall:
    kind = data.get("kind", "wall")
    if kind not in get_args(WallKind):
        raise HomeError(
            f"Unknown wall kind {kind!r}; expected one of {', '.join(get_args(WallKind))}"
        )
    thickness = finite(data.get("thickness"), "A wall's thickness")
    if thickness < 0.0:
        raise HomeError("A wall's thickness can't be negative")
    return Wall(
        a=vec2(data.get("a"), "A wall's end"),
        b=vec2(data.get("b"), "A wall's end"),
        kind=cast(WallKind, kind),
        west_facing=bool(data.get("westFacing", False)),
        exterior=bool(data.get("exterior", False)),
        thickness=thickness,
    )


def _box(data: Mapping[str, Any]) -> Box2:
    return Box2(
        min=vec2(data.get("min"), "A column's corner"),
        max=vec2(data.get("max"), "A column's corner"),
    )


def _furniture(data: Mapping[str, Any]) -> Furniture:
    item_id = _text(data.get("id"), "A piece of furniture's id")
    box = data.get("box")
    shape = data.get("polygon")
    if box is None and shape is None:
        raise HomeError(f"Furniture '{item_id}' needs a box or a polygon")
    height = finite(data.get("height"), f"Furniture '{item_id}'s height")
    if height < 0.0:
        raise HomeError(f"Furniture '{item_id}'s height can't be negative")
    x0, y0, x1, y1 = (
        _numbers(box, 4, f"Furniture '{item_id}'s box") if box is not None else (0, 0, 0, 0)
    )
    return Furniture(
        id=item_id,
        name=_text(data.get("name"), f"Furniture '{item_id}'s name"),
        height=height,
        z0=finite(data.get("z0", 0.0), f"Furniture '{item_id}'s base"),
        confirmed=bool(data.get("confirmed", False)),
        box=(x0, y0, x1, y1) if box is not None else None,
        polygon=polygon_of(shape, f"Furniture '{item_id}'") if shape is not None else None,
    )


def _location(value: Any) -> Location | None:
    if value is None:
        return None
    data = _object(value, "The location")
    lat = finite(data.get("lat"), "The latitude")
    lon = finite(data.get("lon"), "The longitude")
    if not -90.0 <= lat <= 90.0:
        raise HomeError("The latitude must be between -90 and 90")
    if not -180.0 <= lon <= 180.0:
        raise HomeError("The longitude must be between -180 and 180")
    return Location(
        name=_text(data.get("name"), "The location's name"),
        lat=lat,
        lon=lon,
        confirmed=bool(data.get("confirmed", False)),
    )


def _size(value: Any, outline: tuple[Vec2, ...]) -> Vec2:
    """home.json's size, or, for a map without one, its outline's extent."""
    if value is None:
        xs, ys = [x for x, _ in outline], [y for _, y in outline]
        return (max(xs) - min(xs), max(ys) - min(ys))
    data = _object(value, "The size")
    return (
        _positive(data.get("eastWest"), "The size east to west"),
        _positive(data.get("northSouth"), "The size north to south"),
    )


def _outdoor(value: Any) -> Outdoor:
    if value is None:
        return Outdoor()
    data = _object(value, "The outdoor areas")
    courtyard, balcony = data.get("courtyard"), data.get("balcony")
    return Outdoor(
        courtyard=polygon_of(courtyard, "The courtyard") if courtyard else (),
        balcony=polygon_of(balcony, "The balcony") if balcony else (),
        courtyard_opens_to=str(data.get("courtyardOpensTo") or ""),
        balcony_off_room=str(data.get("balconyOffRoom") or ""),
    )


def home_from_dict(data: Mapping[str, Any]) -> Home:
    """Read a map in home.json's shape. Raises HomeError, naming the field, when it can't."""
    data = _object(data, "The home map")
    rooms = tuple(_room(_object(item, "A room")) for item in _list(data, "rooms", required=True))
    if not rooms:
        raise HomeError("A home map needs at least one room")
    room_ids = [room.id for room in rooms]
    _unique(room_ids, "room")
    subs = tuple(_sub_zone(_object(item, "A sub-zone")) for item in _list(data, "subZones"))
    _unique([*room_ids, *(sub.id for sub in subs)], "room or sub-zone")
    for sub in subs:
        if sub.room not in room_ids:
            raise HomeError(f"Sub-zone '{sub.id}' is in an unknown room '{sub.room}'")
    anchors = tuple(_anchor(_object(item, "An anchor")) for item in _list(data, "anchors"))
    _unique([anchor.id for anchor in anchors], "anchor")
    outline = polygon_of(data.get("outline"), "The outline")
    return Home(
        outline=outline,
        rooms=rooms,
        sub_zones=subs,
        walls=tuple(_wall(_object(item, "A wall")) for item in _list(data, "walls")),
        columns=tuple(_box(_object(item, "A column")) for item in _list(data, "columns")),
        furniture=tuple(
            _furniture(_object(item, "A piece of furniture")) for item in _list(data, "furniture")
        ),
        anchors=anchors,
        ceiling=_positive(data.get("ceiling"), "The ceiling"),
        beams=_positive(data.get("beams"), "The beams"),
        wall_cut_height=_positive(data.get("wallCutHeight"), "The wall cut height"),
        size=_size(data.get("size"), outline),
        north_offset_deg=finite(data.get("northOffsetDeg", 0.0), "The north offset") % 360.0,
        location=_location(data.get("location")),
        outdoor=_outdoor(data.get("outdoor")),
    )


# --- writing -------------------------------------------------------------------------


def _points(points: Sequence[Sequence[float]]) -> list[list[float]]:
    return [list(point) for point in points]


def _anchor_dict(anchor: Anchor) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": anchor.id,
        "name": anchor.name,
        "position": list(anchor.position),
        "confirmed": anchor.confirmed,
    }
    if anchor.points:
        data["points"] = _points(anchor.points)
    return data


def _furniture_dict(item: Furniture) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": item.id,
        "name": item.name,
        "height": item.height,
        "z0": item.z0,
        "confirmed": item.confirmed,
    }
    if item.box is not None:
        data["box"] = list(item.box)
    if item.polygon is not None:
        data["polygon"] = _points(item.polygon)
    return data


def home_to_dict(home: Home) -> dict[str, Any]:
    """The map in home.json's shape (its lights and totals aside)."""
    data: dict[str, Any] = {
        "outline": _points(home.outline),
        "rooms": [
            {
                "id": room.id,
                "name": room.name,
                "polygon": _points(room.polygon),
                "labelAt": list(room.label_at),
            }
            for room in home.rooms
        ],
        "subZones": [
            {"id": sub.id, "name": sub.name, "room": sub.room, "polygon": _points(sub.polygon)}
            for sub in home.sub_zones
        ],
        "walls": [
            {
                "a": list(wall.a),
                "b": list(wall.b),
                "kind": wall.kind,
                "westFacing": wall.west_facing,
                "exterior": wall.exterior,
                "thickness": wall.thickness,
            }
            for wall in home.walls
        ],
        "columns": [{"min": list(box.min), "max": list(box.max)} for box in home.columns],
        "furniture": [_furniture_dict(item) for item in home.furniture],
        "anchors": [_anchor_dict(anchor) for anchor in home.anchors],
        "ceiling": home.ceiling,
        "beams": home.beams,
        "wallCutHeight": home.wall_cut_height,
        "size": {"eastWest": home.size[0], "northSouth": home.size[1]},
        "northOffsetDeg": home.north_offset_deg,
        "outdoor": {
            "courtyard": _points(home.outdoor.courtyard),
            "balcony": _points(home.outdoor.balcony),
            "courtyardOpensTo": home.outdoor.courtyard_opens_to,
            "balconyOffRoom": home.outdoor.balcony_off_room,
        },
    }
    if home.location is not None:
        data["location"] = {
            "name": home.location.name,
            "lat": home.location.lat,
            "lon": home.location.lon,
            "confirmed": home.location.confirmed,
        }
    return data
