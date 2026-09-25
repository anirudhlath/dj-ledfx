from __future__ import annotations

import numpy as np
import pytest

from dj_ledfx.effects.blend import blend_into

BASE = (0.2, 0.4, 0.6)
TOP = (0.5, 0.5, 0.5)


@pytest.mark.parametrize(
    ("mode", "opacity", "expected"),
    [
        ("normal", 1.0, (0.5, 0.5, 0.5)),
        ("normal", 0.5, (0.35, 0.45, 0.55)),
        ("add", 1.0, (0.7, 0.9, 1.1)),  # not clamped: that happens once, at send
        ("add", 0.5, (0.45, 0.65, 0.85)),
        ("screen", 1.0, (0.6, 0.7, 0.8)),
        ("multiply", 1.0, (0.1, 0.2, 0.3)),
        ("max", 1.0, (0.5, 0.5, 0.6)),
        ("screen", 0.0, BASE),
    ],
)
def test_each_blend_mode(mode: str, opacity: float, expected: tuple[float, ...]) -> None:
    base = np.array([BASE], dtype=np.float32)
    blend_into(base, np.array([TOP], dtype=np.float32), mode, opacity)
    assert base.dtype == np.float32
    assert np.allclose(base, [expected])


def test_an_unknown_blend_mode_is_refused() -> None:
    with pytest.raises(ValueError, match="dodge"):
        blend_into(np.zeros((1, 3), np.float32), np.zeros((1, 3), np.float32), "dodge", 1.0)
