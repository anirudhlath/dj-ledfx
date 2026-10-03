"""The look model, shaped like the web app contract (web spec §12.2; engine spec §5.2).

M2 blends any number of visible field layers under the firmware layers. Everything else
the contract can describe is refused with the milestone that brings it.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, get_args

from dj_ledfx.effects.base import StripEffect
from dj_ledfx.effects.field import FieldEffect
from dj_ledfx.effects.firmware import FirmwareEffect
from dj_ledfx.effects.params import EffectParam, check_setting
from dj_ledfx.effects.registry import get_effect_class
from dj_ledfx.effects.strip_adapter import PROJECTION_PARAMS, StripAdapter
from dj_ledfx.looks.selectors import Selector, parse_selector

LayerType = Literal["field", "particles", "firmware"]
Blend = Literal["add", "screen", "normal", "multiply", "max"]
TransitionKind = Literal["cut", "fade", "wipe", "spread", "dissolve"]
Category = Literal["ambient", "tempo", "audio", "home", "firmware"]
Scope = Literal["any-zone", "whole-home"]
InputKind = Literal["tempo", "music", "home-assistant", "sun"]
MaskKind = Literal["height", "room", "sub-zone", "anchor"]
MirrorAxis = Literal["x", "y", "z"]

MAX_TRANSITION_S = 10.0  # the longest transition; a saved look's longer one plays this long
MAX_TRAILS_S = 10.0  # the longest trail
MIN_SCALE = 0.1  # a transform's scale, smallest and largest
MAX_SCALE = 10.0


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
class HeightMask:
    """The layer shows between two heights, metres above the floor."""

    low: float
    high: float


@dataclass(frozen=True, slots=True)
class RoomMask:
    """The layer shows in one room of the home map, by id."""

    room: str


@dataclass(frozen=True, slots=True)
class SubZoneMask:
    """The layer shows in one sub-zone of the home map, by id."""

    sub_zone: str


@dataclass(frozen=True, slots=True)
class AnchorMask:
    """The layer shows within `radius` metres of an anchor."""

    anchor: str
    radius: float


Mask = HeightMask | RoomMask | SubZoneMask | AnchorMask


@dataclass(frozen=True, slots=True)
class Mirror:
    """The field reflected across a plane square to `axis`, `at` metres along it (None: the
    zone's centre). The low side shows on both."""

    axis: MirrorAxis = "x"
    at: float | None = None


@dataclass(frozen=True, slots=True)
class Transform:
    """The field's space moved: shifted by `offset` metres, turned `rotate_deg` clockwise
    seen from above and grown `scale` times, both about the zone's centre."""

    offset: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotate_deg: float = 0.0
    scale: float = 1.0


@dataclass(frozen=True, slots=True)
class Layer:
    id: str
    name: str
    type: LayerType
    kind: str
    visible: bool = True
    blend: Blend = "normal"
    opacity: float = 1.0
    settings: Mapping[str, Any] = field(default_factory=dict)  # the effect's own
    # The lights a firmware layer picks (None: all of them). The contract carries it as
    # the layer's `lights` setting (ruling 13).
    lights: tuple[Selector, ...] | None = None
    mask: Mask | None = None  # the layer modifiers (spec §5.3)
    mirror: Mirror | None = None
    transform: Transform | None = None


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


def _finite(value: Any, what: str) -> float:
    number = _float(value, what)
    if not math.isfinite(number):
        raise LookError(f"{what} must be a finite number")
    return number


def _ident(value: Any, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LookError(f"{what} needs an id")
    return value.strip()


def _numbers(value: Any, count: int, what: str) -> tuple[float, ...]:
    if not isinstance(value, list | tuple) or len(value) != count:
        raise LookError(f"{what} must be {count} numbers")
    return tuple(_finite(item, what) for item in value)


def _mask(layer: str, data: Any) -> Mask | None:
    if data is None:
        return None
    if not isinstance(data, Mapping):
        raise LookError(f"Layer '{layer}': a mask must be an object")
    kind = _choice(data.get("kind"), get_args(MaskKind), "mask")
    what = f"Layer '{layer}': the {kind} mask"
    if kind == "height":
        low, high = _numbers(data.get("range"), 2, f"{what}'s range")
        if low >= high:
            raise LookError(f"{what}'s range must run from low to high")
        return HeightMask(low, high)
    if kind == "room":
        return RoomMask(_ident(data.get("room"), what))
    if kind == "sub-zone":
        return SubZoneMask(_ident(data.get("subZone"), what))
    radius = _finite(data.get("radius"), f"{what}'s radius")
    if radius <= 0.0:
        raise LookError(f"{what}'s radius must be above 0")
    return AnchorMask(_ident(data.get("anchor"), what), radius)


def _mirror(layer: str, data: Any) -> Mirror | None:
    if data is None:
        return None
    if not isinstance(data, Mapping):
        raise LookError(f"Layer '{layer}': a mirror must be an object")
    at = data.get("at")
    return Mirror(
        axis=_choice(data.get("axis", "x"), get_args(MirrorAxis), "mirror axis"),
        at=None if at is None else _finite(at, f"Layer '{layer}': the mirror's place"),
    )


def _transform(layer: str, data: Any) -> Transform | None:
    if data is None:
        return None
    if not isinstance(data, Mapping):
        raise LookError(f"Layer '{layer}': a transform must be an object")
    what = f"Layer '{layer}': the transform"
    x, y, z = _numbers(data.get("offset", (0.0, 0.0, 0.0)), 3, f"{what}'s offset")
    scale = _finite(data.get("scale", 1.0), f"{what}'s scale")
    if not MIN_SCALE <= scale <= MAX_SCALE:
        raise LookError(f"{what}'s scale must be between {MIN_SCALE:g} and {MAX_SCALE:g}")
    return Transform(
        offset=(x, y, z),
        rotate_deg=_finite(data.get("rotateDeg", 0.0), f"{what}'s rotation"),
        scale=scale,
    )


def _modifiers(data: Mapping[str, Any]) -> LookModifiers:
    trails = data.get("trailsS")
    if trails is not None:
        trails = _finite(trails, "Trails")
        if not 0.0 < trails <= MAX_TRAILS_S:
            raise LookError(f"Trails must be longer than 0 s and at most {MAX_TRAILS_S:g} s")
    cap = data.get("brightnessCap")
    if cap is not None:
        cap = _finite(cap, "The brightness cap")
        if not 0.0 <= cap <= 1.0:
            raise LookError("The brightness cap must be between 0 and 1")
    return LookModifiers(
        trails_s=trails,
        downbeat_flash=bool(data.get("downbeatFlash", False)),
        brightness_cap=cap,
        evening=bool(data.get("evening", False)),
    )


def _duration(value: Any) -> float:
    """A transition's length. A saved look may hold one no request could send now (from
    before M4 checked them): out of range it's clamped, and not finite it's a cut."""
    seconds = _float(value, "Transition duration")
    if not math.isfinite(seconds) or seconds <= 0.0:
        return 0.0
    return min(seconds, MAX_TRANSITION_S)


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
    name = str(data.get("name") or kind)
    lights = _lights(name, settings.pop(LIGHTS_SETTING, None))
    return Layer(
        id=str(data.get("id") or f"layer-{index + 1}"),
        name=name,
        type=layer_type,
        kind=kind,
        visible=bool(data.get("visible", True)),
        blend=_choice(data.get("blend", "normal"), get_args(Blend), "blend mode"),
        opacity=opacity,
        settings=settings,
        lights=lights,
        mask=_mask(name, data.get("mask")),
        mirror=_mirror(name, data.get("mirror")),
        transform=_transform(name, data.get("transform")),
    )


def _lights(layer: str, value: Any) -> tuple[Selector, ...] | None:
    """A layer's `lights` setting as selectors; None (all lights) when it's empty."""
    if value is None or value == "" or value == []:
        return None
    try:
        check_setting(LIGHTS_SETTING, LIGHTS_PARAM, value)
        return tuple(
            parse_selector(item) for item in ([value] if isinstance(value, str) else value)
        )
    except ValueError as exc:
        raise LookError(f"Layer '{layer}': {exc}") from exc


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
        modifiers=_modifiers(modifiers),
        transition=Transition(
            kind=_choice(transition.get("kind", "cut"), get_args(TransitionKind), "transition"),
            duration_s=_duration(transition.get("durationS", 0.0)),
        ),
        derived_from=str(data["derivedFrom"]) if data.get("derivedFrom") else None,
    )


_PLAIN_TYPES = {
    "color": "colour",
    "color_list": "palette",
    "bool": "boolean",
    "anchor": "anchor",
    "point": "point",
    "zone": "zone",
    "device_set": "lights",  # the contract's name wins (engine spec §1)
}


def _schema_entry(key: str, param: EffectParam) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "key": key,
        "label": param.label or key.replace("_", " ").capitalize(),
        "bindable": param.bindable,
    }
    if param.type in ("float", "int"):
        entry.update(
            type="number",
            min=param.min if param.min is not None else 0.0,
            max=param.max if param.max is not None else 1.0,
            step=param.step if param.step is not None else (1 if param.type == "int" else 0.01),
        )
    elif param.type == "range":
        entry.update(
            type="range",
            min=param.min if param.min is not None else 0.0,
            max=param.max if param.max is not None else 1.0,
        )
    elif param.type in _PLAIN_TYPES:
        entry["type"] = _PLAIN_TYPES[param.type]
    else:
        entry.update(type="choice", options=list(param.choices or []))
    return entry


