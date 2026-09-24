# dj-ledfx dashboard: brief for Claude Design

Paste everything below the line into Claude Design and attach the floor-plan image, `floorplan.png`. It is kept out of git, in `.superpowers/brainstorm/1505004-1790196208/home-import/`.

---

Design the web app for **dj-ledfx** from a blank page. dj-ledfx is a self-hosted lighting engine that runs "looks" across every smart light in one apartment, 24/7, from a home server.

Effects are computed in 3D. Every LED has a real position in the home, so light moves through rooms the way it would through space: a sunset glows from the floor up, a shockwave expands from the TV, a wisp walks from room to room. It started as a DJ tool synced to Pioneer's Pro DJ Link; now DJing is just one input.

One person uses it: the owner, mostly at a desktop browser, and on a phone for quick changes from the sofa.

## What should make it special

This is an instrument for playing light through a real home, not a settings panel. Moments worth designing around:

- A sunset that starts at the bedroom's west windows and follows the real sun across the apartment.
- Tapping a tempo and watching every lamp land on the beat.
- The doorbell sending a golden ring from the front door through every room.
- Fireflies drifting through the living room, each lamp glowing only as one passes.

There is no existing design to match and no brand to follow. Explore a few genuinely different directions before settling on one.

## What the owner does, most important first

1. Put a look on a room, or the whole home, and walk away. It keeps running, even after restarts.
2. See at a glance what's running where, and every light's live colour.
3. Browse and preview looks, tweak one and save it as a new look.
4. Place lights in the 3D home and fix their positions.
5. Check on devices and inputs: health, latency, tempo, music, Home Assistant.

## The home (real data, please use it)

The attached floor plan is accurate; north is up. Use it for geometry only: its colours and styling are not a design direction. The apartment is about 14.8 × 14.5 m, C-shaped around an outdoor courtyard that opens to the west. The ceiling is 3.35 m, with beams down to 3.10 m. There is a balcony off the sunroom.

| Room | m² | Lights |
|---|---|---|
| Living room (south-east) | 30.2 | Right Corner Lamp, Left Corner Lamp, Rope, Ikea Lamp 1–3, Candle 1–3 (LIFX Candle), Right Lamp (LIFX Mini), TV Lamp (LIFX Tube). Anchors: TV, sofa, coffee table, speakers |
| Kitchen | 17.8 | Corner Lamp (Govee floor lamp), Floor Lamp (LIFX Mini). Sub-zone: the counter |
| Bedroom (north-west, three west windows) | 24.7 | Bed Left, Bed Right (LIFX bulbs) |
| Office: a desk zone along the bedroom's south wall | — | Desk Left, Desk Right (LIFX bulbs); PC (RAM sticks, keyboard, mouse, GPU, motherboard) |
| Corridor / Entrance | 11.0 | Neon Indoor (LIFX Neon strip) |
| Study, Sunroom, Bathroom, Wardrobe | 8.2, 6.1, 8.2, 9.4 | none |

That is 19 devices (the PC counts as one) and about 412 LEDs.

## Concepts

