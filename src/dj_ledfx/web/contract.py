"""The web app's data contract (web spec §12.2) as Pydantic models.

Fields are snake_case here and camelCase on the wire. Class names are the contract's:
the web app generates its types from the OpenAPI schema (spec §9).
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping, Sequence
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from dj_ledfx.devices.capabilities import DeviceCapabilities, LightProtocol
from dj_ledfx.devices.lights import LightEntry, LightIndex
from dj_ledfx.devices.manager import ManagedDevice
from dj_ledfx.effects.color import rgb_to_hex
from dj_ledfx.effects.firmware import FirmwareEffect
from dj_ledfx.effects.registry import get_effect_classes
from dj_ledfx.home import model as home_model
from dj_ledfx.home import shapes
from dj_ledfx.home.map import HomeMap
from dj_ledfx.home.model import WallKind
from dj_ledfx.looks import model as looks
from dj_ledfx.looks.model import Blend, Category, InputKind, LayerType, Scope, TransitionKind
from dj_ledfx.types import RGB, DeviceStats
from dj_ledfx.zones import attention
from dj_ledfx.zones.attention import AttentionAction, AttentionKind, Severity, SubjectType
from dj_ledfx.zones.lights import LightState, LightStatus
from dj_ledfx.zones.model import (
    RecentLookInfo,
    RunningZoneInfo,
    StartResult,
    ZoneKind,
    ZoneRecord,
)
from dj_ledfx.zones.runtime import ZoneState


class ContractModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


# --- looks -------------------------------------------------------------------------


class SettingValue(ContractModel):
    value: Any
    binding: dict[str, Any] | None = None  # bindings arrive in M7


class SettingSchema(ContractModel):
    key: str
    label: str
    unit: str | None = None
    bindable: bool = False
    type: Literal[
        "number",
        "colour",
        "palette",
        "anchor",
        "point",
        "zone",
        "lights",
        "range",
        "boolean",
        "choice",
    ]
    min: float | None = None
    max: float | None = None
    step: float | None = None
    options: list[str] | None = None


class Layer(ContractModel):
    id: str
    name: str
    type: LayerType
    kind: str
    visible: bool = True
    blend: Blend = "normal"
    opacity: float = 1.0
    settings: dict[str, SettingValue] = Field(default_factory=dict)
    setting_schema: list[SettingSchema] = Field(default_factory=list, alias="schema")
    mask: dict[str, Any] | None = None
    mirror: dict[str, Any] | None = None
    transform: dict[str, Any] | None = None


class LookModifiers(ContractModel):
    trails_s: float | None = None
    downbeat_flash: bool = False
    brightness_cap: float | None = None
    evening: bool = False


class Transition(ContractModel):
    kind: TransitionKind = "cut"
    duration_s: float = 0.0


class Look(ContractModel):
    id: str = ""
    name: str
    category: Category
    built_in: bool = False
    derived_from: str | None = None
    description: str = ""
    thumbnail: str = ""
    scope: Scope = "any-zone"
    needs: list[InputKind] = Field(default_factory=list)
    uses: list[InputKind] = Field(default_factory=list)
    starred: bool = False
    layers: list[Layer] = Field(default_factory=list)
    modifiers: LookModifiers = Field(default_factory=LookModifiers)
    transition: Transition = Field(default_factory=Transition)


class Starred(ContractModel):
    starred: bool


def look_out(look: looks.Look, starred: bool) -> Look:
    return Look.model_validate(looks.look_to_dict(look, starred=starred))


def look_in(body: Look) -> looks.Look:
    """The look a request describes. Raises LookError when M1 can't read it."""
    return looks.look_from_dict(body.model_dump(by_alias=True))


# --- zones -------------------------------------------------------------------------


class Zone(ContractModel):
    id: str
    name: str
    kind: ZoneKind
    lights: list[str]


class RunningZoneTransition(ContractModel):
    from_: str = Field(alias="from")
    kind: TransitionKind
    progress: float


class RunningZoneFps(ContractModel):
    actual: float
    target: int


class RunningZoneError(ContractModel):
    layer: str
    message: str
    at: datetime