LIGHTS_SETTING = "lights"  # a firmware layer's light ids or type:<word> selectors
LIGHTS_PARAM = EffectParam(type="device_set", default=None, label="Lights")


def setting_schema(kind: str) -> list[dict[str, Any]]:
    try:
        cls = get_effect_class(kind)
    except KeyError:
        return []
    entries = [_schema_entry(key, param) for key, param in cls.parameters().items()]
    if issubclass(cls, FirmwareEffect):
        entries.append(_schema_entry(LIGHTS_SETTING, LIGHTS_PARAM))
    if issubclass(cls, StripEffect):
        entries += [_schema_entry(key, param) for key, param in PROJECTION_PARAMS.items()]
    return entries


def _mask_to_dict(mask: Mask | None) -> dict[str, Any] | None:
    match mask:
        case HeightMask(low, high):
            return {"kind": "height", "range": [low, high]}
        case RoomMask(room):
            return {"kind": "room", "room": room}
        case SubZoneMask(sub_zone):
            return {"kind": "sub-zone", "subZone": sub_zone}
        case AnchorMask(anchor, radius):
            return {"kind": "anchor", "anchor": anchor, "radius": radius}
    return None


def _modifiers_to_dict(layer: Layer) -> dict[str, Any]:
    """A layer's mask, mirror and transform in the contract's shapes, None where unset."""
    mirror, transform = layer.mirror, layer.transform
    return {
        "mask": _mask_to_dict(layer.mask),
        "mirror": None if mirror is None else {"axis": mirror.axis, "at": mirror.at},
        "transform": None
        if transform is None
        else {
            "offset": list(transform.offset),
            "rotateDeg": transform.rotate_deg,
            "scale": transform.scale,
        },
    }


