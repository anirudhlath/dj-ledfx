# dj-ledfx vs LedFx — Feature Comparison Report

> Generated: 2026-03-23
> Purpose: Track feature parity and gaps between dj-ledfx and the open-source LedFx project.
> Goal: dj-ledfx will support both CDJ beat-sync (solved problem) AND direct audio processing (like LedFx), combining the best of both approaches.

---

## Fundamental Architecture Difference

| | **LedFx** | **dj-ledfx** |
|---|---|---|
| **Input** | Microphone/loopback audio (sounddevice + aubio) | Pro DJ Link network packets (CDJ beat data) |
| **Philosophy** | Audio-reactive -- effects respond to what they *hear* | Beat-deterministic -- effects sync to what the DJ *plays* |
| **Concurrency** | Threading (`threading.Lock` everywhere) | Single asyncio event loop |
| **Web framework** | aiohttp | FastAPI |
| **Config** | JSON + voluptuous schema validation | TOML + dataclasses + SQLite runtime |
| **Frontend** | React + Material-UI | React 19 + shadcn/ui + Tailwind v4 |

These are fundamentally different products solving different problems today. LedFx is a general audio visualizer; dj-ledfx is a DJ-specific beat-sync engine. The goal is to merge both capabilities -- CDJ-accurate beat sync PLUS audio-reactive frequency analysis.

---

## 1. Beat/Audio Engine

### LedFx: More Feature-Rich (but less accurate)

| Feature | LedFx | dj-ledfx |
|---|---|---|
| **Beat detection** | aubio onset/tempo + custom volume threshold | Deterministic from CDJ packets |
| **Beat accuracy** | Estimated (~10-50ms jitter typical for audio onset) | Sample-accurate from hardware (<1ms) |
| **BPM tracking** | aubio tempo tracker | Direct from CDJ (pitch-adjusted: `bpm * (1 + pitch/100)`) |
| **Bar tracking** | `bar_oscillator()` -- estimated 0-4 range | Exact `beat_number` 1-4 from CDJ, bar_phase interpolated |
| **Frequency analysis** | Full mel-scale filterbanks (9 filter types), FFT 4096 samples, 3-band split | None |
| **Pitch detection** | aubio yinfft/yin/schmitt | Not applicable |
| **Onset strength** | Multiple algorithms (energy, HFC, phase) | Not applicable |
| **Drift correction** | N/A (continuous audio stream) | Soft (<5ms: 10% adjust) / Hard (>=5ms: snap) |

### LedFx Audio Pipeline Details

1. **Audio capture**: sounddevice (PortAudio wrapper), WASAPI loopback on Windows, manual routing (BlackHole/PulseAudio) on macOS/Linux
2. **Pre-processing**: Pre-emphasis filtering, volume normalization with exponential smoothing, optional resampling to 30kHz
3. **FFT**: 4096-sample FFT, max 15kHz Nyquist
4. **Mel filterbanks** (`Melbanks`): Multiple parallel filterbanks at different frequency resolutions. 9 coefficient types: `matt_mel`, `triangle`, `bark`, `mel`, `htk`, `scott`, `scott_mel`, `fixed`, `fixed_simple`. Three default bands at [350, 2000, 15000] Hz boundaries.
5. **Smoothing**: `ExpFilter` with separate decay/rise coefficients, power factor transformation for peak isolation
6. **Beat/onset detection**: aubio library for onset detection (energy, HFC, phase), tempo tracking, pitch detection. Custom `volume_beat_now()` for amplitude-based beats.

### Gap Analysis

- dj-ledfx has no frequency analysis at all -- effects can only respond to beat phase/BPM/energy
- Adding audio input (even just mel-bank analysis) would unlock frequency-reactive effects (bass pulse, treble sparkle, spectrum visualizer, etc.)
- CDJ beat accuracy + frequency analysis would be the best of both worlds

---

## 2. Effect Engine

### LedFx: Significantly More Mature

| Feature | LedFx | dj-ledfx |
|---|---|---|
| **Effect count** | ~50+ effects | 6 effects |
| **Effect categories** | 1D audio, 2D matrix, gradient, temporal | 1D beat-synced only |
| **Base class hierarchy** | 4 levels: Effect -> AudioReactive -> Gradient -> Twod | 1 level: Effect ABC |
| **Render signature** | Two-phase: `audio_data_updated()` + `render()` | Single: `render(ctx: BeatContext, led_count)` |
| **Auto-registration** | `__init_subclass__` + RegistryLoader + watchdog hot-reload | `__init_subclass__` (same pattern) |
| **Post-processing** | Flip, mirror, blur (Gaussian), brightness, background blend | None |
| **Transitions** | 7 types (dissolve, push, slide, iris, through-white/black, add) | None |
| **2D support** | PIL-based matrix rendering (flame, smoke, plasma, rain, etc.) | None (1D strips only) |
| **Pixel grouping** | `effective_pixel_count` reduces compute for dense strips | None |
| **Fallback effects** | Auto-restore previous effect on timeout | None |
| **Effect hot-swap** | Yes | Yes (EffectDeck) |
| **Parameter system** | voluptuous schema + UI generation | EffectParam descriptor + introspection |
| **Preset system** | Built-in + user presets, preset matching | PresetStore with TOML/SQLite persistence |
| **Calibration patterns** | Test pattern generator for device setup | None |

