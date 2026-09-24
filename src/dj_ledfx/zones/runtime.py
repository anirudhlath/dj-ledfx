"""One running zone: its look, its LEDs and the frames it renders ahead (spec §4.1, §8)."""

from __future__ import annotations

import math
import time
from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Literal

import numpy as np
from loguru import logger

from dj_ledfx.effects.context import render_context
from dj_ledfx.effects.engine import RingBuffer
from dj_ledfx.effects.firmware import FirmwareEffect
from dj_ledfx.effects.ledset import DeviceSlice, LedSource, build_ledset
from dj_ledfx.looks.model import (
    Layer,
    Look,
    LookError,
    firmware_layers,
    make_effect,
    visible_field_layer,
)
from dj_ledfx.scheduling.route import DeviceRoute
from dj_ledfx.types import RenderedFrame
from dj_ledfx.zones.model import CrashInfo

if TYPE_CHECKING:
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

ZoneState = Literal["running", "slow", "crashed", "waiting"]
LightMode = Literal["streaming", "own-effect", "streamed-copy"]


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _finite(colors: FloatRGB) -> FloatRGB:
    if not np.isfinite(colors).all():
        raise FloatingPointError("the layer produced NaN or infinite colours")
    return colors


def _layout(look: Look) -> list[tuple[str, str, str, bool]]:
    return [(layer.id, layer.type, layer.kind, layer.visible) for layer in look.layers]


@dataclass(frozen=True, slots=True)
class ZoneLight:
    """One light as its zone sees it."""

    device_id: str
    led_count: int
    caps: DeviceCapabilities
    geometry: DeviceGeometry | None = None


