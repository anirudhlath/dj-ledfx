"""The look model, shaped like the web app contract (web spec §12.2; engine spec §5.2).

M1 runs one visible streamed layer plus any number of firmware layers. Everything else
the contract can describe is refused with the milestone that brings it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, get_args

from dj_ledfx.effects.base import StripEffect
from dj_ledfx.effects.field import FieldEffect
from dj_ledfx.effects.firmware import FirmwareEffect
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.effects.registry import get_effect_class
from dj_ledfx.effects.strip_adapter import StripAdapter

LayerType = Literal["field", "particles", "firmware"]
Blend = Literal["add", "screen", "normal", "multiply", "max"]
TransitionKind = Literal["cut", "fade", "wipe", "spread", "dissolve"]
Category = Literal["ambient", "tempo", "audio", "home", "firmware"]
Scope = Literal["any-zone", "whole-home"]
InputKind = Literal["tempo", "music", "home-assistant", "sun"]


class LookError(ValueError):
    """A look that can't be read or can't run in this version, with the reason."""


class LookNotFoundError(KeyError):
    pass


class BuiltInLookError(Exception):
    """Built-in looks are never changed; save an edit as a new look instead."""


@dataclass(frozen=True, slots=True)
class Transition:
    kind: TransitionKind = "cut"
    duration_s: float = 0.0


@dataclass(frozen=True, slots=True)
class LookModifiers:
    trails_s: float | None = None
    downbeat_flash: bool = False
    brightness_cap: float | None = None
    evening: bool = False


@dataclass(frozen=True, slots=True)
class Layer:
    id: str
    name: str
    type: LayerType
    kind: str
    visible: bool = True
    blend: Blend = "normal"
    opacity: float = 1.0
    settings: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Look:
    id: str
    name: str
    category: Category
    description: str = ""
    thumbnail: str = ""
    scope: Scope = "any-zone"
    needs: tuple[InputKind, ...] = ()
    uses: tuple[InputKind, ...] = ()
    layers: tuple[Layer, ...] = ()
    modifiers: LookModifiers = LookModifiers()
    transition: Transition = Transition()
    built_in: bool = False
    derived_from: str | None = None


def _choice(value: Any, allowed: tuple[str, ...], what: str) -> Any:
    if value not in allowed:
        raise LookError(f"Unknown {what} {value!r}; expected one of {', '.join(allowed)}")
    return value


def _float(value: Any, what: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise LookError(f"{what} must be a number")
    return float(value)


def _inputs(values: Any, what: str) -> tuple[Any, ...]:
    if not isinstance(values, list):
        raise LookError(f"'{what}' must be a list of inputs")
    return tuple(_choice(v, get_args(InputKind), "input") for v in values)


def _layer_from_dict(data: Mapping[str, Any], index: int) -> Layer:
    if not isinstance(data, Mapping):
        raise LookError(f"Layer {index + 1} must be an object")
    layer_type = _choice(data.get("type"), get_args(LayerType), "layer type")
    if layer_type == "particles":
        raise LookError("Particle layers arrive in M5")
    for modifier in ("mask", "mirror", "transform"):
        if data.get(modifier) is not None:
            raise LookError(f"Layer modifiers ({modifier}) arrive in M4")
    raw_settings = data.get("settings") or {}
    if not isinstance(raw_settings, Mapping):
        raise LookError("Layer settings must be an object")
    settings: dict[str, Any] = {}
    for key, setting in raw_settings.items():
        if not isinstance(setting, Mapping) or "value" not in setting:
            raise LookError(f"Setting '{key}' must be an object with a value")
        if setting.get("binding") is not None:
            raise LookError(f"Setting '{key}' is bound to a signal; bindings arrive in M7")
        settings[str(key)] = setting["value"]
    opacity = _float(data.get("opacity", 1.0), "Layer opacity")
    if not 0.0 <= opacity <= 1.0:
        raise LookError("Layer opacity must be between 0 and 1")
    kind = str(data.get("kind") or "")
    return Layer(
        id=str(data.get("id") or f"layer-{index + 1}"),
        name=str(data.get("name") or kind),
        type=layer_type,
        kind=kind,
        visible=bool(data.get("visible", True)),
        blend=_choice(data.get("blend", "normal"), get_args(Blend), "blend mode"),
        opacity=opacity,
        settings=settings,
    )


def look_from_dict(data: Mapping[str, Any]) -> Look:
    """Read a contract-shaped look. `builtIn` and `starred` in the input are ignored."""
    if not isinstance(data, Mapping):
        raise LookError("A look must be an object")
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise LookError("A look needs a name")
    layers = data.get("layers") or []
    if not isinstance(layers, list):
        raise LookError("'layers' must be a list")
    modifiers = data.get("modifiers") or {}
    transition = data.get("transition") or {}
    if not isinstance(modifiers, Mapping) or not isinstance(transition, Mapping):
        raise LookError("'modifiers' and 'transition' must be objects")
    return Look(
        id=str(data.get("id") or ""),
        name=name.strip(),
        category=_choice(data.get("category"), get_args(Category), "category"),
        description=str(data.get("description") or ""),
        thumbnail=str(data.get("thumbnail") or ""),
        scope=_choice(data.get("scope", "any-zone"), get_args(Scope), "scope"),
        needs=_inputs(data.get("needs", []), "needs"),
        uses=_inputs(data.get("uses", []), "uses"),
        layers=tuple(_layer_from_dict(layer, i) for i, layer in enumerate(layers)),
        modifiers=LookModifiers(
            trails_s=modifiers.get("trailsS"),
            downbeat_flash=bool(modifiers.get("downbeatFlash", False)),
            brightness_cap=modifiers.get("brightnessCap"),
            evening=bool(modifiers.get("evening", False)),
        ),
        transition=Transition(
            kind=_choice(transition.get("kind", "cut"), get_args(TransitionKind), "transition"),
            duration_s=_float(transition.get("durationS", 0.0), "Transition duration"),
        ),
        derived_from=str(data["derivedFrom"]) if data.get("derivedFrom") else None,
    )


def _schema_entry(key: str, param: EffectParam) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "key": key,
        "label": param.label or key.replace("_", " ").capitalize(),
        "bindable": False,  # bindings arrive in M7
    }
    if param.type in ("float", "int"):
        entry.update(
            type="number",
            min=param.min if param.min is not None else 0.0,
            max=param.max if param.max is not None else 1.0,
            step=param.step if param.step is not None else (1 if param.type == "int" else 0.01),
        )
    elif param.type == "color":
        entry["type"] = "colour"
    elif param.type == "color_list":
        entry["type"] = "palette"
    elif param.type == "bool":
        entry["type"] = "boolean"
    else:
        entry.update(type="choice", options=list(param.choices or []))
    return entry


def setting_schema(kind: str) -> list[dict[str, Any]]:
    try:
        params = get_effect_class(kind).parameters()
    except KeyError:
        return []
    return [_schema_entry(key, param) for key, param in params.items()]


def _layer_to_dict(layer: Layer) -> dict[str, Any]:
    return {
        "id": layer.id,
        "name": layer.name,
        "type": layer.type,
        "kind": layer.kind,
        "visible": layer.visible,
        "blend": layer.blend,
        "opacity": layer.opacity,
        "settings": {key: {"value": value} for key, value in layer.settings.items()},
        "schema": setting_schema(layer.kind),
        "mask": None,
        "mirror": None,
        "transform": None,
    }


def look_to_dict(look: Look, *, starred: bool = False) -> dict[str, Any]:
    return {
        "id": look.id,
        "name": look.name,
        "category": look.category,
        "builtIn": look.built_in,
        "derivedFrom": look.derived_from,
        "description": look.description,
        "thumbnail": look.thumbnail,
        "scope": look.scope,
        "needs": list(look.needs),
        "uses": list(look.uses),
        "starred": starred,
        "layers": [_layer_to_dict(layer) for layer in look.layers],
        "modifiers": {
            "trailsS": look.modifiers.trails_s,
            "downbeatFlash": look.modifiers.downbeat_flash,
            "brightnessCap": look.modifiers.brightness_cap,
            "evening": look.modifiers.evening,
        },
        "transition": {"kind": look.transition.kind, "durationS": look.transition.duration_s},
    }


def make_effect(layer: Layer) -> FieldEffect | FirmwareEffect:
    """A fresh effect for the layer with its settings applied. Strip effects come wrapped."""
    try:
        cls = get_effect_class(layer.kind)
    except KeyError:
        raise LookError(f"Layer '{layer.name}' uses an unknown effect '{layer.kind}'") from None
    effect = cls()
    try:
        effect.set_params(**layer.settings)
    except (TypeError, ValueError) as exc:
        raise LookError(f"Layer '{layer.name}': {exc}") from exc
    if layer.type == "firmware":
        if not isinstance(effect, FirmwareEffect):
            raise LookError(f"Layer '{layer.name}': '{layer.kind}' isn't a firmware effect")
        return effect
    if isinstance(effect, StripEffect):
        return StripAdapter(effect)
    if isinstance(effect, FieldEffect):
        return effect
    raise LookError(f"Layer '{layer.name}': '{layer.kind}' isn't a field effect")


def visible_field_layer(look: Look) -> Layer | None:
    return next((layer for layer in look.layers if layer.type == "field" and layer.visible), None)


def firmware_layers(look: Look) -> list[Layer]:
    return [layer for layer in look.layers if layer.type == "firmware"]


def validate_look(look: Look) -> None:
    """Raise LookError if M1 can't run the look."""
    if not look.layers:
        raise LookError("A look needs at least one layer")
    if look.scope != "any-zone":
        raise LookError("Home looks (whole-home scope) arrive in M6")
    if look.modifiers != LookModifiers():
        raise LookError("Look modifiers arrive in M4")
    for layer in look.layers:
        make_effect(layer)
    if sum(1 for layer in look.layers if layer.type == "field" and layer.visible) > 1:
        raise LookError("M1 plays one streamed layer; layer blending arrives in M2")