### LedFx Effect Categories (~50+)

- **1D Audio Reactive**: scroll, wavelength, energy, magnitude, spectrum, bands, bar, multiBar, power, equalizer, fade, rain, rainbow, strobe, real_strobe, scan, scan_and_flare, scan_multi, scroll_plus, vumeter, blade_power_plus, bleep, block_reflections, blocks, crawler, lava_lamp, marching, melt, melt_and_sparkle, metro, modulate, pitchSpectrum, random_flash, singleColor, water
- **2D Matrix**: flame2d, smoke2d, noise2d, waterfall2d, digitalrain2d, equalizer2d, plasma2d, keybeat2d, soap2d, texter2d, game_of_life
- **Gradient-based**: gradient, plasmawled
- **Special**: clone, gifplayer, imagespin, filter, hierarchy, blender, concentric, radial, droplets

### dj-ledfx Effects (6)

1. **BeatPulse**: Brightness decay per beat (gamma curve), palette color cycling on bar_phase
2. **RainbowWave**: HSV rainbow cycling, energy-adaptive speed, beat pulse dimming
3. **ColorChase**: Moving color bands, energy-adaptive speed/count, bidirectional
4. **Strobe**: Beat-synced with energy-adaptive subdivision (powers of 2)
5. **Breathe**: Sine-wave brightness oscillation synced to beats
6. **FireStorm**: Noise-driven fire with temporal smoothing

### Gap Analysis

- Post-processing pipeline (blur, mirror, flip) -- cheap to add, large visual impact
- Transitions between effects -- critical for live performance
- 2D matrix support -- MatrixGeometry exists but no effects use it
- Pixel grouping for high-LED-count strips
- Need many more effects (LedFx has 50+, many can be adapted for beat-sync)

---

## 3. Latency/Timing -- dj-ledfx is Superior

| Feature | LedFx | dj-ledfx |
|---|---|---|
| **Latency compensation** | **None** | Future-frame ring buffer with per-device offsets |
| **Frame scheduling** | Render-and-send immediately per thread | LookaheadScheduler with FrameSlot depth-1 slots |
| **Per-device timing** | Configurable refresh rate per device only | Per-device send loops at natural FPS + latency strategy |
| **RTT measurement** | None | EMA/WindowedMean with outlier rejection |
| **Ring buffer** | None | 1s of future frames, `find_nearest(target_time)` |
| **Latency strategies** | None | Static, EMA (alpha=0.3, outlier rejection), WindowedMean |
| **Device-type heuristics** | LIFX capped at 20fps (anti-strobe) | Govee=100ms, LIFX=50ms, USB=5ms initial seeds |
| **Transport gating** | Always running | STOPPED/PLAYING/SIMULATING with state capture/restore |

### Why This Matters

LedFx renders a frame and immediately sends it to all devices. A LIFX bulb (50-450ms latency) and a USB strip (5ms latency) will be 45-445ms out of sync. There is no mechanism to correct this.

dj-ledfx renders 1 second into the future, stores frames in a ring buffer, and each device's send loop picks the frame matching `now + device_latency`. All devices hit the beat simultaneously regardless of their individual latency characteristics.

**This is a fundamental design advantage that LedFx cannot replicate without rewriting their render pipeline.**

---

## 4. Device Integration

### LedFx: Broader Protocol Support

| Protocol | LedFx | dj-ledfx |
|---|---|---|
| **WLED** (E1.31/DDP/UDP) | Yes (primary target) | No |
| **E1.31 (sACN)** | Yes | No |
| **ArtNet** | Yes | No |
| **DDP** | Yes | No |
| **OpenRGB** | Yes | Yes |
| **Govee** | Yes (Razer protocol) | Yes (reimplemented, solid + segment) |
| **LIFX** | Yes | Yes (full binary protocol: bulb/strip/tile) |
| **Philips Hue** | Yes | No |
| **Nanoleaf** | Yes | No |
| **Adalight** (serial) | Yes | No |
| **rpi_ws281x** | Yes | No |
| **Launchpad** (MIDI) | Yes | No |
| **Twinkly** | Yes | No |
| **OSC** | Yes | No |
| **Total** | ~17 protocols | 3 protocols + ghost |

### dj-ledfx: Better Device Management

