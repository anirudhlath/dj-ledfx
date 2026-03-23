# Effect Library Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the effect library from 1 (BeatPulse) to 6 polished effects with shared utilities and automatic energy adaptation via BPM.

**Architecture:** Add `BeatContext` dataclass to decouple effects from transport state. Build three utility modules (color, easing, energy) under `effects/`. Migrate the render signature once, then build 5 new effects on top. All effects are pure numpy math (synchronous, no I/O) except FireStorm which carries temporal state.

**Tech Stack:** Python 3.12, numpy, pytest, ruff, mypy

**Spec:** `docs/superpowers/specs/2026-03-23-effect-library-expansion-design.md`

---

## File Map

### New files
| File | Responsibility |
|------|---------------|
| `src/dj_ledfx/effects/color.py` | Color math: hex/RGB conversion, HSV→RGB vectorized, palette interpolation |
| `src/dj_ledfx/effects/easing.py` | Easing functions: lerp, ease_in/out, sine_ease |
| `src/dj_ledfx/effects/energy.py` | BPM→energy mapping |
| `src/dj_ledfx/effects/breathe.py` | Breathe effect |
| `src/dj_ledfx/effects/strobe.py` | Strobe effect |
| `src/dj_ledfx/effects/color_chase.py` | ColorChase effect |
| `src/dj_ledfx/effects/rainbow_wave.py` | RainbowWave effect |
| `src/dj_ledfx/effects/fire_storm.py` | FireStorm effect |
| `tests/effects/test_color.py` | Color utility tests |
| `tests/effects/test_easing.py` | Easing utility tests |
| `tests/effects/test_energy.py` | Energy utility tests |
| `tests/effects/test_breathe.py` | Breathe effect tests |
| `tests/effects/test_strobe.py` | Strobe effect tests |
| `tests/effects/test_color_chase.py` | ColorChase effect tests |
| `tests/effects/test_rainbow_wave.py` | RainbowWave effect tests |
| `tests/effects/test_fire_storm.py` | FireStorm effect tests |

### Modified files
| File | Change |
|------|--------|
| `src/dj_ledfx/types.py` | Add `BeatContext` dataclass |
| `src/dj_ledfx/effects/base.py` | Change `render()` signature to `(self, ctx: BeatContext, led_count: int)` |
| `src/dj_ledfx/effects/deck.py` | Update `render()` to pass `BeatContext` |
| `src/dj_ledfx/effects/engine.py` | Construct `BeatContext` from `BeatState` in `tick()` |
| `src/dj_ledfx/effects/beat_pulse.py` | Migrate to `BeatContext`, use shared `hex_to_rgb` from `color.py` |
| `src/dj_ledfx/effects/__init__.py` | Add imports for new effect modules |
| `tests/effects/test_beat_pulse.py` | Update 7 `.render()` calls to use `BeatContext` |
| `tests/effects/test_registry.py` | Update `DummyEffect.render()` and `_BadEffect.render()` signatures |
| `tests/effects/test_deck.py` | Update 2 `deck.render()` calls to use `BeatContext` |
| `tests/effects/test_engine.py` | No direct render calls — engine constructs `BeatContext` internally |

---

### Task 1: Add BeatContext to types.py

**Files:**
- Modify: `src/dj_ledfx/types.py:35` (after `BeatState`)
- Test: `tests/test_types.py`

- [ ] **Step 1: Write the test**

In `tests/test_types.py`, add:

```python
from dj_ledfx.types import BeatContext

def test_beat_context_creation():
    ctx = BeatContext(beat_phase=0.5, bar_phase=0.25, bpm=128.0, dt=0.016)
    assert ctx.beat_phase == 0.5
    assert ctx.bar_phase == 0.25
    assert ctx.bpm == 128.0
    assert ctx.dt == 0.016

def test_beat_context_is_frozen():
    import pytest
    ctx = BeatContext(beat_phase=0.5, bar_phase=0.25, bpm=128.0, dt=0.016)
    with pytest.raises(AttributeError):
        ctx.bpm = 130.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_types.py::test_beat_context_creation tests/test_types.py::test_beat_context_is_frozen -v`
Expected: FAIL — `ImportError: cannot import name 'BeatContext'`

- [ ] **Step 3: Implement BeatContext**

In `src/dj_ledfx/types.py`, add after the `BeatState` dataclass:

```python
@dataclass(frozen=True, slots=True)
class BeatContext:
    """Minimal beat state for effect rendering. Intentionally strips transport
    fields from BeatState (is_playing, next_beat_time, etc.) to keep the
    effect API narrow."""
    beat_phase: float  # 0.0-1.0 within current beat
    bar_phase: float   # 0.0-1.0 within current 4-beat bar
    bpm: float         # current pitch-adjusted BPM
    dt: float          # frame delta (seconds)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_types.py::test_beat_context_creation tests/test_types.py::test_beat_context_is_frozen -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/types.py tests/test_types.py
git commit -m "feat: add BeatContext dataclass to types"
```

---

### Task 2: Migrate render signature (Effect ABC, Deck, Engine)

**Files:**
- Modify: `src/dj_ledfx/effects/base.py:68-76`
- Modify: `src/dj_ledfx/effects/deck.py:47-54`
- Modify: `src/dj_ledfx/effects/engine.py:145-165`
- Modify: `src/dj_ledfx/effects/beat_pulse.py:54-70`
- Modify: `tests/effects/test_beat_pulse.py` (7 render calls)
- Modify: `tests/effects/test_registry.py` (2 render signatures)
- Modify: `tests/effects/test_deck.py` (2 render calls)

- [ ] **Step 1: Update Effect ABC render signature**

In `src/dj_ledfx/effects/base.py`, change import and render method:

```python
# Add to imports
from dj_ledfx.types import BeatContext

# Change render signature (line 68-76)
@abstractmethod
def render(
    self,
    ctx: BeatContext,
    led_count: int,
) -> NDArray[np.uint8]:
    """Return shape (led_count, 3) uint8 RGB array."""
```

- [ ] **Step 2: Update EffectDeck.render()**

In `src/dj_ledfx/effects/deck.py`:

```python
# Add to imports
from dj_ledfx.types import BeatContext

# Change render method (line 47-54)
def render(
    self,
    ctx: BeatContext,
    led_count: int,
) -> NDArray[np.uint8]:
    return self._effect.render(ctx, led_count)
```

