# Effect Library Expansion Design

## Summary

Expand the effect library from 1 effect (BeatPulse) to 6, with shared utilities and automatic energy adaptation. Effects target House/Techno steady grooves and EDM/Festival drops. All effects degrade gracefully from addressable LED strips to single-color bulbs.

## Approach

Thin Foundation + Parallel Effects: build a minimal utility layer (color math, easing, energy inference), then build 5 new effects on top. Utilities are shaped by real needs, not speculation.

## Foundation Changes

### BeatContext Dataclass

Replace the 4 individual render parameters with a `BeatContext` dataclass. Added to `types.py`:

```python
@dataclass(frozen=True, slots=True)
class BeatContext:
    beat_phase: float   # 0.0-1.0 within current beat
    bar_phase: float    # 0.0-1.0 within current 4-beat bar
    bpm: float          # current pitch-adjusted BPM
    dt: float           # frame delta (seconds)
```

**Relationship to BeatState:** `BeatState` already exists in `types.py` with `beat_phase`, `bar_phase`, and `bpm`. `BeatContext` is an intentionally minimal subset — it strips fields that effects should not depend on (`is_playing`, `next_beat_time`, `pitch_percent`, `deck_number`, `deck_name`) and adds `dt` (a rendering parameter). This keeps the effect API narrow and prevents effects from coupling to transport or deck state. The engine constructs `BeatContext` from `BeatState` + frame period.

### Render Signature Change

`Effect.render()` changes from:

```python
def render(self, beat_phase: float, bar_phase: float, dt: float, led_count: int) -> NDArray[np.uint8]
```

to:

```python
def render(self, ctx: BeatContext, led_count: int) -> NDArray[np.uint8]
```

Breaking change — requires updating:
- `Effect` ABC in `effects/base.py`
- `EffectDeck.render()` in `effects/deck.py`
- `EffectEngine.tick()` in `effects/engine.py` (constructs `BeatContext` from `BeatState` + frame period)
- `BeatPulse` in `effects/beat_pulse.py`
- Test effects in `tests/effects/test_registry.py` (helper effect classes define `render()`)
- Direct `deck.render()` calls in `tests/effects/test_deck.py`
- All other tests that call `render()` or mock it (grep for `\.render(` across `tests/`)

`led_count` remains a separate parameter — it's a rendering constraint, not musical state.

### Shared Utilities

Three modules under `effects/`:

#### `effects/color.py` — Color Math

- `hex_to_rgb(hex: str) -> tuple[int, int, int]` — extracted from BeatPulse
- `rgb_to_hex(r: int, g: int, b: int) -> str`
- `hsv_to_rgb_array(h: NDArray, s: float | NDArray, v: float | NDArray) -> NDArray[np.uint8]` — vectorized HSV to RGB, output size inferred from `h.shape[0]`
- `palette_lerp(palette: list[tuple[int,int,int]], positions: NDArray[np.float64]) -> NDArray[np.uint8]` — smooth interpolation between palette colors at arbitrary 0-1 positions. Core of any gradient/wave/chase effect.

#### `effects/easing.py` — Easing Functions

All operate on `float` or `NDArray`:

- `lerp(a, b, t)` — linear interpolation `a + (b - a) * t`
- `ease_in(t, power=2.0)` — `t^power` (generalizes gamma)
- `ease_out(t, power=2.0)` — `1 - (1-t)^power`
- `ease_in_out(t)` — smooth hermite `3t^2 - 2t^3`
- `sine_ease(t)` — `sin(t * pi/2)` for natural breathing curves

#### `effects/energy.py` — BPM Energy Inference

- `bpm_energy(bpm: float, low: float = 100.0, high: float = 150.0) -> float` — maps BPM to 0.0-1.0 energy level, clamped. Below `low` returns 0, above `high` returns 1, linear in between.

All utilities are pure functions, stateless, numpy-vectorized where applicable.

## Effects

### 1. Breathe