class RunningZone(ContractModel):
    zone_id: str
    look_id: str
    look_name: str
    since: datetime
    brightness: float
    lights: list[str]  # the lights it owns after take-overs
    # the rooms it still covers, by name, in map order
    covers: list[str] = Field(default_factory=list)
    state: Literal[ZoneState, "transition"]  # transitions arrive in M4
    transition: RunningZoneTransition | None = None  # transitions arrive in M4
    fps: RunningZoneFps | None = None
    error: RunningZoneError | None = None
    waiting_for: list[InputKind] | None = None


class Overlay(ContractModel):
    look_id: str
    name: str
    trigger: str
    ends_at: datetime
    progress: float


class Running(ContractModel):
    zones: list[RunningZone]
    overlays: list[Overlay] = Field(default_factory=list)  # overlays arrive in M6


class TakeOver(ContractModel):
    zone_id: str
    zone_name: str
    look_name: str
    lights: list[str]  # the lights it lost
    stopped: bool  # it had none left, so it stopped


class RecentLook(ContractModel):
    """A look that stopped, for "Start again" (web spec §9.4). §12.2 has no such type: the
    M2 plan's ruling 19 shapes it, and F1 types it by hand until the backend serves it."""

    zone_id: str
    zone_name: str
    look_id: str
    look_name: str
    started_at: datetime
    stopped_at: datetime


class StartRequest(ContractModel):
    look_id: str | None = None
    look: Look | None = None  # an unsaved draft
    transition: Transition | None = None  # accepted; M1 plays every transition as a cut


class StartResponse(RunningZone):
    take_overs: list[TakeOver] = Field(default_factory=list)


class Brightness(ContractModel):
    value: float


class CreateGroup(ContractModel):
    name: str
    lights: list[str]


class UpdateGroup(ContractModel):
    name: str | None = None
    lights: list[str] | None = None


def zone_out(zone: ZoneRecord, index: LightIndex) -> Zone:
    return Zone(
        id=zone.id, name=zone.name, kind=zone.kind, lights=list(index.collapse(zone.lights))
    )


def _running_fields(info: RunningZoneInfo, index: LightIndex) -> dict[str, Any]:
    fps = None
    if info.fps_actual is not None and info.fps_target is not None:
        fps = {"actual": round(info.fps_actual, 1), "target": info.fps_target}
    error = None
    if info.error is not None:
        error = {"layer": info.error.layer, "message": info.error.message, "at": info.error.at}
    return {
        "zone_id": info.zone_id,
        "look_id": info.look_id,
        "look_name": info.look_name,
        "since": info.since,
        "brightness": info.brightness,
        "lights": list(index.collapse(info.lights)),
        "covers": list(info.covers),
        "state": info.state,
        "fps": fps,
        "error": error,
        "waiting_for": list(info.waiting_for) or None,
    }


def running_zone_out(info: RunningZoneInfo, index: LightIndex) -> RunningZone:
    return RunningZone.model_validate(_running_fields(info, index))


def running_out(infos: Iterable[RunningZoneInfo], index: LightIndex) -> Running:
    return Running(zones=[running_zone_out(info, index) for info in infos])


def start_out(result: StartResult, index: LightIndex) -> StartResponse:
    take_overs = [
        {
            "zone_id": take_over.zone_id,
            "zone_name": take_over.zone_name,
            "look_name": take_over.look_name,
            "lights": list(index.collapse(take_over.lights)),
            "stopped": take_over.stopped,
        }
        for take_over in result.take_overs
    ]
    fields = {**_running_fields(result.running, index), "take_overs": take_overs}
    return StartResponse.model_validate(fields)


def recent_look_out(info: RecentLookInfo) -> RecentLook:
    return RecentLook.model_validate(info, from_attributes=True)


# --- preview (web spec §12.3) -----------------------------------------------------------


class PreviewRequest(ContractModel):
    zone_id: str
    look_id: str | None = None
    look: Look | None = None  # an unsaved draft


class PreviewStarted(ContractModel):
    preview_id: str


class PreviewUpdate(ContractModel):
    look: Look  # the editor's look as it is now, saved or not