- [ ] **Step 3: Update EffectEngine.tick() to construct BeatContext**

In `src/dj_ledfx/effects/engine.py`, add import and change tick:

```python
# Add to imports
from dj_ledfx.types import BeatContext, RenderedFrame

# In tick() method, replace the pipeline loop (lines 151-164):
def tick(self, now: float) -> None:
    target_time = now + self._max_lookahead_s
    state = self._clock.get_state_at(target_time)

    render_start = time.monotonic()

    ctx = BeatContext(
        beat_phase=state.beat_phase,
        bar_phase=state.bar_phase,
        bpm=state.bpm,
        dt=self._frame_period,
    )

    for pipeline in self.pipelines:
        colors = pipeline.deck.render(ctx, pipeline.led_count)
        frame = RenderedFrame(
            colors=colors,
            target_time=target_time,
            beat_phase=state.beat_phase,
            bar_phase=state.bar_phase,
        )
        pipeline.ring_buffer.write(frame)

    render_elapsed = time.monotonic() - render_start
    metrics.RENDER_DURATION.observe(render_elapsed)
    metrics.FRAMES_RENDERED.inc()
    self._render_times.append(render_elapsed)

    logger.trace(
        "Rendered {} pipeline(s) for t+{:.0f}ms",
        len(self.pipelines),
        self._max_lookahead_s * 1000,
    )
```

- [ ] **Step 4: Update BeatPulse to use BeatContext**

In `src/dj_ledfx/effects/beat_pulse.py`:

```python
# Add to imports
from dj_ledfx.types import BeatContext

# Change render signature (line 54-70)
def render(
    self,
    ctx: BeatContext,
    led_count: int,
) -> NDArray[np.uint8]:
    brightness = (1.0 - ctx.beat_phase) ** self._gamma

    color_index = int(ctx.bar_phase * len(self._palette)) % len(self._palette)
    r, g, b = self._palette[color_index]

    out = np.empty((led_count, 3), dtype=np.uint8)
    out[:, 0] = int(r * brightness)
    out[:, 1] = int(g * brightness)
    out[:, 2] = int(b * brightness)
    return out
```

- [ ] **Step 5: Update test_beat_pulse.py**

Replace all `effect.render(beat_phase=X, bar_phase=Y, dt=Z, led_count=N)` calls with `effect.render(BeatContext(beat_phase=X, bar_phase=Y, bpm=128.0, dt=Z), N)`. Add import at top:

```python
from dj_ledfx.types import BeatContext
```

Each render call becomes, e.g.:
```python
# Old: effect.render(beat_phase=0.0, bar_phase=0.0, dt=0.016, led_count=10)
# New: effect.render(BeatContext(beat_phase=0.0, bar_phase=0.0, bpm=128.0, dt=0.016), 10)
```

Apply this pattern to all 7 calls.

- [ ] **Step 6: Update test_registry.py**

Change `DummyEffect.render()` and `_BadEffect.render()` signatures:

```python
# Add import
from dj_ledfx.types import BeatContext

# DummyEffect (line 22):
def render(self, ctx: BeatContext, led_count: int):
    import numpy as np
    return np.zeros((led_count, 3), dtype=np.uint8)

# _BadEffect (line 69):
def render(self, ctx: BeatContext, led_count: int):
    import numpy as np
    return np.zeros((led_count, 3), dtype=np.uint8)
```

- [ ] **Step 7: Update test_deck.py**

Add import and update 2 render calls:

```python
from dj_ledfx.types import BeatContext

# Line 29: deck.render(0.5, 0.25, 0.016, 10) becomes:
result = deck.render(BeatContext(beat_phase=0.5, bar_phase=0.25, bpm=128.0, dt=0.016), 10)

# Line 48: deck.render(0.0, 0.0, 0.016, 5) becomes:
result = deck.render(BeatContext(beat_phase=0.0, bar_phase=0.0, bpm=128.0, dt=0.016), 5)
```

- [ ] **Step 8: Run full test suite**

Run: `uv run pytest -x -v`
Expected: All tests pass. The engine tests don't call `.render()` directly — they go through `engine.tick()` which now constructs `BeatContext` internally.

- [ ] **Step 9: Commit**

```bash
git add src/dj_ledfx/effects/base.py src/dj_ledfx/effects/deck.py src/dj_ledfx/effects/engine.py src/dj_ledfx/effects/beat_pulse.py tests/effects/test_beat_pulse.py tests/effects/test_registry.py tests/effects/test_deck.py
git commit -m "refactor: migrate render signature to BeatContext

BeatContext bundles beat_phase, bar_phase, bpm, and dt into a single
dataclass. This adds bpm as a net-new data flow through the render
pipeline, enabling energy-adaptive effects."
```

---

### Task 3: Shared utilities — easing.py

**Files:**
- Create: `src/dj_ledfx/effects/easing.py`
- Create: `tests/effects/test_easing.py`

- [ ] **Step 1: Write the tests**

Create `tests/effects/test_easing.py`:

```python
import numpy as np
import pytest

from dj_ledfx.effects.easing import ease_in, ease_in_out, ease_out, lerp, sine_ease


def test_lerp_endpoints():
    assert lerp(0.0, 10.0, 0.0) == 0.0
    assert lerp(0.0, 10.0, 1.0) == 10.0


def test_lerp_midpoint():
    assert lerp(0.0, 10.0, 0.5) == pytest.approx(5.0)


def test_lerp_numpy_array():
    t = np.array([0.0, 0.5, 1.0])
    result = lerp(0.0, 10.0, t)
    np.testing.assert_allclose(result, [0.0, 5.0, 10.0])


def test_ease_in_endpoints():
    assert ease_in(0.0) == pytest.approx(0.0)
    assert ease_in(1.0) == pytest.approx(1.0)


def test_ease_in_is_slow_at_start():
    assert ease_in(0.5) < 0.5


def test_ease_out_endpoints():
    assert ease_out(0.0) == pytest.approx(0.0)
    assert ease_out(1.0) == pytest.approx(1.0)


def test_ease_out_is_fast_at_start():
    assert ease_out(0.5) > 0.5


def test_ease_in_out_endpoints():
    assert ease_in_out(0.0) == pytest.approx(0.0)
    assert ease_in_out(1.0) == pytest.approx(1.0)


def test_ease_in_out_midpoint():
    assert ease_in_out(0.5) == pytest.approx(0.5)


def test_sine_ease_endpoints():
    assert sine_ease(0.0) == pytest.approx(0.0)
    assert sine_ease(1.0) == pytest.approx(1.0)


def test_sine_ease_numpy_array():
    t = np.array([0.0, 1.0])
    result = sine_ease(t)
    np.testing.assert_allclose(result, [0.0, 1.0], atol=1e-10)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/effects/test_easing.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement easing.py**

Create `src/dj_ledfx/effects/easing.py`:

```python
"""Easing functions for effect animations. All accept float or NDArray."""