Smooth sinusoidal intensity swell. The "chill groove" effect.

**Behavior:** Fades up and down using `sine_ease` over a configurable beat span. Color advances to next palette color each cycle.

**Energy adaptation:** Cycle length shrinks from `beats_per_cycle` (default 4) toward 1 as energy increases.

**Parameters:**
| Name | Type | Default | Range | Description |
|------|------|---------|-------|-------------|
| `palette` | color_list | warm amber/gold (hex strings) | — | Color palette |
| `beats_per_cycle` | float | 4.0 | 1.0–4.0 | Base cycle length before energy scaling (clamped to one bar max — cross-bar cycles would require statefulness) |
| `min_brightness` | float | 0.05 | 0.0–0.5 | Floor brightness (never fully black) |

**Render logic:**
```
energy = bpm_energy(ctx.bpm)
effective_beats = lerp(1, beats_per_cycle, 1 - energy)
# bar_phase * 4 gives beat position 0-4 within bar
cycles_per_bar = 4.0 / effective_beats
cycle_phase = (ctx.bar_phase * cycles_per_bar) % 1.0
# Full sine wave: 0→1→0 over one cycle
brightness = min_brightness + (1 - min_brightness) * (0.5 + 0.5 * sin(cycle_phase * 2 * pi))
# Advance palette color each cycle within the bar
color_index = int(ctx.bar_phase * cycles_per_bar) % len(palette)
color = palette[color_index]
output = color * brightness
```

**Single-color degradation:** Works identically — uniform intensity fade.

### 2. Strobe

Sharp beat-locked flash. The "drop" effect.

**Behavior:** Full-brightness flash for a short duty cycle on each beat subdivision, black otherwise.

**Energy adaptation:** Subdivision increases — quarter notes at low energy, 8th notes mid, 16th notes at high energy.

**Parameters:**
| Name | Type | Default | Range | Description |
|------|------|---------|-------|-------------|
| `palette` | color_list | white | — | Flash colors |
| `duty_cycle` | float | 0.15 | 0.05–0.5 | Fraction of subdivision that's lit |
| `max_subdivision` | int | 4 | 1, 2, 4 | Energy ceiling for subdivision density |

**Render logic:**
```
energy = bpm_energy(ctx.bpm)
# Snap to nearest power of 2: for max_subdivision=4, gives 1, 2, or 4
subdivision = 2 ** round(log2(lerp(1, max_subdivision, energy)))
sub_phase = (ctx.beat_phase * subdivision) % 1.0
on = sub_phase < duty_cycle
# Derive beat index from bar_phase (0-3 across the 4-beat bar)
beat_index = int(ctx.bar_phase * 4) % len(palette)
color = palette[beat_index]
output = color if on else black
```

**Single-color degradation:** Works identically — full flash on/off.

### 3. ColorChase

Moving color bands traveling along the strip. The "groove" effect.

**Behavior:** Palette colors form repeating bands across the LED strip, scrolling with beat phase. On single-color devices, degrades to palette cycling per beat.

**Energy adaptation:** Band count increases and scroll speed multiplies with energy.

**Parameters:**
| Name | Type | Default | Range | Description |
|------|------|---------|-------|-------------|
| `palette` | color_list | RGB+yellow | — | Band colors |
| `band_count` | float | 2.0 | 1.0–8.0 | Base palette repetitions across strip |
| `direction` | choice | "forward" | forward/reverse | Scroll direction |

**Render logic:**
```
energy = bpm_energy(ctx.bpm)
speed = 1.0 + energy * 2.0
effective_bands = band_count + energy * 2.0
positions = np.linspace(0, 1, led_count) + beat_phase * speed
if direction == "reverse": positions = -positions
output = palette_lerp(palette, (positions * effective_bands) % 1.0)
```

**Single-color degradation:** When `led_count == 1`, cycles through palette colors per beat.

### 4. RainbowWave

