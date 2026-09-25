from __future__ import annotations

from types import MappingProxyType

import numpy as np

from dj_ledfx.effects.color import palette_at, palette_float
from dj_ledfx.effects.field_tools import anchor_or_centre, distances, height01, smoothstep
from dj_ledfx.effects.ledset import LedSource, PlacedLeds, Space, build_ledset

POINTS = np.array([[0.0, 0.0, 0.0], [2.0, 0.0, 1.5], [4.0, 2.0, 3.0]])


def test_an_anchor_or_the_middle_of_the_zone() -> None:
    sofa = np.array([1.0, 1.0, 0.5], dtype=np.float32)
    with_sofa = build_ledset(
        [LedSource("strip", 3, placed=PlacedLeds.from_positions(POINTS))],
        Space(anchors=MappingProxyType({"sofa": sofa})),
    )
    assert np.allclose(anchor_or_centre(with_sofa, "sofa"), sofa)
    assert np.allclose(anchor_or_centre(with_sofa, "gone"), [2.0, 1.0, 1.5])
    assert np.allclose(anchor_or_centre(with_sofa, ""), [2.0, 1.0, 1.5])
    assert np.allclose(distances(with_sofa, np.zeros(3, dtype=np.float32))[1], 2.5)


def test_height_is_measured_against_the_ceiling_or_the_zone() -> None:
    placed = PlacedLeds.from_positions(POINTS)
    mapped = build_ledset([LedSource("strip", 3, placed=placed)], Space(ceiling=3.0))
    unmapped = build_ledset([LedSource("strip", 3, placed=placed)])
    assert np.allclose(height01(mapped), [0.0, 0.5, 1.0])
    assert np.allclose(height01(unmapped), [0.0, 0.5, 1.0])  # the zone's own bottom to top
    high = build_ledset(
        [LedSource("strip", 3, placed=PlacedLeds.from_positions(POINTS + [0, 0, 1.0]))],
        Space(ceiling=3.0),
    )
    assert np.allclose(height01(high), [1 / 3, 2.5 / 3, 1.0])  # clipped at the ceiling


def test_float_palettes_blend_between_their_stops() -> None:
    palette = palette_float(["#000000", "#ff0000", "#ffffff"])
    assert palette.shape == (3, 3) and palette.dtype == np.float32
    colours = palette_at(palette, np.array([0.0, 0.25, 0.5, 1.0, 2.0]))
    assert np.allclose(colours[1], [0.5, 0.0, 0.0])
    assert np.allclose(colours[2], [1.0, 0.0, 0.0])
    assert np.allclose(colours[3:], 1.0)  # past the end holds the last stop
    assert np.allclose(palette_at(palette[:1], np.array([0.3, 0.9])), 0.0)


def test_smoothstep() -> None:
    assert np.allclose(
        smoothstep(0.0, 1.0, np.array([-1.0, 0.0, 0.5, 1.0, 2.0])), [0, 0, 0.5, 1, 1]
    )
