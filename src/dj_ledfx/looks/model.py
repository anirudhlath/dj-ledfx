"""The look model, shaped like the web app contract (web spec §12.2; engine spec §5.2).

M2 blends any number of visible field layers under the firmware layers. Everything else
the contract can describe is refused with the milestone that brings it.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, TypeVar, get_args

from dj_ledfx.effects.base import StripEffect
from dj_ledfx.effects.field import FieldEffect
from dj_ledfx.effects.firmware import FirmwareEffect
from dj_ledfx.effects.params import EffectParam, check_setting
from dj_ledfx.effects.registry import get_effect_class
from dj_ledfx.effects.strip_adapter import PROJECTION_PARAMS, StripAdapter
from dj_ledfx.looks.selectors import Selector, parse_selector
from dj_ledfx.readers import Reader
from dj_ledfx.types import is_finite_number

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
# The farthest, either way, a look's places and distances go in metres: a mask's heights
# and reach, a mirror's place, a transform's offset. A float32 position goes infinite at
# about 3.4e38 m, and every effect's colours with it.
MAX_DISTANCE_M = 1000.0


class LookError(ValueError):
    """A look that can't be read or can't run in this version, with the reason."""


_READ = Reader(LookError)  # the readers the home map uses too (readers.py)


class LookNotFoundError(KeyError):
    pass


class BuiltInLookError(Exception):
    """Built-in looks are never changed; save an edit as a new look instead."""


@dataclass(frozen=True, slots=True)
class Transition:
    kind: TransitionKind = "cut"
    duration_s: float = 0.0

    @property
    def plays(self) -> bool:
        """Whether a start plays anything: a cut, or a transition of no time, doesn't."""
        return self.kind != "cut" and self.duration_s > 0.0


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


# Reading a look is lenient with numbers: saved data (a look, a zone's assignment, a
# restored backup) may hold one no request could send now, from before a limit or by hand.
# A number past its bounds is clamped to them, and NaN or an infinity is the number's
# neutral value, so the look still loads. Requests never get here out of bounds: the
# contract refuses them with 422 (web/contract.py). What can't be mapped is refused:
# something that isn't a number at all, an unknown kind, a height range from high to low.
_Neutral = TypeVar("_Neutral", float, None)
_Part = TypeVar("_Part")


def _endless(number: int | float) -> bool:
    """NaN or an infinity. An integer too big for a float isn't: it's past a bound."""
    return not (is_finite_number(number) or isinstance(number, int))


def _bounded(
    value: Any, what: str, low: float, high: float, neutral: _Neutral
) -> float | _Neutral:
    """A number within low..high, clamped to them; `neutral` for NaN or an infinity."""
    number = _READ.number(value, what)
    return neutral if _endless(number) else float(min(max(number, low), high))


def _optional(value: Any, what: str, low: float, high: float) -> float | None:
    """A number a look may leave out (None), within low..high; None for NaN or an
    infinity."""
    return None if value is None else _bounded(value, what, low, high, None)


def _metres(value: Any, what: str, neutral: _Neutral) -> float | _Neutral:
    return _bounded(value, what, -MAX_DISTANCE_M, MAX_DISTANCE_M, neutral)


def _degrees(value: Any, what: str) -> float:
    """An angle as the same turn from -180 (not included) to 180; 0 for NaN or an
    infinity."""
    number = _READ.number(value, what)
    return 0.0 if _endless(number) else 180.0 - (180 - number) % 360


def _part(
    read: Callable[[str, Mapping[str, Any]], _Part], layer: str, data: Any, what: str
) -> _Part | None:
    """A layer's mask, mirror or transform (`what`), read by `read`; None when it has
    none."""
    return None if data is None else read(layer, _READ.mapping(data, f"Layer '{layer}': {what}"))