class ZoneRuntime:
    """Renders one running zone's look ahead of time into its own ring buffer."""

    def __init__(
        self,
        zone_id: str,
        look: Look,
        lights: Sequence[ZoneLight],
        *,
        clock: BeatClock,
        latency_s: Callable[[str], float],
        fps: int = 60,
        max_lookahead_s: float = 1.0,
        brightness: float = 1.0,
        seed: int = 0,
        timer: Callable[[], float] = time.perf_counter,
        now: Callable[[], datetime] = _utcnow,
    ) -> None:
        self.zone_id = zone_id
        self.look = look
        self.brightness = brightness
        self.generation = 0
        self.crash: CrashInfo | None = None
        self.slow_since: datetime | None = None
        self._clock = clock
        self._latency_s = latency_s
        self._fps = fps
        self._max_lookahead_s = max_lookahead_s
        self._seed = seed
        self._timer = timer
        self._now = now
        self._field: tuple[Layer, FieldEffect] | None = None
        self._firmware: list[tuple[Layer, FirmwareEffect]] = []  # top layer first
        self._claims: dict[str, int] = {}  # light -> firmware layer it runs itself
        self._copies: dict[str, int] = {}  # light -> firmware layer streamed as a copy
        self._emulated: set[str] = set()  # lights that rejected their firmware effect
        self._lights: tuple[ZoneLight, ...] = ()
        self._slices: dict[str, DeviceSlice] = {}
        self._rendering = ""
        self._last_crash_log = float("-inf")
        self._render_s = 0.0  # moving average of the render time
        self._stride = 1
        self._ticks = 0
        self._rendered: deque[float] = deque()
        self._below_since: float | None = None
        self.ring = RingBuffer(capacity=int(max_lookahead_s * fps) + 2, led_count=0)
        self.leds = build_ledset([])
        self.set_lights(lights)
        self._compile()

    # --- what the zone looks like from outside -------------------------------------

    @property
    def lights(self) -> tuple[ZoneLight, ...]:
        return self._lights

    @property
    def field_effect(self) -> FieldEffect | None:
        return self._field[1] if self._field is not None else None

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
        """The zone's largest device latency plus one frame, within the lookahead."""
        latency = max((self._latency_s(light.device_id) for light in self._lights), default=0.0)
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
        piece = self._slices.get(device_id)
        if piece is None or piece.count == 0:
            return None
        return DeviceRoute(
            zone_id=self.zone_id,
            ring=self.ring,
            start=piece.start,
            stop=piece.stop,
            streaming=device_id not in self._claims,
        )

    # --- changes --------------------------------------------------------------------

    def set_lights(self, lights: Sequence[ZoneLight]) -> None:
        """Rebuild the LED set and start a fresh ring, so no route outlives its frames."""
        self._lights = tuple(lights)
        self.leds = build_ledset(
            [LedSource(light.device_id, light.led_count, light.geometry) for light in self._lights]
        )
        self._slices = {piece.device_id: piece for piece in self.leds.slices}
        self.ring = RingBuffer(capacity=self.ring.capacity, led_count=self.leds.count)
        self._emulated &= set(self._slices)
        self._plan_claims()

    def set_brightness(self, value: float) -> None:
        self.brightness = value
        if self._claims:
            self.generation += 1  # firmware effects take the brightness when they start

    def update_look(self, look: Look) -> None:
        """Take new settings in place when the layers are the same, else rebuild the look.

        In place keeps each effect's state, so a chase keeps its position while a slider
        moves. The generation moves on only when firmware lights need their effect again.
        """
        old, self.look = self.look, look
        if self.crash is not None or _layout(old) != _layout(look) or old.needs != look.needs:
            self._compile()
            return
        field_layer = visible_field_layer(look)
        if self._field is not None and field_layer is not None:
            self._field[1].set_params(**field_layer.settings)
            self._field = (field_layer, self._field[1])
        resend = False
        for index, layer in enumerate(reversed(firmware_layers(look))):
            old_layer, effect = self._firmware[index]
            if old_layer.settings != layer.settings:
                effect.set_params(**layer.settings)
                resend = True
            self._firmware[index] = (layer, effect)
        if resend:
            self.generation += 1

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
        frame = np.zeros((self.leds.count, 3), dtype=np.float32)
        if self.waiting_for or self.leds.count == 0:
            return frame
        if self._field is not None:
            layer, effect = self._field
            self._rendering = layer.name
            frame[:] = _finite(effect.render(ctx, self.leds)) * np.float32(layer.opacity)
        assigned = [*self._claims.items(), *self._copies.items()]
        for index in sorted({owner for _, owner in assigned}):
            layer, firmware = self._firmware[index]
            self._rendering = layer.name
            copy = _finite(firmware.emulate(ctx, self.leds)) * np.float32(layer.opacity)
            for device_id, owner in assigned:
                if owner == index:
                    piece = self._slices[device_id]
                    frame[piece.start : piece.stop] = copy[piece.start : piece.stop]
        frame *= np.float32(self.brightness)
        return frame

    def _compile(self) -> None:
        self.generation += 1
        self.crash = None
        self._field = None
        self._firmware = []
        field_layer = visible_field_layer(self.look)
        layers = [field_layer] if field_layer is not None else []
        layers += list(reversed(firmware_layers(self.look)))
        for layer in layers:
            try:
                effect = make_effect(layer)
            except LookError as exc:
                self._field = None
                self._firmware = []
                self._fail(layer.name, str(exc))
                break
            effect.reseed(self._seed)
            if isinstance(effect, FirmwareEffect):
                self._firmware.append((layer, effect))
            else:
                self._field = (layer, effect)
        self._plan_claims()

    def _plan_claims(self) -> None:
        self._claims = {}
        self._copies = {}
        if self.crash is not None or self.waiting_for or not self._firmware:
            return
        for light in self._lights:
            index = next(
                (i for i, (_, fw) in enumerate(self._firmware) if fw.supports(light.caps)),
                None,
            )
            if index is None:
                if self._field is None:
                    self._copies[light.device_id] = 0  # the top layer's streamed copy
            elif light.device_id in self._emulated:
                self._copies[light.device_id] = index
            else:
                self._claims[light.device_id] = index

    def _fail(self, layer: str, message: str) -> None:
        self.crash = CrashInfo(layer=layer, message=message, at=self._now())
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
        while now - self._rendered[0] > 1.0:
            self._rendered.popleft()
        if len(self._rendered) < SLOW_RATIO * self._fps:
            if self._below_since is None:
                self._below_since = now
            if self.slow_since is None and now - self._below_since >= SLOW_AFTER_S:
                self.slow_since = self._now()
        else:
            self._below_since = None
            self.slow_since = None
