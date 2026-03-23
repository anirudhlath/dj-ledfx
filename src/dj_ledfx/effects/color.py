"""Color math utilities for effects."""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def hsv_to_rgb_array(
    h: NDArray[np.float64],
    s: float | NDArray[np.float64],
    v: float | NDArray[np.float64],
) -> NDArray[np.uint8]:
    """Vectorized HSV to RGB. h in [0,1], s in [0,1], v in [0,1]."""
    h = np.asarray(h, dtype=np.float64)
    s = np.asarray(s, dtype=np.float64)
    v = np.asarray(v, dtype=np.float64)
    n = h.shape[0]

    i = (h * 6.0).astype(int) % 6
    f = h * 6.0 - np.floor(h * 6.0)
    p = v * (1.0 - s)
    q = v * (1.0 - s * f)
    t = v * (1.0 - s * (1.0 - f))

    # Build RGB channels based on sector
    r = np.empty(n, dtype=np.float64)
    g = np.empty(n, dtype=np.float64)
    b = np.empty(n, dtype=np.float64)

    mask0 = i == 0
    mask1 = i == 1
    mask2 = i == 2
    mask3 = i == 3
    mask4 = i == 4
    mask5 = i == 5

    r[mask0] = v if np.ndim(v) == 0 else v[mask0]
    g[mask0] = t[mask0]
    b[mask0] = p if np.ndim(p) == 0 else p[mask0]

    r[mask1] = q[mask1]
    g[mask1] = v if np.ndim(v) == 0 else v[mask1]
    b[mask1] = p if np.ndim(p) == 0 else p[mask1]

    r[mask2] = p if np.ndim(p) == 0 else p[mask2]
    g[mask2] = v if np.ndim(v) == 0 else v[mask2]
    b[mask2] = t[mask2]

    r[mask3] = p if np.ndim(p) == 0 else p[mask3]
    g[mask3] = q[mask3]
    b[mask3] = v if np.ndim(v) == 0 else v[mask3]

    r[mask4] = t[mask4]
    g[mask4] = p if np.ndim(p) == 0 else p[mask4]
    b[mask4] = v if np.ndim(v) == 0 else v[mask4]

    r[mask5] = v if np.ndim(v) == 0 else v[mask5]
    g[mask5] = p if np.ndim(p) == 0 else p[mask5]
    b[mask5] = q[mask5]

    out = np.empty((n, 3), dtype=np.uint8)
    out[:, 0] = np.clip(r * 255.0, 0, 255).astype(np.uint8)
    out[:, 1] = np.clip(g * 255.0, 0, 255).astype(np.uint8)
    out[:, 2] = np.clip(b * 255.0, 0, 255).astype(np.uint8)
    return out


def palette_lerp(
    palette: list[tuple[int, int, int]],
    positions: NDArray[np.float64],
) -> NDArray[np.uint8]:
    """Interpolate between palette colors at 0-1 positions."""
    n_colors = len(palette)
    if n_colors == 1:
        out = np.empty((len(positions), 3), dtype=np.uint8)
        out[:] = palette[0]
        return out

    palette_arr = np.array(palette, dtype=np.float64)  # (n_colors, 3)
    # Scale positions to palette index space
    scaled = np.clip(positions, 0.0, 1.0) * (n_colors - 1)
    idx_low = np.floor(scaled).astype(int)
    idx_high = np.minimum(idx_low + 1, n_colors - 1)
    frac = scaled - idx_low

    # Lerp between adjacent colors
    low_colors = palette_arr[idx_low]  # (n, 3)
    high_colors = palette_arr[idx_high]  # (n, 3)
    result = low_colors + (high_colors - low_colors) * frac[:, np.newaxis]
    return np.clip(result, 0, 255).astype(np.uint8)  # type: ignore[return-value]
