"""The web app's data contract (web spec §12.2) as Pydantic models.

Fields are snake_case here and camelCase on the wire. Class names are the contract's:
the web app generates its types from the OpenAPI schema (spec §9).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from dj_ledfx.looks import model as looks

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