# --- the home map (web spec §12.2) ------------------------------------------------------

Vec2 = tuple[float, float]
Vec3 = tuple[float, float, float]


class Room(ContractModel):
    id: str
    name: str
    polygon: list[Vec2]
    label_at: Vec2
    has_lights: bool  # whether any light is placed in it now (F1's Room)


class SubZone(ContractModel):
    id: str
    name: str
    room: str
    polygon: list[Vec2]


class Anchor(ContractModel):
    id: str
    name: str
    position: Vec3
    points: list[Vec3] | None = None
    confirmed: bool = False


class Wall(ContractModel):
    a: Vec2
    b: Vec2
    kind: WallKind
    west_facing: bool
    exterior: bool
    thickness: float


class Box2(ContractModel):
    min: Vec2
    max: Vec2


class Furniture(ContractModel):
    id: str
    name: str
    height: float
    z0: float = 0.0
    confirmed: bool = False
    box: tuple[float, float, float, float] | None = None  # x0, y0, x1, y1
    polygon: list[Vec2] | None = None


class Location(ContractModel):
    name: str
    lat: float
    lon: float
    confirmed: bool = False


class Outdoor(ContractModel):
    courtyard: list[Vec2] = Field(default_factory=list)
    balcony: list[Vec2] = Field(default_factory=list)
    courtyard_opens_to: str = ""
    balcony_off_room: str = ""


class HomeSize(ContractModel):
    east_west: float
    north_south: float


class Home(ContractModel):
    outline: list[Vec2]
    rooms: list[Room]
    sub_zones: list[SubZone]
    walls: list[Wall]
    columns: list[Box2]
    furniture: list[Furniture]  # read-only in M2 (ruling 10)
    anchors: list[Anchor]
    ceiling: float
    beams: float
    wall_cut_height: float
    size: HomeSize
    north_offset_deg: float
    location: Location | None = None
    outdoor: Outdoor = Field(default_factory=Outdoor)


class HomeSettings(ContractModel):
    """PUT /home: only what's sent changes."""

    north_offset_deg: float | None = None
    ceiling: float | None = None
    beams: float | None = None
    location: Location | None = None


class AnchorIn(ContractModel):
    name: str
    position: Vec3
    points: list[Vec3] = Field(default_factory=list)


class AnchorUpdate(ContractModel):
    name: str | None = None
    position: Vec3 | None = None
    points: list[Vec3] | None = None
    confirmed: bool | None = None


class SubZoneIn(ContractModel):
    name: str
    room: str
    polygon: list[Vec2]


class SubZoneUpdate(ContractModel):
    name: str | None = None
    room: str | None = None
    polygon: list[Vec2] | None = None


class PointShape(ContractModel):
    kind: Literal["point"]
    position: Vec3


class LineShape(ContractModel):
    kind: Literal["line"]
    path: tuple[Vec3, Vec3]


class BentLineShape(ContractModel):
    kind: Literal["bent-line"]
    path: list[Vec3]


class CylinderShape(ContractModel):
    kind: Literal["cylinder"]
    base: Vec3
    height: float
    radius: float


class GridShape(ContractModel):
    kind: Literal["grid"]
    center: Vec3
    width: float
    depth: float
    rotation: Vec3 = (0.0, 0.0, 0.0)  # turn, tilt, roll in degrees; only a grid has one


AnyShape = PointShape | LineShape | BentLineShape | CylinderShape | GridShape
LightShape = Annotated[AnyShape, Field(discriminator="kind")]


class PlacementIn(ContractModel):
    """PUT /lights/{id}/placement (ruling 16). Without ledOrder, a shape of the same kind
    keeps its order and a new kind takes its first."""

    shape: LightShape
    led_order: str | None = None


class Placement(ContractModel):
    shape: LightShape
    led_order: str
    confirmed: bool
    confirmed_at: datetime | None = None


def home_out(home: home_model.Home, rooms_with_lights: Collection[str]) -> Home:
    data = home_model.home_to_dict(home)
    for room in data["rooms"]:
        room["hasLights"] = room["id"] in rooms_with_lights
    return Home.model_validate(data)


