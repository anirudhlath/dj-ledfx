"""One running zone: its look, its LEDs and the frames it renders ahead (spec §4.1, §8)."""

from __future__ import annotations

import itertools
import math
import time
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Literal

import numpy as np
from loguru import logger

from dj_ledfx.effects.blend import blend_into
from dj_ledfx.effects.context import render_context
from dj_ledfx.effects.firmware import FirmwareEffect
from dj_ledfx.effects.ledset import (
    NO_ROOM,
    NO_SPACE,
    LedSet,
    LedSource,
    PlacedLeds,
    Space,
    build_ledset,
)
from dj_ledfx.effects.ring_buffer import RingBuffer
from dj_ledfx.looks.model import (
    Layer,
    Look,
    LookError,
    firmware_layers,
    make_effect,
    visible_field_layers,
)
from dj_ledfx.looks.selectors import Selector, selects
from dj_ledfx.scheduling.route import DeviceRoute
from dj_ledfx.timing import trim_window, utcnow
from dj_ledfx.types import RenderedFrame
from dj_ledfx.zones.model import CrashInfo

if TYPE_CHECKING:
    from numpy.typing import NDArray

    from dj_ledfx.beat.clock import BeatClock
    from dj_ledfx.devices.capabilities import DeviceCapabilities
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.field import FieldEffect
    from dj_ledfx.spatial.geometry import DeviceGeometry
    from dj_ledfx.types import FloatRGB

FRAME_BUDGET_S = 0.005
SLOW_RATIO = 0.8
SLOW_AFTER_S = 30.0
CRASH_LOG_INTERVAL_S = 60.0
ALWAYS_AVAILABLE = frozenset({"tempo"})  # the internal clock at worst (spec §5.2)

# Process-wide, so no two runtimes ever share a generation: a light applied for one
# runtime always sees a new look as new.
_GENERATIONS = itertools.count(1)

ZoneState = Literal["running", "slow", "crashed", "waiting"]
LightMode = Literal["streaming", "own-effect", "streamed-copy"]


def _finite(colors: FloatRGB) -> FloatRGB:
    if not np.isfinite(colors).all():
        raise FloatingPointError("the layer produced NaN or infinite colours")
    return colors


def _layout(look: Look) -> list[tuple[str, str, str, bool, object]]:
    """What can't change in place: the layers, and which lights each one picks."""
    return [
        (layer.id, layer.type, layer.kind, layer.visible, layer.lights) for layer in look.layers
    ]


@dataclass(frozen=True, slots=True)
class ZoneLight:
    """One light as its zone sees it: where the home map puts its LEDs (None: not placed)
    and its room's index in the zone's Space.rooms."""

    device_id: str
    led_count: int
    caps: DeviceCapabilities
    geometry: DeviceGeometry | None = None
    placed: PlacedLeds | None = None
    room: int = NO_ROOM
    light_id: str = ""  # its light's id: the PC's for a PC part (devices/lights.py)
    name: str = ""


