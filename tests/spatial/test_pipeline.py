"""Tests for ScenePipeline."""
import pytest

from dj_ledfx.effects.beat_pulse import BeatPulse
from dj_ledfx.effects.deck import EffectDeck
from dj_ledfx.effects.engine import RingBuffer
from dj_ledfx.spatial.pipeline import ScenePipeline


def test_scene_pipeline_creation():
    deck = EffectDeck(BeatPulse())
    buf = RingBuffer(capacity=60, led_count=60)
    pipeline = ScenePipeline(
        scene_id="dj-booth", deck=deck, ring_buffer=buf,
        compositor=None, mapping=None, devices=[], led_count=60,
    )
    assert pipeline.scene_id == "dj-booth"
    assert pipeline.led_count == 60
    assert pipeline.deck is deck
    assert pipeline.ring_buffer is buf


def test_scene_pipeline_shared_deck():
    deck = EffectDeck(BeatPulse())
    p1 = ScenePipeline(
        scene_id="booth", deck=deck, ring_buffer=RingBuffer(60, 60),
        compositor=None, mapping=None, devices=[], led_count=60,
    )
    p2 = ScenePipeline(
        scene_id="floor", deck=deck, ring_buffer=RingBuffer(60, 100),
        compositor=None, mapping=None, devices=[], led_count=100,
    )
    assert p1.deck is p2.deck
    assert p1.ring_buffer is not p2.ring_buffer