- **Look:** a named preset built from layers, plus modifiers and a transition.
  - Layer types: a *field* (a 3D pattern), *particles*, or *firmware* (a light's own built-in effect, such as LIFX Flame).
  - Layer modifiers: mask (a height band, a room, a sub-zone, or distance from an anchor), mirror, transform.
  - Look modifiers: trails, downbeat flash, brightness cap, evening (warmer and dimmer later in the day).
  - Transitions: cut, fade, wipe, spread, dissolve.
  - Categories: Ambient, Tempo, Audio, Home, Firmware. Each look says which inputs it needs.
- **Zone:** where a look runs. It can be a room, a sub-zone (the Office desk, the kitchen counter), the whole home, or a custom group of lights. A light is in at most one running zone; starting a look on an overlapping zone takes those lights over. Off stops the look and puts each light back how it was.
- **Anchor:** a named point in the home that looks use, such as the TV, the sofa, the speakers or the coffee table.
- **Inputs:**
  - A tempo clock that is always running: an internal BPM with tap tempo, taken over by Pro DJ Link when a DJ plays, or by the music's beat.
  - Music from Music Assistant: loudness, beat, spectrum.
  - Home Assistant: doorbell, bedtime, what's playing.
  - The sun's real position.
- **Bindings:** any setting can follow a signal (e.g. Aurora's speed follows loudness).
- **Preview-only:** everything renders on screen and nothing is sent to the lights.
- **Sharing:** a light switched off elsewhere drops out and rejoins when it is switched back on. The app never turns lights on by itself; only starting a look does.

## The 29 looks

**Ambient (no input)**

- Sunset: a slow gradient from warm at the floor to deep blue at the ceiling, with the Candles on LIFX Flame.
- Fireflies: fireflies wander the room; a lamp only glows while one drifts through it.
- Embers: the Candles and the Tube run LIFX Flame while embers rise from the floor and climb the other lamps.
- Rain storm: rain runs down the lamps, and lightning strikes a random spot, lighting each lamp by distance.
- Snow: snow drifts down and catches on the lamps as it passes.
- Aurora: aurora curtains drift near the ceiling; the Candles and the Tube run LIFX Morph in the same palette.
- Lava: a slow 3D plasma in lava colours that never quite repeats.
- Color carousel: each lamp's hue comes from its angle around the room, so a rainbow slowly circles you.
- Ripples: drops land on the floor and send rings outward; lamps shimmer as the rings pass.
- Focus: calm and warm near the sofa, busier and more colourful further away.
- Spotlights: two soft spotlights drift from lamp to lamp.

**Tempo (beat)**

- Beat bursts: every beat fires particles out of the TV, with a bigger burst on the downbeat.
- Shockwave + beam: a sphere of light expands from the TV every beat while a lighthouse beam turns once per bar.
- Vortex: particles spiral up around the room, kicked faster on each beat.
- Twin comets: two comets chase lamp to lamp, landing on each beat.
- Fountain: a fountain on the coffee table sprays particles, with a bigger burst on every beat.
- Flock: a flock swirls as one and scatters on every other downbeat.
- Bouncing ball: one ball ricochets around the room and lands exactly on every beat.
- Scanner: a horizontal plane sweeps floor to ceiling and back every two beats.
- 3D checker: 1 m cubes swap colours on each beat, like a disco floor in 3D.

**Audio (music)**

- Speaker waves: kicks send wavefronts out from the speakers, snares bloom between them, hi-hats sparkle up high.
- Room spectrum: height is frequency; bass lights the floor, treble the ceiling.
- Tide: a water line rises and falls with loudness, with foam at the surface.
- Drop moment: a calm verse, a build where a plane rises and the strobe doubles each bar, then a white flash and shockwaves on the drop.

**Home (whole apartment)**

- Home sunset: the sunset in every room, with a warm sun that follows the real one across the apartment.
- Wisp: two wisps roam room to room; each lamp glows only while one passes.
- Goodnight: a warm glow walks through the home switching rooms off behind it, and leaves the bedroom on a night light.
- Doorbell ripple: the doorbell sends a golden ring from the front door through every room, over whatever is running.

**Firmware**

- Firmware showcase: every light runs its own built-in effect (LIFX Flame, Morph, Move and waveforms; OpenRGB hardware modes). Lights without one, like the Govee lamp, get a streamed copy.

## What it needs to cover

These are areas of capability, not a sitemap or a layout. Organise, merge and navigate them however serves the owner best.

- **The home, live:** the whole home in 3D (rooms, walls, windows, the courtyard) with every light showing its live colour at up to 60 fps. What's running in each zone, since when, and which inputs it uses; dimming or turning a zone off.
- **Putting a look on:** choosing a zone and a look should take seconds, with a way to preview before committing.
- **Always within reach:** the tempo (BPM, the beat, and where it comes from: internal, Pro DJ Link or the music), preview-only, and whether anything needs attention.
- **Looks:** browse all 29 by category, see them move before choosing, know which ones need tempo, music or Home Assistant, and keep favourites.
- **Shaping a look:** its layers (order, blend mode, opacity, on or off); each layer's settings, which can be numbers, colours, palettes, an anchor or any point in the home, a zone, or a set of lights; modifiers; the transition; and making any setting follow a live signal. Save variations as new looks, or reset to the original.
- **The home map:** place and rotate each light as a point, a line, a bent line, a cylinder or a grid of LEDs. Add anchors and sub-zones. Positions that were guessed stay marked until confirmed.
- **Devices:** every light and PC part with its room, model, LED count, capabilities (colour, multizone, matrix, built-in effects) and live colours. Status: online, offline, switched off elsewhere, running its own effect, or streamed. Latency, send rate and dropped frames. Identify (blink), find new lights, override a latency, remove.
- **Inputs:** the tempo source, BPM, tap tempo, beat and bar position, and Pro DJ Link decks; Music Assistant's connection, player group, and live loudness and spectrum; Home Assistant's connection and the chosen entities' live values; every signal's live value and which looks use it.
- **Settings:** preview-only, a global brightness cap, location and north, the engine's frame rate, the Pro DJ Link network interface, LIFX, Govee and OpenRGB (on or off, and their hosts), and backup and restore of everything as a file.

## States to design

- A light that is offline, switched off elsewhere, running its own built-in effect, or getting a streamed copy because it can't run the effect itself.
- A look that crashed; a zone running slow at a reduced frame rate.
- An input disconnected or stale; no music playing; no DJ.
- Preview-only on: make it unmistakable.
- A transition in progress between two looks.
- Empty states (no lights placed, nothing running) and a reconnecting live connection.

## Please deliver

High-fidelity designs for everything above, including the states, at desktop and phone sizes, ready to hand off to Claude Code.