class ZoneRuntime:
    """Renders one running zone's look ahead of time into its own ring buffer."""

    def __init__(
        self,
        zone_id: str,
        look: Look,
        lights: Sequence[ZoneLight],
        *,
        clock: BeatClock,
        latency_s: Callable[[str], float | None],
        fps: int = 60,
        max_lookahead_s: float = 1.0,
        brightness: float = 1.0,
        seed: int = 0,
        space: Space = NO_SPACE,
        timer: Callable[[], float] = time.perf_counter,
        now: Callable[[], datetime] = utcnow,
        on_state_change: Callable[[ZoneRuntime], None] | None = None,
        watched: Callable[[], bool] = lambda: True,
    ) -> None:
        self.zone_id = zone_id
        # Called when the zone crashes, turns slow or recovers by itself; the zone
        # manager tells the running channel.
        self._on_state_change = on_state_change
        self.look = look
        self.brightness = brightness
        self.generation = 0  # _compile draws the first
        self.crash: CrashInfo | None = None
        self.slow_since: datetime | None = None
        self._clock = clock
        self._latency_s = latency_s
        self._fps = fps
        self._max_lookahead_s = max_lookahead_s
        self._seed = seed
        self._timer = timer
        self._now = now
        # Whether anyone watches this zone's frames (Task 13). Lights that run their
        # own effect are drawn only for the preview, so only while someone watches.
        self._watched = watched
        self._fields: list[tuple[Layer, FieldEffect]] = []  # bottom to top
        self._firmware: list[tuple[Layer, FirmwareEffect]] = []  # top layer first
        self._selectors: list[tuple[Selector, ...] | None] = []  # each firmware layer's lights
        self._claims: dict[str, int] = {}  # light -> firmware layer it runs itself
        self._copies: dict[str, int] = {}  # light -> firmware layer streamed as a copy
        self._emulated: set[str] = set()  # lights that rejected their firmware effect
        # Each firmware layer's lights and their LEDs: where they sit in the zone's frame
        # and the LED set the layer's emulation is drawn on. Copies go to the lights;
        # claims only to the preview.
        self._copy_targets: list[tuple[int, NDArray[np.intp], LedSet]] = []
        self._claim_targets: list[tuple[int, NDArray[np.intp], LedSet]] = []
        self._lights: tuple[ZoneLight, ...] = ()
        self._rendering = ""
        self._last_crash_log = float("-inf")
        self._render_s = 0.0  # moving average of the render time
        self._stride = 1
        self._ticks = 0
        self._rendered: deque[float] = deque()
        self._below_since: float | None = None
        self._capacity = int(max_lookahead_s * fps) + 2
        self.ring: RingBuffer
        self.leds: LedSet
        self._space = space
        self._place(lights)
        self._compile()

    # --- what the zone looks like from outside -------------------------------------

    @property
    def lights(self) -> tuple[ZoneLight, ...]:
        return self._lights

    @property
    def space(self) -> Space:
        return self._space

    @property
    def field_effect(self) -> FieldEffect | None:
        """The bottom field layer's effect: a classic look's only one."""
        return self._fields[0][1] if self._fields else None

    @property
    def waiting_for(self) -> tuple[str, ...]:
        return tuple(need for need in self.look.needs if need not in ALWAYS_AVAILABLE)

    @property
    def state(self) -> ZoneState:
        if self.crash is not None:
            return "crashed"
        if self.waiting_for:
            return "waiting"
        return "slow" if self.slow_since is not None else "running"

    @property
    def fps_actual(self) -> float:
        return float(len(self._rendered))

    @property
    def fps_target(self) -> int:
        return self._fps

    @property
    def horizon_s(self) -> float:
        """The largest latency of the zone's lights that take its frames, plus one frame,
        within the lookahead. A light running its own effect, or not connected (latency
        None), takes none."""
        latency = 0.0
        for light in self._lights:
            if light.device_id not in self._claims:
                light_s = self._latency_s(light.device_id)
                if light_s is not None and light_s > latency:
                    latency = light_s
        return min(latency + 1.0 / self._fps, self._max_lookahead_s)

    def claim_for(self, device_id: str) -> tuple[Layer, FirmwareEffect] | None:
        index = self._claims.get(device_id)
        return None if index is None else self._firmware[index]

    def mode_of(self, device_id: str) -> LightMode:
        if device_id in self._claims:
            return "own-effect"
        if device_id in self._copies:
            return "streamed-copy"
        return "streaming"

    def effect_name(self, device_id: str) -> str | None:
        index = self._claims.get(device_id, self._copies.get(device_id))
        return None if index is None else self._firmware[index][1].display_name

    def route_for(self, device_id: str) -> DeviceRoute | None:
        piece = self.leds.slice_for(device_id)
        if piece is None or piece.count == 0:
            return None
        return DeviceRoute(self, device_id, streaming=device_id not in self._claims)

    # --- changes --------------------------------------------------------------------

    def set_lights(self, lights: Sequence[ZoneLight], space: Space | None = None) -> None:
        """Rebuild the LED set, in a new space if one is given. Routes read the ring and
        the LED set at each send, so they need nothing. A new ring starts only when the
        frame's layout changed (which device's LEDs sit where): a light moved or a new
        space keeps the frames coming, with no warm-up."""
        if space is not None:
            self._space = space
        self._place(lights)
        self._plan_claims()

    def set_brightness(self, value: float) -> None:
        self.brightness = value
        if self._claims:
            self.generation = next(_GENERATIONS)  # firmware effects take it when they start

    def update_look(self, look: Look) -> None:
        """Take new settings in place when the layers are the same, else rebuild the look.

        In place keeps each effect's state, so a chase keeps its position while a slider
        moves; blend and opacity are read from the layer each frame. The generation moves
        on only when firmware lights need their effect again.
        """
        old, self.look = self.look, look
        if self.crash is not None or _layout(old) != _layout(look) or old.needs != look.needs:
            self._compile()
            return
        for index, layer in enumerate(visible_field_layers(look)):
            old_layer, field_effect = self._fields[index]
            if old_layer.settings != layer.settings:
                field_effect.set_params(**layer.settings)
            self._fields[index] = (layer, field_effect)
        resend = False
        for index, layer in enumerate(reversed(firmware_layers(look))):
            old_layer, firmware = self._firmware[index]
            if old_layer.settings != layer.settings:
                firmware.set_params(**layer.settings)
                resend = True
            self._firmware[index] = (layer, firmware)
        if resend:
            self.generation = next(_GENERATIONS)

    def restart(self) -> None:
        """Re-create the look (spec §8), and give rejected firmware effects another try."""
        self._emulated.clear()
        self._compile()

    def mark_emulated(self, device_id: str) -> None:
        """The light refused its firmware effect: stream that layer's copy to it instead."""
        index = self._claims.pop(device_id, None)
        if index is not None:
            self._emulated.add(device_id)
            self._copies[device_id] = index
            self._copy_targets = self._targets(self._copies)
            self._claim_targets = self._targets(self._claims)

    # --- rendering ------------------------------------------------------------------

    def tick(self, now: float) -> None:
        """Render the frame shown at now + horizon, unless crashed or skipping for budget."""
        if self.crash is not None:
            return
        self._ticks += 1
        if self._ticks % self._stride:
            return
        target = now + self.horizon_s
        ctx = render_context(self._clock, target, self._stride / self._fps)
        started = self._timer()
        try:
            colors = self._render(ctx)
        except Exception as exc:  # a look never takes the engine down (spec §8)
            self._fail(self._rendering, f"{type(exc).__name__}: {exc}")
            return
        elapsed = self._timer() - started
        self.ring.write(
            RenderedFrame(
                colors=colors,
                target_time=target,
                beat_phase=ctx.beat_phase,
                bar_phase=ctx.bar_phase,
            )
        )
        self._track_speed(now, elapsed)

    def _render(self, ctx: RenderContext) -> FloatRGB:
        """A new frame every tick: the ring keeps it. The field layers blend bottom to top;
        then each firmware layer's emulation is drawn on its lights. Waiting, it's dark."""
        frame = np.zeros((self.leds.count, 3), dtype=np.float32)
        if self.waiting_for or self.leds.count == 0:
            return frame
        for layer, field_effect in self._fields:
            self._rendering = layer.name
            colors = _finite(field_effect.render(ctx, self.leds))
            blend_into(frame, colors, layer.blend, layer.opacity)
        targets = self._copy_targets
        if self._claim_targets and self._watched():
            targets = [*targets, *self._claim_targets]
        for index, where, leds in targets:
            layer, firmware = self._firmware[index]
            self._rendering = layer.name
            frame[where] = _finite(firmware.emulate(ctx, leds)) * np.float32(layer.opacity)
        frame *= np.float32(self.brightness)
        return frame

    def _compile(self) -> None:
        self.generation = next(_GENERATIONS)
        self.crash = None
        self._fields = []
        self._firmware = []
        self._selectors = []
        layers = visible_field_layers(self.look) + list(reversed(firmware_layers(self.look)))
        for position, layer in enumerate(layers):
            try:
                effect = make_effect(layer)
            except LookError as exc:
                self._fields, self._firmware, self._selectors = [], [], []
                self._fail(layer.name, str(exc))
                break
            effect.reseed(self._seed + position)
            if isinstance(effect, FirmwareEffect):
                self._firmware.append((layer, effect))
                self._selectors.append(layer.lights)
            else:
                self._fields.append((layer, effect))
        self._plan_claims()

    def _place(self, lights: Sequence[ZoneLight]) -> None:
        self._lights = tuple(lights)
        before = getattr(self, "leds", None)
        self.leds = build_ledset(
            [
                LedSource(
                    light.device_id, light.led_count, light.geometry, light.placed, light.room
                )
                for light in self._lights
            ],
            self._space,
        )
        if before is None or before.slices != self.leds.slices:
            self.ring = RingBuffer(self._capacity)
        self._emulated &= {light.device_id for light in self._lights}

    def _picks(self, index: int, light: ZoneLight) -> bool:
        selectors = self._selectors[index]
        if selectors is None:
            return True
        ids = {light.device_id, light.light_id}
        return selects(selectors, ids, f"{light.name} {light.caps.model}")

    def _plan_claims(self) -> None:
        """Which firmware layer each light runs itself or takes a copy of: the top layer
        that picks the light and that it supports. A light no layer claims takes the copy
        of the top layer that picks it, but only when there is no field layer to play.
        A light that refuses its effect later (mark_emulated) keeps its layer's copy."""
        self._claims = {}
        self._copies = {}
        self._copy_targets = []
        self._claim_targets = []
        if self.crash is not None or self.waiting_for or not self._firmware:
            return
        for light in self._lights:
            picked = [i for i in range(len(self._firmware)) if self._picks(i, light)]
            index = next((i for i in picked if self._firmware[i][1].supports(light.caps)), None)
            if index is None:
                if not self._fields and picked:
                    self._copies[light.device_id] = picked[0]
            elif light.device_id in self._emulated:
                self._copies[light.device_id] = index
            else:
                self._claims[light.device_id] = index
        self._copy_targets = self._targets(self._copies)
        self._claim_targets = self._targets(self._claims)

    def _targets(self, layer_of: Mapping[str, int]) -> list[tuple[int, NDArray[np.intp], LedSet]]:
        targets: list[tuple[int, NDArray[np.intp], LedSet]] = []
        for index in sorted(set(layer_of.values())):
            where, leds = self.leds.subset({d for d, i in layer_of.items() if i == index})
            if len(where):
                targets.append((index, where, leds))
        return targets

    def _fail(self, layer: str, message: str) -> None:
        self.crash = CrashInfo(layer=layer, message=message, at=self._now())
        self._state_changed()
        stamp = time.monotonic()
        if stamp - self._last_crash_log >= CRASH_LOG_INTERVAL_S:
            self._last_crash_log = stamp
            logger.error(
                "Zone {}: layer '{}' crashed, holding the last frame: {}",
                self.zone_id,
                layer,
                message,
            )

    def _track_speed(self, now: float, elapsed: float) -> None:
        self._render_s = elapsed if self._render_s == 0.0 else 0.9 * self._render_s + 0.1 * elapsed
        self._stride = max(1, min(self._fps, math.ceil(self._render_s / FRAME_BUDGET_S)))
        self._rendered.append(now)
        trim_window(self._rendered, now)
        if len(self._rendered) < SLOW_RATIO * self._fps:
            if self._below_since is None:
                self._below_since = now
            if self.slow_since is None and now - self._below_since >= SLOW_AFTER_S:
                self.slow_since = self._now()
                self._state_changed()
        else:
            self._below_since = None
            if self.slow_since is not None:
                self.slow_since = None
                self._state_changed()

    def _state_changed(self) -> None:
        if self._on_state_change is not None:
            self._on_state_change(self)