Smooth hue rotation flowing across the strip. Universal crowd-pleaser.

**Behavior:** Full HSV rainbow mapped across the strip, rotating over time. Bar phase drives rotation so it completes one full cycle per bar.

**Energy adaptation:** Rotation speed increases, brightness pulses on beat at high energy.

**Parameters:**
| Name | Type | Default | Range | Description |
|------|------|---------|-------|-------------|
| `saturation` | float | 1.0 | 0.5–1.0 | Color saturation |
| `wave_count` | float | 1.0 | 0.5–4.0 | Rainbow cycles across strip |
| `beat_pulse` | float | 0.3 | 0.0–1.0 | Beat-synced brightness modulation depth |

**Render logic:**
```
energy = bpm_energy(ctx.bpm)
speed = 1.0 + energy
hues = (np.linspace(0, wave_count, led_count) + bar_phase * speed) % 1.0
value = 1.0 - beat_pulse * ease_in(beat_phase, 2)
output = hsv_to_rgb_array(hues, saturation, value)
```

**Single-color degradation:** When `led_count == 1`, single hue rotates over time.

### 5. FireStorm

Organic chaotic flickering. The "peak energy" effect.

**Behavior:** Per-LED random brightness modulation with warm color base. Uses numpy RNG seeded from beat state for reproducible-but-organic noise. Temporal smoothing carries forward previous frame.

**Energy adaptation:** Low energy = gentle candle flicker (small variance). High energy = aggressive full-range chaos.

**Parameters:**
| Name | Type | Default | Range | Description |
|------|------|---------|-------|-------------|
| `palette` | color_list | fire (red/orange/yellow) | — | Base colors |
| `intensity` | float | 0.7 | 0.3–1.0 | Flicker variance |
| `smoothing` | float | 0.3 | 0.0–0.9 | Temporal smoothing (0=random, 0.9=slow drift) |

**Render logic:**
```
energy = bpm_energy(ctx.bpm)
effective_intensity = intensity * (0.5 + 0.5 * energy)
# noise ranges 0.0-1.0, used as both brightness and palette position
noise = rng.random(led_count)
smoothed = prev_frame * smoothing + noise * (1 - smoothing)
prev_frame = smoothed  # carry state (values stay in 0.0-1.0)
# palette_lerp selects color, multiply by brightness for flicker
brightness = (1.0 - effective_intensity) + smoothed * effective_intensity
output = palette_lerp(palette, smoothed) * brightness[:, np.newaxis]
```

**Thread safety:** FireStorm's `prev_frame` state is safe because effect render methods run synchronously on the single asyncio event loop (per CLAUDE.md).

**Single-color degradation:** Works identically with `led_count == 1` — single flickering light.

**Statefulness:** FireStorm is the only stateful effect — stores `prev_frame` array for temporal smoothing. All other effects are pure functions of beat state.

## Migration & Integration

### Effect Registration
- Each new effect lives in its own file under `effects/` (e.g., `effects/breathe.py`)
- Import added to `effects/__init__.py` to trigger auto-registry via `__init_subclass__`
- No other wiring needed — `get_effect_classes()`, `get_effect_schemas()`, and `create_effect()` pick them up automatically

### Web UI
- Effect dropdown reads from `get_effect_schemas()` — new effects appear automatically
- All param types used (`float`, `color_list`, `choice`, `int`) are already defined in `EffectParam`
- No frontend code changes required

### No Changes Needed
- Scheduling, devices, spatial compositor, persistence, transport — effects are fully decoupled from these systems

## Existing Effect
- **BeatPulse** stays as-is (migrated to `BeatContext` signature but behavior unchanged)

## Testing Strategy
- Unit tests for each utility function (color, easing, energy)
- Unit tests for each effect: verify output shape, dtype, value ranges, energy adaptation behavior
- BeatPulse regression test: verify identical output after `BeatContext` migration
- Integration: existing pipeline tests continue to work after signature migration