| Management Feature | LedFx | dj-ledfx |
|---|---|---|
| **Discovery** | mDNS/Zeroconf (WLED only) | DiscoveryOrchestrator with multi-backend scanning |
| **Ghost/offline** | Basic offline handling | Full ghost promote/demote lifecycle |
| **State capture/restore** | No | Yes (per-device, on transport stop) |
| **Device identity** | Config-based | MAC-based `stable_id` for cross-session matching |
| **Fast reconnect** | No | `connect_known_devices()` skips scanning |
| **Geometry reporting** | No | Adapters report StripGeometry/MatrixGeometry |

### Gap Analysis

- **WLED/E1.31/DDP** is the biggest protocol gap -- WLED is by far the most popular LED controller in the community
- ArtNet and Adalight would cover most remaining use cases
- Hue/Nanoleaf are nice-to-haves

---

## 5. Virtual Devices / Spatial

| Feature | LedFx | dj-ledfx |
|---|---|---|
| **Virtual devices** | Yes -- mature span/copy/segment mapping | No virtual device abstraction |
| **Segment mapping** | `[device_id, start, end, invert]` per segment | Spatial compositor distributes globally |
| **Span vs Copy** | Span distributes effect; Copy replicates per segment | Linear/Radial mapping with global normalization |
| **3D scene model** | No | Yes (SceneModel with DevicePlacement, 3D coordinates) |
| **3D scene editor** | No | Yes (R3F/Three.js in browser) |
| **Mapping types** | 1D segment-based | LinearMapping (dot product) + RadialMapping (distance) |
| **Multi-scene** | Scenes = effect snapshots (restore config) | Concurrent scene activation with conflict detection |
| **Pixel optimization** | Precompiled numpy remap arrays (13x perf gain) | None noted |

### Gap Analysis

- LedFx's Virtual system is proven and practical -- span/copy modes with segment granularity
- dj-ledfx's 3D approach has higher ceiling but is less baked
- Consider supporting LedFx-style segment mapping as a simpler alternative alongside spatial mapping

---

## 6. Web UI / Configuration

| Feature | LedFx | dj-ledfx |
|---|---|---|
| **Config format** | JSON (single file) | TOML (import/export) + SQLite (runtime) |
| **Config migration** | Version-tracked with migration functions | SQLite file-based migrations |
| **Scenes** | Snapshot/restore of all virtual states | Multi-scene with concurrent activation |
| **PWA support** | Yes (service worker, manifest) | No |
| **SSL/HTTPS** | Optional | No |
| **API endpoints** | ~40 endpoint files | ~6 routers |
| **WS protocol** | Client types, event filters, audio streaming | Multiplexed channels (beat/stats/frames/transport) |
| **WS binary frames** | Base64-encoded, rate-limited | Raw RGB with 2-byte name + 4-byte seq header |

---

## Summary Scorecard

| Area | LedFx | dj-ledfx | Notes |
|---|---|---|---|
| **Audio analysis** | **Superior** | -- | Mel banks, FFT, frequency bands, pitch |
| **Beat accuracy** | -- | **Superior** | Hardware-deterministic vs audio-estimated |
| **Effect library** | **Superior** | -- | 50+ vs 6, plus 2D, transitions, post-processing |
| **Effect framework** | Comparable | Comparable | Both use `__init_subclass__`, similar patterns |
| **Latency compensation** | -- | **Superior** | Ring buffer + per-device strategies vs nothing |
| **Device protocols** | **Superior** | -- | 17 vs 3. WLED alone is a big gap |
| **Device management** | -- | **Superior** | Ghost lifecycle, state capture, stable IDs |
| **Spatial/3D** | -- | **Superior** | 3D scene model + editor vs 1D segments |
| **Virtual devices** | **Superior** | -- | Mature span/copy system |
| **Web architecture** | Comparable | Slightly better | FastAPI + SQLite vs aiohttp + JSON |
| **Maturity** | **Superior** | -- | Years of community development |

---

## Strategic Priorities (Suggested)

### High Impact, Closes Biggest Gaps
1. **Audio input pipeline** -- Add sounddevice + mel-bank analysis alongside CDJ input. Dual-source beat/frequency data. This is the stated project goal.
2. **Effect library expansion** -- Port/adapt LedFx-style effects for beat-sync + frequency-reactive. Target 20+ effects.
3. **Post-processing pipeline** -- Blur, mirror, flip, brightness. Cheap to add, big visual payoff.
4. **Effect transitions** -- At least dissolve/crossfade for live performance.
5. **WLED/E1.31/DDP support** -- Opens up the largest device ecosystem.

### Medium Impact
6. **2D matrix effects** -- MatrixGeometry already exists, needs effect support.
7. **Pixel grouping** -- Reduce compute for high-count strips.
8. **Virtual device abstraction** -- LedFx-style span/copy alongside spatial mapping.
9. **Fallback effects** -- Auto-restore on timeout.

### Nice-to-Have
10. **PWA support** -- Service worker, manifest for mobile use.
11. **Calibration patterns** -- Test patterns for device setup.
12. **Additional protocols** -- Hue, Nanoleaf, ArtNet, Adalight.
