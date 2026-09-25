"""The web app's data contract (web spec §12.2) as Pydantic models.

Fields are snake_case here and camelCase on the wire. Class names are the contract's:
the web app generates its types from the OpenAPI schema (spec §9).
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from dj_ledfx.devices.capabilities import DeviceCapabilities, LightProtocol
from dj_ledfx.devices.manager import ManagedDevice
from dj_ledfx.effects.color import rgb_to_hex
from dj_ledfx.effects.firmware import FirmwareEffect
from dj_ledfx.effects.registry import get_effect_classes
from dj_ledfx.looks import model as looks
from dj_ledfx.looks.model import Blend, Category, InputKind, LayerType, Scope, TransitionKind
from dj_ledfx.types import RGB, DeviceStats
from dj_ledfx.zones import attention
from dj_ledfx.zones.attention import AttentionAction, AttentionKind, Severity, SubjectType
from dj_ledfx.zones.lights import LightState, LightStatus
from dj_ledfx.zones.model import RunningZoneInfo, StartResult, ZoneKind, ZoneRecord
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


def zone_out(zone: ZoneRecord) -> Zone:
    return Zone(id=zone.id, name=zone.name, kind=zone.kind, lights=list(zone.lights))


def _running_fields(info: RunningZoneInfo) -> dict[str, Any]:
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
        "lights": list(info.lights),
        "covers": list(info.covers),
        "state": info.state,
        "fps": fps,
        "error": error,
        "waiting_for": list(info.waiting_for) or None,
    }


def running_zone_out(info: RunningZoneInfo) -> RunningZone:
    return RunningZone.model_validate(_running_fields(info))


def running_out(infos: Iterable[RunningZoneInfo]) -> Running:
    return Running(zones=[running_zone_out(info) for info in infos])


def start_out(result: StartResult) -> StartResponse:
    take_overs = [
        {
            "zone_id": take_over.zone_id,
            "zone_name": take_over.zone_name,
            "look_name": take_over.look_name,
            "lights": list(take_over.lights),
            "stopped": take_over.stopped,
        }
        for take_over in result.take_overs
    ]
    fields = {**_running_fields(result.running), "take_overs": take_overs}
    return StartResponse.model_validate(fields)


# --- lights and attention ----------------------------------------------------------


class LightLatency(ContractModel):
    measured_ms: float | None
    override_ms: float | None = None  # overrides move to PUT /lights/{id}/latency (F6)
    estimated: bool  # the light can't be probed: the type's heuristic


class LightPart(ContractModel):
    name: str
    leds: int


class Light(ContractModel):
    id: str
    name: str
    room: str | None = None  # placement fields arrive with the home map (M2)
    sub_zone: str | None = None
    model: str
    protocol: LightProtocol
    leds: int
    capabilities: list[Literal["colour", "multizone", "matrix", "effects"]]
    built_in_effects: list[str]
    parts: list[LightPart] | None = None
    shape: dict[str, Any] | None = None
    led_order: str = ""
    confirmed: bool = False
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


def light_out(managed: ManagedDevice, state: LightState, stats: DeviceStats | None) -> Light:
    adapter, tracker = managed.adapter, managed.tracker
    info, caps = adapter.device_info, adapter.capabilities
    effects = built_in_effects(caps)
    flags = {
        "colour": caps.colour,
        "multizone": caps.multizone,
        "matrix": caps.matrix,
        "effects": bool(effects),
    }
    return Light.model_validate(
        {
            "id": state.device_id,
            "name": info.name,
            "model": caps.model or info.device_type,
            "protocol": caps.protocol,
            "leds": adapter.led_count,
            "capabilities": [name for name, on in flags.items() if on],
            "built_in_effects": effects,
            "status": state.status,
            "status_since": state.since,
            "own_effect": state.own_effect,
            "latency": {
                "measured_ms": round(tracker.effective_latency_ms - tracker.manual_offset_ms, 1),
                "estimated": not adapter.supports_latency_probing,
            },
            "send_fps": round(stats.send_fps, 1) if stats else 0.0,
            "dropped_pct": round(stats.dropped_pct, 2) if stats else 0.0,
            "address": info.address,
            "mac": info.mac,
            "firmware": caps.firmware_version,
            "power": state.power,
            "colour": _hex(state.colour),
        }
    )


def light_update_out(state: LightState) -> LightUpdate:
    return LightUpdate(
        id=state.device_id,
        status=state.status,
        status_since=state.since,
        own_effect=state.own_effect,
        power=state.power,
        colour=_hex(state.colour),
    )


def attention_out(item: attention.AttentionItem) -> AttentionItem:
    return AttentionItem.model_validate(
        {
            "id": item.id,
            "severity": item.severity,
            "kind": item.kind,
            "subject": {"type": item.subject_type, "id": item.subject_id},
            "title": item.title,
            "detail": item.detail,
            "since": item.since,
            "actions": list(item.actions),
        }
    )