def _layer_to_dict(layer: Layer, *, for_storage: bool) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": layer.id,
        "name": layer.name,
        "type": layer.type,
        "kind": layer.kind,
        "visible": layer.visible,
        "blend": layer.blend,
        "opacity": layer.opacity,
        "settings": {key: {"value": value} for key, value in layer.settings.items()},
        **_modifiers_to_dict(layer),
    }
    if layer.lights is not None:
        data["settings"][LIGHTS_SETTING] = {"value": [s.text for s in layer.lights]}
    if not for_storage:
        data["schema"] = setting_schema(layer.kind)
    return data


def look_to_dict(
    look: Look, *, starred: bool = False, for_storage: bool = False
) -> dict[str, Any]:
    """The look in the contract's shape. For storage, without the star (kept apart) and
    the layers' setting schemas (worked out from the effect kind when read)."""
    data: dict[str, Any] = {
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
        "layers": [_layer_to_dict(layer, for_storage=for_storage) for layer in look.layers],
        "modifiers": {
            "trailsS": look.modifiers.trails_s,
            "downbeatFlash": look.modifiers.downbeat_flash,
            "brightnessCap": look.modifiers.brightness_cap,
            "evening": look.modifiers.evening,
        },
        "transition": {"kind": look.transition.kind, "durationS": look.transition.duration_s},
    }
    if not for_storage:
        data["starred"] = starred
    return data


def make_effect(layer: Layer) -> FieldEffect | FirmwareEffect:
    """A fresh effect for the layer with its settings applied. Strip effects come wrapped,
    so the adapter takes its projection settings and passes the rest on."""
    try:
        cls = get_effect_class(layer.kind)
    except KeyError:
        raise LookError(f"Layer '{layer.name}' uses an unknown effect '{layer.kind}'") from None
    raw = cls()
    effect: FieldEffect | FirmwareEffect
    if layer.type == "firmware":
        if not isinstance(raw, FirmwareEffect):
            raise LookError(f"Layer '{layer.name}': '{layer.kind}' isn't a firmware effect")
        effect = raw
    elif isinstance(raw, StripEffect):
        effect = StripAdapter(raw)
    elif isinstance(raw, FieldEffect):
        effect = raw
    else:
        raise LookError(f"Layer '{layer.name}': '{layer.kind}' isn't a field effect")
    try:
        effect.set_params(**layer.settings)
    except (TypeError, ValueError) as exc:
        raise LookError(f"Layer '{layer.name}': {exc}") from exc
    return effect


def visible_field_layers(look: Look) -> list[Layer]:
    """The streamed layers the runtime blends, bottom to top."""
    return [layer for layer in look.layers if layer.type == "field" and layer.visible]


def visible_field_layer(look: Look) -> Layer | None:
    fields = visible_field_layers(look)
    return fields[0] if fields else None


def firmware_layers(look: Look) -> list[Layer]:
    return [layer for layer in look.layers if layer.type == "firmware" and layer.visible]


def validate_look(look: Look) -> None:
    """Raise LookError if M2 can't run the look."""
    if not look.layers:
        raise LookError("A look needs at least one layer")
    if look.scope != "any-zone":
        raise LookError("Home looks (whole-home scope) arrive in M6")
    if look.modifiers != LookModifiers():
        raise LookError("Look modifiers arrive in M4")
    for layer in look.layers:
        make_effect(layer)
        modified = (layer.mask, layer.mirror, layer.transform) != (None, None, None)
        if layer.type == "firmware" and modified:
            raise LookError(
                f"Layer '{layer.name}': a firmware layer runs whole on the lights it picks; "
                "it takes no mask, mirror or transform"
            )
        if layer.type != "firmware" and layer.lights is not None:
            raise LookError(
                f"Layer '{layer.name}': only a firmware layer picks its lights; "
                "give a streamed layer a mask instead"
            )