from __future__ import annotations

import math

import numpy as np
from numpy.typing import NDArray


def lerp(
    a: float, b: float, t: float | NDArray[np.float64]
) -> float | NDArray[np.float64]:
    return a + (b - a) * t


def ease_in(
    t: float | NDArray[np.float64], power: float = 2.0
) -> float | NDArray[np.float64]:
    return t**power


def ease_out(
    t: float | NDArray[np.float64], power: float = 2.0
) -> float | NDArray[np.float64]:
    return 1.0 - (1.0 - t) ** power


def ease_in_out(
    t: float | NDArray[np.float64],
) -> float | NDArray[np.float64]:
    return 3.0 * t**2 - 2.0 * t**3


def sine_ease(
    t: float | NDArray[np.float64],
) -> float | NDArray[np.float64]:
    if isinstance(t, np.ndarray):
        return np.sin(t * (np.pi / 2.0))
    return math.sin(t * (math.pi / 2.0))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/effects/test_easing.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/effects/easing.py tests/effects/test_easing.py
git commit -m "feat: add easing utility module (lerp, ease_in/out, sine_ease)"
```

---

### Task 4: Shared utilities — energy.py

**Files:**
- Create: `src/dj_ledfx/effects/energy.py`
- Create: `tests/effects/test_energy.py`

- [ ] **Step 1: Write the tests**

Create `tests/effects/test_energy.py`:

```python
import pytest

from dj_ledfx.effects.energy import bpm_energy


def test_below_low_is_zero():
    assert bpm_energy(80.0) == 0.0


def test_above_high_is_one():
    assert bpm_energy(170.0) == 1.0


def test_at_low_boundary():
    assert bpm_energy(100.0) == pytest.approx(0.0)


def test_at_high_boundary():
    assert bpm_energy(150.0) == pytest.approx(1.0)


def test_midpoint():
    assert bpm_energy(125.0) == pytest.approx(0.5)


def test_custom_range():
    assert bpm_energy(140.0, low=120.0, high=160.0) == pytest.approx(0.5)


def test_zero_bpm():
    assert bpm_energy(0.0) == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/effects/test_energy.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement energy.py**

Create `src/dj_ledfx/effects/energy.py`:

```python
"""BPM-to-energy inference for automatic effect adaptation."""

from __future__ import annotations


def bpm_energy(bpm: float, low: float = 100.0, high: float = 150.0) -> float:
    """Map BPM to 0.0-1.0 energy level. Linear between low and high, clamped."""
    if bpm <= low:
        return 0.0
    if bpm >= high:
        return 1.0
    return (bpm - low) / (high - low)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/effects/test_energy.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/dj_ledfx/effects/energy.py tests/effects/test_energy.py
git commit -m "feat: add BPM energy inference utility"
```

---

### Task 5: Shared utilities — color.py

**Files:**
- Create: `src/dj_ledfx/effects/color.py`
- Create: `tests/effects/test_color.py`
- Modify: `src/dj_ledfx/effects/beat_pulse.py` (use shared `hex_to_rgb`)

- [ ] **Step 1: Write the tests**

Create `tests/effects/test_color.py`:

```python
import numpy as np
import pytest

from dj_ledfx.effects.color import hex_to_rgb, hsv_to_rgb_array, palette_lerp, rgb_to_hex


def test_hex_to_rgb():
    assert hex_to_rgb("#ff0000") == (255, 0, 0)
    assert hex_to_rgb("#00ff00") == (0, 255, 0)
    assert hex_to_rgb("0000ff") == (0, 0, 255)


def test_rgb_to_hex():
    assert rgb_to_hex(255, 0, 0) == "#ff0000"
    assert rgb_to_hex(0, 255, 0) == "#00ff00"


def test_hsv_to_rgb_array_red():
    h = np.array([0.0])
    result = hsv_to_rgb_array(h, 1.0, 1.0)
    assert result.shape == (1, 3)
    assert result.dtype == np.uint8
    assert result[0, 0] == 255  # R
    assert result[0, 1] == 0    # G
    assert result[0, 2] == 0    # B


def test_hsv_to_rgb_array_rainbow():
    h = np.array([0.0, 1 / 3, 2 / 3])
    result = hsv_to_rgb_array(h, 1.0, 1.0)
    assert result.shape == (3, 3)
    # Red
    assert result[0, 0] == 255
    # Green
    assert result[1, 1] == 255
    # Blue
    assert result[2, 2] == 255


def test_hsv_to_rgb_array_value_scales():
    h = np.array([0.0])
    result = hsv_to_rgb_array(h, 1.0, 0.5)
    assert result[0, 0] == 127 or result[0, 0] == 128  # ~half brightness


def test_palette_lerp_endpoints():
    palette = [(255, 0, 0), (0, 0, 255)]
    positions = np.array([0.0, 1.0])
    result = palette_lerp(palette, positions)
    assert result.shape == (2, 3)
    assert result.dtype == np.uint8
    np.testing.assert_array_equal(result[0], [255, 0, 0])
    np.testing.assert_array_equal(result[1], [0, 0, 255])


def test_palette_lerp_midpoint():
    palette = [(0, 0, 0), (200, 200, 200)]
    positions = np.array([0.5])
    result = palette_lerp(palette, positions)
    assert result[0, 0] == pytest.approx(100, abs=1)


def test_palette_lerp_wraps():
    palette = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    positions = np.array([0.0, 0.5, 1.0])
    result = palette_lerp(palette, positions)
    assert result.shape == (3, 3)


def test_palette_lerp_single_color():
    palette = [(128, 64, 32)]
    positions = np.array([0.0, 0.5, 1.0])
    result = palette_lerp(palette, positions)
    for i in range(3):
        np.testing.assert_array_equal(result[i], [128, 64, 32])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/effects/test_color.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement color.py**

Create `src/dj_ledfx/effects/color.py`:

```python
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
    low_colors = palette_arr[idx_low]      # (n, 3)
    high_colors = palette_arr[idx_high]    # (n, 3)
    result = low_colors + (high_colors - low_colors) * frac[:, np.newaxis]
    return np.clip(result, 0, 255).astype(np.uint8)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/effects/test_color.py -v`
Expected: PASS

- [ ] **Step 5: Update BeatPulse to use shared hex_to_rgb**

In `src/dj_ledfx/effects/beat_pulse.py`, replace local `_hex_to_rgb` with import:

```python
# Remove local _hex_to_rgb function and _DEFAULT_PALETTE constant that uses it
# Replace with:
from dj_ledfx.effects.color import hex_to_rgb