def anchor_out(anchor: home_model.Anchor) -> Anchor:
    return Anchor(
        id=anchor.id,
        name=anchor.name,
        position=anchor.position,
        points=list(anchor.points) or None,
        confirmed=anchor.confirmed,
    )


def sub_zone_out(sub: home_model.SubZone) -> SubZone:
    return SubZone.model_validate(sub, from_attributes=True)


def shape_in(shape: AnyShape) -> shapes.LightShape:
    """The engine's shape; shape_from_dict checks what Pydantic can't (ShapeError: 400)."""
    return shapes.shape_from_dict(shape.model_dump(by_alias=True))


def placement_out(placement: shapes.Placement) -> Placement:
    return Placement.model_validate(shapes.placement_to_dict(placement))


def _placed(home_map: HomeMap | None, target_id: str) -> dict[str, Any]:
    """A light's place on the map, as Light's fields."""
    if home_map is None:
        return {}
    fields: dict[str, Any] = {
        "room": home_map.room_of(target_id),
        "sub_zone": home_map.sub_zone_of(target_id),
    }
    placement = home_map.placement(target_id)
    if placement is not None:
        fields |= shapes.placement_to_dict(placement)
    return fields


# --- lights and attention ----------------------------------------------------------


class LightLatency(ContractModel):
    measured_ms: float | None
    override_ms: float | None = None  # overrides move to PUT /lights/{id}/latency (F6)
    estimated: bool  # the light can't be probed: the type's heuristic


class LightPart(ContractModel):
    id: str  # the part's device id, which places it on its own (ruling 4; not in the contract)
    name: str
    leds: int
    shape: LightShape | None = None  # its own placement; None shares the PC's (ruling 4)


class Light(ContractModel):
    id: str
    name: str
    room: str | None = None
    sub_zone: str | None = None
    model: str
    protocol: LightProtocol
    leds: int
    capabilities: list[Literal["colour", "multizone", "matrix", "effects"]]
    built_in_effects: list[str]
    parts: list[LightPart] | None = None
    shape: LightShape | None = None
    led_order: str = ""
    confirmed: bool = False
    confirmed_at: datetime | None = None  # when it was confirmed; not in the contract
    status: LightStatus  # the contract's LightStatus plus "idle"
    status_since: datetime
    own_effect: str | None = None
    latency: LightLatency
    send_fps: float
    dropped_pct: float
    address: str
    mac: str | None = None
    firmware: str | None = None
    power: bool | None = None  # as last read; not in the contract
    colour: str | None = None  # "#RRGGBB" as last read; not in the contract


class LightUpdate(ContractModel):
    """A light's entry on the `lights` channel."""

    id: str
    status: LightStatus
    status_since: datetime
    own_effect: str | None = None
    power: bool | None = None
    colour: str | None = None


class AttentionSubject(ContractModel):
    type: SubjectType
    id: str


class AttentionItem(ContractModel):
    id: str
    severity: Severity
    kind: AttentionKind
    subject: AttentionSubject
    title: str
    detail: str
    since: datetime
    actions: list[AttentionAction]


def _hex(colour: RGB | None) -> str | None:
    return None if colour is None else rgb_to_hex(*colour).upper()


def built_in_effects(caps: DeviceCapabilities) -> list[str]:
    """The firmware effects a light can run itself (web spec §11.2)."""
    return [
        cls.display_name
        for cls in get_effect_classes().values()
        if issubclass(cls, FirmwareEffect) and cls().supports(caps)
    ]


