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
from dj_ledfx.effects.fx import Fx
from dj_ledfx.effects.particle_tools import NO_PARTICLES, Among, Ground, Particles, lit

if TYPE_CHECKING:
    from dj_ledfx.effects.context import RenderContext
    from dj_ledfx.effects.ledset import LedSet
    from dj_ledfx.types import FloatRGB

# Spec §5.1: "capped at about 500". Each effect keeps to it itself, so that every particle lives
# out its life; step() keeps the newest of the particles of one that doesn't.
MAX_PARTICLES = 500


class ParticleEffect(Effect):
    @abstractmethod
    def place(self, leds: LedSet, among: Among = None) -> None:
        """Where the particles move: the layer's view of its zone's LEDs, every one of which
        they light, and of those the ones `among` marks (its mask's LEDs: None, all of
        them), the only ones they go to. Cheap to call again with the same set and mask."""

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

    def in_space(self, ctx: RenderContext, leds: LedSet) -> Fx | None:
        """The last step's particles: where each is, its colour and its radius."""
        particles = self.particles
        return Fx(particles=particles) if particles.count else None


class ParamParticles(ParamSettings, ParticleEffect):
    """A particle effect that keeps its settings in one dict (ParamSettings) and its
    particles in closed form: positions() gives the particles at any moment from the
    moment, the seed and the Ground alone."""

    _ground: Ground | None = None
    _particles: Particles = NO_PARTICLES

    def place(self, leds: LedSet, among: Among = None) -> None:
        self._placed(leds, among)

    def step(self, ctx: RenderContext) -> None:
        ground = self._ground
        # positions() goes by the stops, and a set with no LEDs (or a mask of none) has none.
        if ground is None or ground.lamps.count == 0:
            self._particles = NO_PARTICLES
            return
        self._particles = self.positions(ctx, ground).newest(MAX_PARTICLES)

    def sample(self, ctx: RenderContext, leds: LedSet) -> FloatRGB:
        ground = self._ground
        if ground is None or ground.leds is not leds:  # the set placed lights whatever its mask
            ground = self._placed(leds)
        return lit(ground, self._particles)

    @property
    def particles(self) -> Particles:
        return self._particles

    @abstractmethod
    def positions(self, ctx: RenderContext, ground: Ground) -> Particles:
        """The particles at ctx's moment, among the ground's LEDs (at least one stop, so at
        least one LED)."""

    def _placed(self, leds: LedSet, among: Among = None) -> Ground:
        """The ground of these LEDs and this mask of them, worked out again only for another
        set or another mask."""
        ground = self._ground
        if ground is None or not ground.holds(leds, among):
            ground = self._ground = Ground.of(leds, among)
        return ground


def drawn(
    effect: ParticleEffect, ctx: RenderContext, leds: LedSet, among: Among = None
) -> FloatRGB:
    """A particle effect's frame on these LEDs at ctx's moment: placed (its lamps among the
    LEDs `among` marks), stepped, sampled."""
    effect.place(leds, among)
    effect.step(ctx)
    return effect.sample(ctx, leds)