# In __init__, change: self._palette = [_hex_to_rgb(c) for c in colors]
# to:                   self._palette = [hex_to_rgb(c) for c in colors]

# In _apply_params, same change for palette update
```

- [ ] **Step 6: Run beat_pulse tests to verify no regression**

Run: `uv run pytest tests/effects/test_beat_pulse.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/dj_ledfx/effects/color.py tests/effects/test_color.py src/dj_ledfx/effects/beat_pulse.py
git commit -m "feat: add color utility module, use shared hex_to_rgb in BeatPulse"
```

---

### Task 6: Breathe effect

**Files:**
- Create: `src/dj_ledfx/effects/breathe.py`
- Create: `tests/effects/test_breathe.py`
- Modify: `src/dj_ledfx/effects/__init__.py`

- [ ] **Step 1: Write the tests**

Create `tests/effects/test_breathe.py`:

```python
import numpy as np
import pytest

from dj_ledfx.effects.breathe import Breathe
from dj_ledfx.types import BeatContext


def _ctx(beat_phase: float = 0.0, bar_phase: float = 0.0, bpm: float = 128.0) -> BeatContext:
    return BeatContext(beat_phase=beat_phase, bar_phase=bar_phase, bpm=bpm, dt=0.016)


def test_output_shape_and_dtype():
    effect = Breathe()
    result = effect.render(_ctx(), 10)
    assert result.shape == (10, 3)
    assert result.dtype == np.uint8


def test_brightness_never_below_min():
    effect = Breathe(min_brightness=0.1)
    # Test many phases
    for phase in np.linspace(0.0, 0.99, 20):
        result = effect.render(_ctx(bar_phase=phase), 1)
        # At min_brightness=0.1, no channel should be fully zero if palette isn't black
        assert result.max() > 0


def test_brightness_varies_across_bar():
    effect = Breathe()
    values = []
    for phase in np.linspace(0.0, 0.99, 10):
        result = effect.render(_ctx(bar_phase=phase), 1)
        values.append(result.max())
    assert max(values) > min(values), "Brightness should vary across bar"


def test_energy_adaptation_faster_at_high_bpm():
    effect = Breathe(beats_per_cycle=4.0)
    # At low BPM (80), cycle should be slower — check full bar for brightness range
    low_bpm_values = [effect.render(_ctx(bar_phase=p, bpm=80.0), 1).max() for p in np.linspace(0, 0.99, 20)]
    high_bpm_values = [effect.render(_ctx(bar_phase=p, bpm=160.0), 1).max() for p in np.linspace(0, 0.99, 20)]
    # High BPM should complete more cycles per bar — more variance in smaller range
    low_zero_crossings = sum(1 for i in range(1, len(low_bpm_values)) if (low_bpm_values[i] > 128) != (low_bpm_values[i-1] > 128))
    high_zero_crossings = sum(1 for i in range(1, len(high_bpm_values)) if (high_bpm_values[i] > 128) != (high_bpm_values[i-1] > 128))
    assert high_zero_crossings >= low_zero_crossings


def test_parameters_schema():
    schema = Breathe.parameters()
    assert "palette" in schema
    assert "beats_per_cycle" in schema
    assert "min_brightness" in schema


def test_get_set_params():
    effect = Breathe(beats_per_cycle=2.0)
    assert effect.get_params()["beats_per_cycle"] == 2.0
    effect.set_params(beats_per_cycle=3.0)
    assert effect.get_params()["beats_per_cycle"] == 3.0


def test_single_led():
    effect = Breathe()
    result = effect.render(_ctx(), 1)
    assert result.shape == (1, 3)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/effects/test_breathe.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement Breathe**

Create `src/dj_ledfx/effects/breathe.py`:

```python
from __future__ import annotations

import math
from typing import Any

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.base import Effect
from dj_ledfx.effects.color import hex_to_rgb
from dj_ledfx.effects.easing import lerp
from dj_ledfx.effects.energy import bpm_energy
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.types import BeatContext

_DEFAULT_PALETTE = ["#ffbf47", "#ff8c00", "#ffd700", "#ffaa33"]


class Breathe(Effect):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "palette": EffectParam(type="color_list", default=list(_DEFAULT_PALETTE), label="Palette"),
            "beats_per_cycle": EffectParam(
                type="float", default=4.0, min=1.0, max=4.0, step=0.5, label="Beats per Cycle"
            ),
            "min_brightness": EffectParam(
                type="float", default=0.05, min=0.0, max=0.5, step=0.01, label="Min Brightness"
            ),
        }

    def __init__(
        self,
        palette: list[str] | None = None,
        beats_per_cycle: float = 4.0,
        min_brightness: float = 0.05,
    ) -> None:
        colors = palette or list(_DEFAULT_PALETTE)
        self._palette = [hex_to_rgb(c) for c in colors]
        self._beats_per_cycle = beats_per_cycle
        self._min_brightness = min_brightness

    def get_params(self) -> dict[str, Any]:
        return {
            "palette": [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in self._palette],
            "beats_per_cycle": self._beats_per_cycle,
            "min_brightness": self._min_brightness,
        }

    def _apply_params(self, **kwargs: Any) -> None:
        if "palette" in kwargs:
            self._palette = [hex_to_rgb(c) for c in kwargs["palette"]]
        if "beats_per_cycle" in kwargs:
            self._beats_per_cycle = float(kwargs["beats_per_cycle"])
        if "min_brightness" in kwargs:
            self._min_brightness = float(kwargs["min_brightness"])

    def render(self, ctx: BeatContext, led_count: int) -> NDArray[np.uint8]:
        energy = bpm_energy(ctx.bpm)
        effective_beats = lerp(self._beats_per_cycle, 1.0, energy)
        cycles_per_bar = 4.0 / effective_beats
        cycle_phase = (ctx.bar_phase * cycles_per_bar) % 1.0

        brightness = self._min_brightness + (1.0 - self._min_brightness) * (
            0.5 + 0.5 * math.sin(cycle_phase * 2.0 * math.pi)
        )

        color_index = int(ctx.bar_phase * cycles_per_bar) % len(self._palette)
        r, g, b = self._palette[color_index]

        out = np.empty((led_count, 3), dtype=np.uint8)
        out[:, 0] = int(r * brightness)
        out[:, 1] = int(g * brightness)
        out[:, 2] = int(b * brightness)
        return out
```