def _mask(layer: str, data: Mapping[str, Any]) -> Mask:
    kind = _choice(data.get("kind"), get_args(MaskKind), "mask")
    what = f"Layer '{layer}': the {kind} mask"
    if kind == "height":  # NaN or an infinity leaves its side of the band open
        low, high = (
            _READ.number(part, f"{what}'s range")
            for part in _READ.items(data.get("range"), 2, f"{what}'s range")
        )
        low, high = (-math.inf if _endless(low) else low, math.inf if _endless(high) else high)
        if low >= high:
            raise LookError(f"{what}'s range must run from low to high")
        return HeightMask(_metres(low, what, -MAX_DISTANCE_M), _metres(high, what, MAX_DISTANCE_M))
    if kind == "room":
        return RoomMask(_READ.text(data.get("room"), f"{what}'s room"))
    if kind == "sub-zone":
        return SubZoneMask(_READ.text(data.get("subZone"), f"{what}'s sub-zone"))
    radius = _bounded(data.get("radius"), f"{what}'s radius", 0.0, MAX_DISTANCE_M, MAX_DISTANCE_M)
    return AnchorMask(_READ.text(data.get("anchor"), f"{what}'s anchor"), radius)


def _mirror(layer: str, data: Mapping[str, Any]) -> Mirror:
    at = data.get("at")
    return Mirror(
        axis=_choice(data.get("axis", "x"), get_args(MirrorAxis), "mirror axis"),
        at=_optional(at, f"Layer '{layer}': the mirror's place", -MAX_DISTANCE_M, MAX_DISTANCE_M),
    )


def _transform(layer: str, data: Mapping[str, Any]) -> Transform:
    what = f"Layer '{layer}': the transform"
    x, y, z = (
        _metres(part, f"{what}'s offset", 0.0)
        for part in _READ.items(data.get("offset", (0.0, 0.0, 0.0)), 3, f"{what}'s offset")
    )
    return Transform(
        offset=(x, y, z),
        rotate_deg=_degrees(data.get("rotateDeg", 0.0), f"{what}'s rotation"),
        scale=_bounded(data.get("scale", 1.0), f"{what}'s scale", MIN_SCALE, MAX_SCALE, 1.0),
    )


def _modifiers(data: Mapping[str, Any]) -> LookModifiers:
    trails = _optional(data.get("trailsS"), "Trails", 0.0, MAX_TRAILS_S)
    return LookModifiers(
        trails_s=trails or None,  # no time is no trails
        downbeat_flash=bool(data.get("downbeatFlash", False)),
        brightness_cap=_optional(data.get("brightnessCap"), "The brightness cap", 0.0, 1.0),
        evening=bool(data.get("evening", False)),
    )


def _duration(value: Any) -> float:
    """A transition's length: none (a cut) when it isn't finite."""
    return _bounded(value, "Transition duration", 0.0, MAX_TRANSITION_S, 0.0)


def _inputs(values: Any, what: str) -> tuple[Any, ...]:
    if not isinstance(values, list):
        raise LookError(f"'{what}' must be a list of inputs")
    return tuple(_choice(v, get_args(InputKind), "input") for v in values)


def _layer_from_dict(layer: Any, index: int) -> Layer:
    data = _READ.mapping(layer, f"Layer {index + 1}")
    layer_type = _choice(data.get("type"), get_args(LayerType), "layer type")
    if layer_type == "particles":
        raise LookError("Particle layers arrive in M5")
    raw_settings = _READ.mapping(data.get("settings") or {}, "Layer settings")
    settings: dict[str, Any] = {}
    for key, setting in raw_settings.items():
        if not isinstance(setting, Mapping) or "value" not in setting:
            raise LookError(f"Setting '{key}' must be an object with a value")
        if setting.get("binding") is not None:
            raise LookError(f"Setting '{key}' is bound to a signal; bindings arrive in M7")
        settings[str(key)] = setting["value"]
    opacity = _bounded(data.get("opacity", 1.0), "Layer opacity", 0.0, 1.0, 1.0)
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
        mask=_part(_mask, name, data.get("mask"), "a mask"),
        mirror=_part(_mirror, name, data.get("mirror"), "a mirror"),
        transform=_part(_transform, name, data.get("transform"), "a transform"),
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
    data = _READ.mapping(data, "A look")
    name = _READ.text(data.get("name"), "A look's name")
    layers = data.get("layers") or []
    if not isinstance(layers, list):
        raise LookError("'layers' must be a list")
    modifiers = _READ.mapping(data.get("modifiers") or {}, "A look's modifiers")
    transition = _READ.mapping(data.get("transition") or {}, "A look's transition")
    return Look(
        id=str(data.get("id") or ""),
        name=name,
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
    """Raise LookError if the engine can't run the look."""
    if not look.layers:
        raise LookError("A look needs at least one layer")
    if look.scope != "any-zone":
        raise LookError("Home looks (whole-home scope) arrive in M6")
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