def light_out(
    entry: LightEntry,
    parts: Sequence[ManagedDevice],
    state: LightState,
    stats: Mapping[str, DeviceStats],
    *,
    home_map: HomeMap | None = None,
) -> Light:
    """A light, from its devices (parts: the entry's managed devices, in order). The PC is
    one light (spec §6.3): its parts' LEDs, capabilities and effects together, the largest
    latency, and its parts' numbers combined as _combined does. A PC has no model, MAC or
    firmware of its own, and lists its parts. state is the light's state; the PC's is its
    parts' combined (zones.lights.combine_states)."""
    effects: list[str] = []
    flags = dict.fromkeys(("colour", "multizone", "matrix", "effects"), False)
    for managed in parts:
        caps = managed.adapter.capabilities
        effects += [name for name in built_in_effects(caps) if name not in effects]
        flags["colour"] = flags["colour"] or caps.colour
        flags["multizone"] = flags["multizone"] or caps.multizone
        flags["matrix"] = flags["matrix"] or caps.matrix
    flags["effects"] = bool(effects)
    send_fps, dropped_pct = _combined([stats[d] for d in entry.devices if d in stats])
    first = parts[0].adapter
    info, caps = first.device_info, first.capabilities
    pc = entry.is_pc
    return Light.model_validate(
        {
            "id": entry.id,
            "name": entry.name,
            "model": caps.protocol if pc else caps.model or info.device_type,
            "protocol": caps.protocol,
            "leds": sum(managed.adapter.led_count for managed in parts),
            "capabilities": [name for name, on in flags.items() if on],
            "built_in_effects": effects,
            "parts": [
                {"id": p.id, "name": p.name, "leds": p.leds, "shape": _part_shape(home_map, p.id)}
                for p in entry.parts
            ]
            if pc
            else None,
            "status": state.status,
            "status_since": state.since,
            "own_effect": state.own_effect,
            "latency": {
                "measured_ms": max(
                    round(m.tracker.effective_latency_ms - m.tracker.manual_offset_ms, 1)
                    for m in parts
                ),
                "estimated": any(not m.adapter.supports_latency_probing for m in parts),
            },
            "send_fps": round(send_fps, 1),
            "dropped_pct": round(dropped_pct, 2),
            "address": info.address,
            "mac": None if pc else info.mac,
            "firmware": None if pc else caps.firmware_version,
            "power": state.power,
            "colour": _hex(state.colour),
            **_placed(home_map, entry.id),
        }
    )


def _combined(parts: Sequence[DeviceStats]) -> tuple[float, float]:
    """A light's send rate and drop rate from its parts': the slowest part that sends, and
    the worst drop rate."""
    sending = [part.send_fps for part in parts if part.send_fps > 0]
    return min(sending, default=0.0), max((part.dropped_pct for part in parts), default=0.0)


def _part_shape(home_map: HomeMap | None, part_id: str) -> dict[str, Any] | None:
    placement = home_map.placement(part_id) if home_map is not None else None
    return shapes.shape_to_dict(placement.shape) if placement is not None else None


def light_stats(index: LightIndex, stats: Iterable[DeviceStats]) -> list[dict[str, Any]]:
    """The stats channel's per-light entries (web spec §12.4), numbers combined as
    light_out combines them."""
    by_device = {entry.device_id: entry for entry in stats if entry.device_id}
    out: list[dict[str, Any]] = []
    for light in index.entries:
        parts = [by_device[d] for d in light.devices if d in by_device]
        if not parts:
            continue
        send_fps, dropped_pct = _combined(parts)
        out.append(
            {
                "id": light.id,
                "send_fps": send_fps,
                "latency_ms": max(part.effective_latency_ms for part in parts),
                "dropped_pct": dropped_pct,
            }
        )
    return out


def light_update_out(state: LightState) -> LightUpdate:
    return LightUpdate(
        id=state.device_id,
        status=state.status,
        status_since=state.since,
        own_effect=state.own_effect,
        power=state.power,
        colour=_hex(state.colour),
    )


def attention_out(item: attention.AttentionItem, index: LightIndex) -> AttentionItem:
    """A light item is about the light: a PC part's is about the PC (ruling 8). Its id
    stays the part's, so two parts offline are two items."""
    subject = index.light_of(item.subject_id) if item.subject_type == "light" else item.subject_id
    return AttentionItem.model_validate(
        {
            "id": item.id,
            "severity": item.severity,
            "kind": item.kind,
            "subject": {"type": item.subject_type, "id": subject},
            "title": item.title,
            "detail": item.detail,
            "since": item.since,
            "actions": list(item.actions),
        }
    )