- [ ] **Step 4: Register the effect**

In `src/dj_ledfx/effects/__init__.py`, add:

```python
from dj_ledfx.effects import breathe as _breathe  # noqa: F401
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/effects/test_breathe.py -v`
Expected: PASS

- [ ] **Step 6: Verify effect auto-registers**

Run: `uv run pytest tests/effects/test_registry.py::test_get_effect_classes_includes_beat_pulse -v`
Expected: PASS (and `breathe` now appears in registry too — can verify with a quick grep or by running the full registry test)

- [ ] **Step 7: Commit**

```bash
git add src/dj_ledfx/effects/breathe.py src/dj_ledfx/effects/__init__.py tests/effects/test_breathe.py
git commit -m "feat: add Breathe effect — smooth sinusoidal intensity swell"
```

---

### Task 7: Strobe effect

**Files:**
- Create: `src/dj_ledfx/effects/strobe.py`
- Create: `tests/effects/test_strobe.py`
- Modify: `src/dj_ledfx/effects/__init__.py`

- [ ] **Step 1: Write the tests**

Create `tests/effects/test_strobe.py`:

```python
import numpy as np
import pytest

from dj_ledfx.effects.strobe import Strobe
from dj_ledfx.types import BeatContext


def _ctx(beat_phase: float = 0.0, bar_phase: float = 0.0, bpm: float = 128.0) -> BeatContext:
    return BeatContext(beat_phase=beat_phase, bar_phase=bar_phase, bpm=bpm, dt=0.016)


def test_output_shape_and_dtype():
    effect = Strobe()
    result = effect.render(_ctx(), 10)
    assert result.shape == (10, 3)
    assert result.dtype == np.uint8


def test_on_at_beat_start():
    effect = Strobe(duty_cycle=0.15)
    result = effect.render(_ctx(beat_phase=0.0), 1)
    assert result.max() > 0, "Should be ON at beat start"


def test_off_after_duty_cycle():
    effect = Strobe(duty_cycle=0.15)
    result = effect.render(_ctx(beat_phase=0.5), 1)
    assert result.max() == 0, "Should be OFF well past duty cycle"


def test_duty_cycle_boundary():
    effect = Strobe(duty_cycle=0.5)
    on = effect.render(_ctx(beat_phase=0.1), 1)
    off = effect.render(_ctx(beat_phase=0.6), 1)
    assert on.max() > 0
    assert off.max() == 0


def test_subdivision_at_high_bpm():
    effect = Strobe(duty_cycle=0.15, max_subdivision=4)
    # At high BPM (160+), subdivision should be 4 (16th notes)
    # beat_phase=0.5 should be ON again (2nd subdivision of 4)
    result = effect.render(_ctx(beat_phase=0.5, bpm=160.0), 1)
    # At subdivision=4, phase 0.5 maps to sub_phase = (0.5*4)%1 = 0.0 → ON
    assert result.max() > 0


def test_parameters_schema():
    schema = Strobe.parameters()
    assert "palette" in schema
    assert "duty_cycle" in schema
    assert "max_subdivision" in schema


def test_get_set_params():
    effect = Strobe(duty_cycle=0.3)
    assert effect.get_params()["duty_cycle"] == 0.3
    effect.set_params(duty_cycle=0.1)
    assert effect.get_params()["duty_cycle"] == 0.1


def test_uniform_across_leds():
    effect = Strobe()
    result = effect.render(_ctx(beat_phase=0.0), 5)
    # All LEDs should be the same color
    for i in range(1, 5):
        np.testing.assert_array_equal(result[0], result[i])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/effects/test_strobe.py -v`
Expected: FAIL

- [ ] **Step 3: Implement Strobe**

Create `src/dj_ledfx/effects/strobe.py`:

```python
from __future__ import annotations

import math
from typing import Any

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.base import Effect
from dj_ledfx.effects.color import hex_to_rgb
from dj_ledfx.effects.easing import lerp
from dj_ledfx.effects.energy import bpm_energy
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.types import BeatContext

_DEFAULT_PALETTE = ["#ffffff"]


class Strobe(Effect):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "palette": EffectParam(type="color_list", default=list(_DEFAULT_PALETTE), label="Palette"),
            "duty_cycle": EffectParam(
                type="float", default=0.15, min=0.05, max=0.5, step=0.01, label="Duty Cycle"
            ),
            "max_subdivision": EffectParam(
                type="int", default=4, min=1, max=4, step=1, label="Max Subdivision"
            ),
        }

    def __init__(
        self,
        palette: list[str] | None = None,
        duty_cycle: float = 0.15,
        max_subdivision: int = 4,
    ) -> None:
        colors = palette or list(_DEFAULT_PALETTE)
        self._palette = [hex_to_rgb(c) for c in colors]
        self._duty_cycle = duty_cycle
        self._max_subdivision = max_subdivision

    def get_params(self) -> dict[str, Any]:
        return {
            "palette": [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in self._palette],
            "duty_cycle": self._duty_cycle,
            "max_subdivision": self._max_subdivision,
        }

    def _apply_params(self, **kwargs: Any) -> None:
        if "palette" in kwargs:
            self._palette = [hex_to_rgb(c) for c in kwargs["palette"]]
        if "duty_cycle" in kwargs:
            self._duty_cycle = float(kwargs["duty_cycle"])
        if "max_subdivision" in kwargs:
            self._max_subdivision = int(kwargs["max_subdivision"])

    def render(self, ctx: BeatContext, led_count: int) -> NDArray[np.uint8]:
        energy = bpm_energy(ctx.bpm)
        raw_sub = lerp(1.0, float(self._max_subdivision), energy)
        subdivision = 2 ** round(math.log2(max(raw_sub, 1.0)))

        sub_phase = (ctx.beat_phase * subdivision) % 1.0
        on = sub_phase < self._duty_cycle

        out = np.zeros((led_count, 3), dtype=np.uint8)
        if on:
            beat_index = int(ctx.bar_phase * 4) % len(self._palette)
            r, g, b = self._palette[beat_index]
            out[:, 0] = r
            out[:, 1] = g
            out[:, 2] = b
        return out
```

