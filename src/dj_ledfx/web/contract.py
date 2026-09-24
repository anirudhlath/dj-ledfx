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

from dj_ledfx.looks import model as looks
from dj_ledfx.zones.model import RunningZoneInfo, StartResult, ZoneRecord

InputKind = Literal["tempo", "music", "home-assistant", "sun"]
TransitionKind = Literal["cut", "fade", "wipe", "spread", "dissolve"]


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
    type: Literal["field", "particles", "firmware"]
    kind: str
    visible: bool = True
    blend: Literal["add", "screen", "normal", "multiply", "max"] = "normal"
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
    category: Literal["ambient", "tempo", "audio", "home", "firmware"]
    built_in: bool = False
    derived_from: str | None = None
    description: str = ""
    thumbnail: str = ""
    scope: Literal["any-zone", "whole-home"] = "any-zone"
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
    kind: Literal["home", "room", "sub-zone", "group"]
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
    covers: list[str] = Field(default_factory=list)  # rooms come with the home map (M2)
    state: Literal["running", "transition", "slow", "crashed", "waiting"]
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
