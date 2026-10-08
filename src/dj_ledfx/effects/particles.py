"""Particle effects (spec §5.1): particles that move through the home, emitted from, led
along and drawn to its anchors and lamps, lighting the LEDs near them.

A particle effect is placed among a layer's LEDs (place()), moves its particles to a
moment (step()) and lights the LEDs from them (sample()). ParamParticles keeps its
settings as a field effect does and works its particles out from the moment, the seed and
the LEDs alone (positions()), so the same moment always gives the same particles: frames
repeat, a twin draws what its zone draws, and a particle that lands on a beat lands on it
however the frames fall.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING

from dj_ledfx.effects.base import Effect, ParamSettings
from dj_ledfx.effects.particle_tools import NO_PARTICLES, Ground, Particles, lit

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB

MAX_PARTICLES = 500  # spec §5.1: "capped at about 500"; step() keeps the newest


class ParticleEffect(Effect):
    @abstractmethod
    def place(self, leds: LedSet) -> None:
        """Where the particles move: the layer's view of its zone's LEDs. Cheap to call
        again with the same set."""

    @abstractmethod
    def step(self, ctx: RenderContext) -> None:
        """Move the particles to ctx's moment."""

    @abstractmethod
    def sample(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        """Each LED's light from the particles: shape (leds.count, 3) float32, 0..1."""

    @property
    @abstractmethod
    def particles(self) -> Particles:
        """The particles of the last step, oldest first."""


class ParamParticles(ParamSettings, ParticleEffect):
    """A particle effect that keeps its settings in one dict (ParamSettings) and its
    particles in closed form: positions() gives the particles at any moment from the
    moment, the seed and the Ground alone."""

    _ground: Ground | None = None
    _particles: Particles = NO_PARTICLES

    def place(self, leds: LedSet) -> None:
        self._placed(leds)

    def step(self, ctx: RenderContext) -> None:
        ground = self._ground
        if ground is None or ground.leds.count == 0:
            self._particles = NO_PARTICLES
            return
        self._particles = self.positions(ctx, ground).newest(MAX_PARTICLES)

    def sample(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        return lit(self._placed(leds), self._particles)

    @property
    def particles(self) -> Particles:
        return self._particles

    @abstractmethod
    def positions(self, ctx: RenderContext, ground: Ground) -> Particles:
        """The particles at ctx's moment, among the ground's LEDs (at least one)."""

    def _placed(self, leds: LedSet) -> Ground:
        """The ground of these LEDs, worked out again only for another set."""
        ground = self._ground
        if ground is None or ground.leds is not leds:
            ground = self._ground = Ground.of(leds)
        return ground


def drawn(effect: ParticleEffect, ctx: RenderContext, leds: LedSet) -> FloatRGB:
    """A particle effect's frame on these LEDs at ctx's moment: placed, stepped, sampled."""
    effect.place(leds)
    effect.step(ctx)
    return effect.sample(ctx, leds)