- [ ] **Step 4: Register the effect**

In `src/dj_ledfx/effects/__init__.py`, add:

```python
from dj_ledfx.effects import strobe as _strobe  # noqa: F401
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/effects/test_strobe.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/effects/strobe.py src/dj_ledfx/effects/__init__.py tests/effects/test_strobe.py
git commit -m "feat: add Strobe effect — beat-synced flash with energy subdivision"
```

---

### Task 8: ColorChase effect

**Files:**
- Create: `src/dj_ledfx/effects/color_chase.py`
- Create: `tests/effects/test_color_chase.py`
- Modify: `src/dj_ledfx/effects/__init__.py`

- [ ] **Step 1: Write the tests**

Create `tests/effects/test_color_chase.py`:

```python
import numpy as np
import pytest

from dj_ledfx.effects.color_chase import ColorChase
from dj_ledfx.types import BeatContext


def _ctx(beat_phase: float = 0.0, bar_phase: float = 0.0, bpm: float = 128.0) -> BeatContext:
    return BeatContext(beat_phase=beat_phase, bar_phase=bar_phase, bpm=bpm, dt=0.016)


def test_output_shape_and_dtype():
    effect = ColorChase()
    result = effect.render(_ctx(), 20)
    assert result.shape == (20, 3)
    assert result.dtype == np.uint8


def test_spatial_gradient():
    effect = ColorChase()
    result = effect.render(_ctx(), 20)
    # Not all LEDs should be the same color (spatial variation)
    assert not np.all(result == result[0])


def test_single_led_degradation():
    effect = ColorChase()
    result = effect.render(_ctx(), 1)
    assert result.shape == (1, 3)
    assert result.max() > 0


def test_scrolls_with_beat_phase():
    effect = ColorChase()
    frame1 = effect.render(_ctx(beat_phase=0.0), 20)
    frame2 = effect.render(_ctx(beat_phase=0.5), 20)
    assert not np.array_equal(frame1, frame2), "Should scroll with beat phase"


def test_direction_reverse():
    effect_fwd = ColorChase(direction="forward")
    effect_rev = ColorChase(direction="reverse")
    fwd = effect_fwd.render(_ctx(beat_phase=0.25), 20)
    rev = effect_rev.render(_ctx(beat_phase=0.25), 20)
    assert not np.array_equal(fwd, rev)


def test_parameters_schema():
    schema = ColorChase.parameters()
    assert "palette" in schema
    assert "band_count" in schema
    assert "direction" in schema
    assert schema["direction"].type == "choice"


def test_get_set_params():
    effect = ColorChase(band_count=3.0)
    assert effect.get_params()["band_count"] == 3.0
    effect.set_params(band_count=5.0)
    assert effect.get_params()["band_count"] == 5.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/effects/test_color_chase.py -v`
Expected: FAIL

- [ ] **Step 3: Implement ColorChase**

Create `src/dj_ledfx/effects/color_chase.py`:

```python
from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.base import Effect
from dj_ledfx.effects.color import hex_to_rgb, palette_lerp
from dj_ledfx.effects.energy import bpm_energy
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.types import BeatContext

_DEFAULT_PALETTE = ["#ff0000", "#00ff00", "#0000ff", "#ffff00"]


class ColorChase(Effect):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "palette": EffectParam(type="color_list", default=list(_DEFAULT_PALETTE), label="Palette"),
            "band_count": EffectParam(
                type="float", default=2.0, min=1.0, max=8.0, step=0.5, label="Band Count"
            ),
            "direction": EffectParam(
                type="choice", default="forward", choices=["forward", "reverse"], label="Direction"
            ),
        }

    def __init__(
        self,
        palette: list[str] | None = None,
        band_count: float = 2.0,
        direction: str = "forward",
    ) -> None:
        colors = palette or list(_DEFAULT_PALETTE)
        self._palette = [hex_to_rgb(c) for c in colors]
        self._band_count = band_count
        self._direction = direction

    def get_params(self) -> dict[str, Any]:
        return {
            "palette": [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in self._palette],
            "band_count": self._band_count,
            "direction": self._direction,
        }

    def _apply_params(self, **kwargs: Any) -> None:
        if "palette" in kwargs:
            self._palette = [hex_to_rgb(c) for c in kwargs["palette"]]
        if "band_count" in kwargs:
            self._band_count = float(kwargs["band_count"])
        if "direction" in kwargs:
            self._direction = str(kwargs["direction"])

    def render(self, ctx: BeatContext, led_count: int) -> NDArray[np.uint8]:
        energy = bpm_energy(ctx.bpm)
        speed = 1.0 + energy * 2.0
        effective_bands = self._band_count + energy * 2.0

        positions = np.linspace(0.0, 1.0, led_count) + ctx.beat_phase * speed
        if self._direction == "reverse":
            positions = -positions

        normalized = (positions * effective_bands) % 1.0
        return palette_lerp(self._palette, normalized)
```

- [ ] **Step 4: Register the effect**

In `src/dj_ledfx/effects/__init__.py`, add:

```python
from dj_ledfx.effects import color_chase as _color_chase  # noqa: F401
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/effects/test_color_chase.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/effects/color_chase.py src/dj_ledfx/effects/__init__.py tests/effects/test_color_chase.py
git commit -m "feat: add ColorChase effect — moving color bands along strip"
```

---

### Task 9: RainbowWave effect

**Files:**
- Create: `src/dj_ledfx/effects/rainbow_wave.py`
- Create: `tests/effects/test_rainbow_wave.py`
- Modify: `src/dj_ledfx/effects/__init__.py`

- [ ] **Step 1: Write the tests**

Create `tests/effects/test_rainbow_wave.py`:

```python
import numpy as np
import pytest

from dj_ledfx.effects.rainbow_wave import RainbowWave
from dj_ledfx.types import BeatContext


def _ctx(beat_phase: float = 0.0, bar_phase: float = 0.0, bpm: float = 128.0) -> BeatContext:
    return BeatContext(beat_phase=beat_phase, bar_phase=bar_phase, bpm=bpm, dt=0.016)


def test_output_shape_and_dtype():
    effect = RainbowWave()
    result = effect.render(_ctx(), 20)
    assert result.shape == (20, 3)
    assert result.dtype == np.uint8


def test_spatial_hue_distribution():
    effect = RainbowWave(wave_count=1.0, beat_pulse=0.0)
    result = effect.render(_ctx(bar_phase=0.0), 60)
    # Should have a variety of colors across the strip
    unique_rows = np.unique(result, axis=0)
    assert len(unique_rows) > 5, "Rainbow should produce many distinct colors"


def test_beat_pulse_modulation():
    effect = RainbowWave(beat_pulse=1.0)
    on_beat = effect.render(_ctx(beat_phase=0.0), 10)
    mid_beat = effect.render(_ctx(beat_phase=0.5), 10)
    # On beat is brightest (value=1.0); brightness drops as beat progresses
    assert on_beat.mean() >= mid_beat.mean()


def test_no_beat_pulse():
    effect = RainbowWave(beat_pulse=0.0)
    on_beat = effect.render(_ctx(beat_phase=0.0), 10)
    mid_beat = effect.render(_ctx(beat_phase=0.5), 10)
    # With no beat pulse, brightness should be the same
    np.testing.assert_array_equal(on_beat, mid_beat)


def test_rotates_with_bar_phase():
    effect = RainbowWave(beat_pulse=0.0)
    frame1 = effect.render(_ctx(bar_phase=0.0), 20)
    frame2 = effect.render(_ctx(bar_phase=0.5), 20)
    assert not np.array_equal(frame1, frame2)


def test_parameters_schema():
    schema = RainbowWave.parameters()
    assert "saturation" in schema
    assert "wave_count" in schema
    assert "beat_pulse" in schema


def test_single_led():
    effect = RainbowWave()
    result = effect.render(_ctx(), 1)
    assert result.shape == (1, 3)
    assert result.max() > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/effects/test_rainbow_wave.py -v`
Expected: FAIL

- [ ] **Step 3: Implement RainbowWave**

Create `src/dj_ledfx/effects/rainbow_wave.py`:

```python
from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.base import Effect
from dj_ledfx.effects.color import hsv_to_rgb_array
from dj_ledfx.effects.easing import ease_in
from dj_ledfx.effects.energy import bpm_energy
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.types import BeatContext


class RainbowWave(Effect):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "saturation": EffectParam(
                type="float", default=1.0, min=0.5, max=1.0, step=0.05, label="Saturation"
            ),
            "wave_count": EffectParam(
                type="float", default=1.0, min=0.5, max=4.0, step=0.5, label="Wave Count"
            ),
            "beat_pulse": EffectParam(
                type="float", default=0.3, min=0.0, max=1.0, step=0.05, label="Beat Pulse"
            ),
        }

    def __init__(
        self,
        saturation: float = 1.0,
        wave_count: float = 1.0,
        beat_pulse: float = 0.3,
    ) -> None:
        self._saturation = saturation
        self._wave_count = wave_count
        self._beat_pulse = beat_pulse

    def get_params(self) -> dict[str, Any]:
        return {
            "saturation": self._saturation,
            "wave_count": self._wave_count,
            "beat_pulse": self._beat_pulse,
        }

    def _apply_params(self, **kwargs: Any) -> None:
        if "saturation" in kwargs:
            self._saturation = float(kwargs["saturation"])
        if "wave_count" in kwargs:
            self._wave_count = float(kwargs["wave_count"])
        if "beat_pulse" in kwargs:
            self._beat_pulse = float(kwargs["beat_pulse"])

    def render(self, ctx: BeatContext, led_count: int) -> NDArray[np.uint8]:
        energy = bpm_energy(ctx.bpm)
        speed = 1.0 + energy
        hues = (np.linspace(0.0, self._wave_count, led_count) + ctx.bar_phase * speed) % 1.0
        value = 1.0 - self._beat_pulse * ease_in(ctx.beat_phase, 2.0)
        return hsv_to_rgb_array(hues, self._saturation, value)
```

- [ ] **Step 4: Register the effect**

In `src/dj_ledfx/effects/__init__.py`, add:

```python
from dj_ledfx.effects import rainbow_wave as _rainbow_wave  # noqa: F401
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/effects/test_rainbow_wave.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/effects/rainbow_wave.py src/dj_ledfx/effects/__init__.py tests/effects/test_rainbow_wave.py
git commit -m "feat: add RainbowWave effect — flowing hue rotation with beat pulse"
```

---

### Task 10: FireStorm effect

**Files:**
- Create: `src/dj_ledfx/effects/fire_storm.py`
- Create: `tests/effects/test_fire_storm.py`
- Modify: `src/dj_ledfx/effects/__init__.py`

- [ ] **Step 1: Write the tests**

Create `tests/effects/test_fire_storm.py`:

```python
import numpy as np
import pytest

from dj_ledfx.effects.fire_storm import FireStorm
from dj_ledfx.types import BeatContext


def _ctx(beat_phase: float = 0.0, bar_phase: float = 0.0, bpm: float = 128.0) -> BeatContext:
    return BeatContext(beat_phase=beat_phase, bar_phase=bar_phase, bpm=bpm, dt=0.016)


def test_output_shape_and_dtype():
    effect = FireStorm()
    result = effect.render(_ctx(), 20)
    assert result.shape == (20, 3)
    assert result.dtype == np.uint8


def test_per_led_variation():
    effect = FireStorm(smoothing=0.0)
    result = effect.render(_ctx(), 20)
    unique_rows = np.unique(result, axis=0)
    assert len(unique_rows) > 1, "Per-LED noise should produce variation"


def test_temporal_smoothing():
    effect = FireStorm(smoothing=0.9)
    frame1 = effect.render(_ctx(), 10)
    frame2 = effect.render(_ctx(), 10)
    # With high smoothing, frames should be similar (not identical due to noise)
    diff = np.abs(frame1.astype(int) - frame2.astype(int))
    assert diff.mean() < 100, "High smoothing should produce similar consecutive frames"


def test_no_smoothing_varies():
    effect = FireStorm(smoothing=0.0)
    frame1 = effect.render(_ctx(), 10)
    frame2 = effect.render(_ctx(), 10)
    assert not np.array_equal(frame1, frame2), "No smoothing should produce different frames"


def test_statefulness_across_renders():
    effect = FireStorm(smoothing=0.5)
    # First render initializes state
    effect.render(_ctx(), 10)
    # Second render should use previous state
    result = effect.render(_ctx(), 10)
    assert result.shape == (10, 3)


def test_led_count_change_resets_state():
    effect = FireStorm(smoothing=0.5)
    effect.render(_ctx(), 10)
    # Changing led_count should work without error
    result = effect.render(_ctx(), 20)
    assert result.shape == (20, 3)


def test_parameters_schema():
    schema = FireStorm.parameters()
    assert "palette" in schema
    assert "intensity" in schema
    assert "smoothing" in schema


def test_get_set_params():
    effect = FireStorm(intensity=0.5)
    assert effect.get_params()["intensity"] == 0.5
    effect.set_params(intensity=0.8)
    assert effect.get_params()["intensity"] == 0.8


def test_single_led():
    effect = FireStorm()
    result = effect.render(_ctx(), 1)
    assert result.shape == (1, 3)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/effects/test_fire_storm.py -v`
Expected: FAIL

- [ ] **Step 3: Implement FireStorm**

Create `src/dj_ledfx/effects/fire_storm.py`:

```python
from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

from dj_ledfx.effects.base import Effect
from dj_ledfx.effects.color import hex_to_rgb, palette_lerp
from dj_ledfx.effects.energy import bpm_energy
from dj_ledfx.effects.params import EffectParam
from dj_ledfx.types import BeatContext

_DEFAULT_PALETTE = ["#ff1500", "#ff6600", "#ff9900", "#ffcc00"]


class FireStorm(Effect):
    @classmethod
    def parameters(cls) -> dict[str, EffectParam]:
        return {
            "palette": EffectParam(type="color_list", default=list(_DEFAULT_PALETTE), label="Palette"),
            "intensity": EffectParam(
                type="float", default=0.7, min=0.3, max=1.0, step=0.05, label="Intensity"
            ),
            "smoothing": EffectParam(
                type="float", default=0.3, min=0.0, max=0.9, step=0.05, label="Smoothing"
            ),
        }

    def __init__(
        self,
        palette: list[str] | None = None,
        intensity: float = 0.7,
        smoothing: float = 0.3,
    ) -> None:
        colors = palette or list(_DEFAULT_PALETTE)
        self._palette = [hex_to_rgb(c) for c in colors]
        self._intensity = intensity
        self._smoothing = smoothing
        self._rng = np.random.default_rng()
        self._prev_frame: NDArray[np.float64] | None = None

    def get_params(self) -> dict[str, Any]:
        return {
            "palette": [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in self._palette],
            "intensity": self._intensity,
            "smoothing": self._smoothing,
        }

    def _apply_params(self, **kwargs: Any) -> None:
        if "palette" in kwargs:
            self._palette = [hex_to_rgb(c) for c in kwargs["palette"]]
        if "intensity" in kwargs:
            self._intensity = float(kwargs["intensity"])
        if "smoothing" in kwargs:
            self._smoothing = float(kwargs["smoothing"])

    def render(self, ctx: BeatContext, led_count: int) -> NDArray[np.uint8]:
        energy = bpm_energy(ctx.bpm)
        effective_intensity = self._intensity * (0.5 + 0.5 * energy)

        noise = self._rng.random(led_count)

        # Apply temporal smoothing
        if self._prev_frame is not None and len(self._prev_frame) == led_count:
            smoothed = self._prev_frame * self._smoothing + noise * (1.0 - self._smoothing)
        else:
            smoothed = noise

        self._prev_frame = smoothed.copy()

        # palette_lerp for color, brightness for flicker
        brightness = (1.0 - effective_intensity) + smoothed * effective_intensity
        colors = palette_lerp(self._palette, smoothed)
        result = (colors.astype(np.float64) * brightness[:, np.newaxis]).astype(np.uint8)
        return result
```

- [ ] **Step 4: Register the effect**

In `src/dj_ledfx/effects/__init__.py`, add:

```python
from dj_ledfx.effects import fire_storm as _fire_storm  # noqa: F401
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/effects/test_fire_storm.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/dj_ledfx/effects/fire_storm.py src/dj_ledfx/effects/__init__.py tests/effects/test_fire_storm.py
git commit -m "feat: add FireStorm effect — organic chaotic flickering with temporal smoothing"
```

---

### Task 11: Full test suite + lint + type check

**Files:** All modified/created files

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest -x -v`
Expected: All tests pass

- [ ] **Step 2: Run linter**

Run: `uv run ruff check .`
Expected: No errors (fix any that appear)

- [ ] **Step 3: Run formatter**

Run: `uv run ruff format .`

- [ ] **Step 4: Run type checker**

Run: `uv run mypy src/`
Expected: No errors (fix any that appear)

- [ ] **Step 5: Commit any fixes**

```bash
git add -u
git commit -m "fix: lint, format, and type check fixes"
```

---

### Task 12: Code architect review

Use the `superpowers:code-reviewer` agent to review all changes since the spec commit against the design spec.

- [ ] **Step 1: Run code architect review**

Dispatch a code review agent comparing the implementation against `docs/superpowers/specs/2026-03-23-effect-library-expansion-design.md`.

- [ ] **Step 2: Fix any issues found**

Address each issue from the review.

- [ ] **Step 3: Commit fixes**

```bash
git add -u
git commit -m "fix: address code architect review feedback"
```

---

### Task 13: Simplify review

- [ ] **Step 1: Run /simplify**

Use the `simplify` skill to review all changed code for reuse, quality, and efficiency issues.

- [ ] **Step 2: Fix any issues found**

Address each issue from the simplify review.

- [ ] **Step 3: Commit fixes**

```bash
git add -u
git commit -m "refactor: simplify review fixes"
```

---

### Task 14: Update CLAUDE.md and memory

- [ ] **Step 1: Run claude-md-management:revise-claude-md**

Update CLAUDE.md with any new patterns, conventions, or gotchas from this implementation.

- [ ] **Step 2: Update memory**

Update `mvp_status.md` to reflect the new effect count and any other changes.

---

### Task 15: Create PR

- [ ] **Step 1: Create feature branch and PR**

```bash
git checkout -b feature/effect-library-expansion
git push -u origin feature/effect-library-expansion
gh pr create --title "feat: expand effect library with 5 new effects + utilities" --body "..."
```
