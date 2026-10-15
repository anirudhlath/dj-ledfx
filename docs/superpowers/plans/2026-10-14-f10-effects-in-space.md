# F10 Web App Effects in Space Implementation Plan (first slice)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The stage draws what the zones' looks are doing in the room, from §12.4's `fx` stream: the particles of M5's eleven particle looks, Shockwave's shell, Speaker waves' kick fronts and Ripples' drops as rings, and Scanner's plane and Shockwave's beam as planes, on the live stream and on the composer's preview. Desktop Live gets §7.4's "Effects in space" switch, on by default and remembered. The owner wants this slice so they can see how each particle look meets the lamps on the stage, and tune the eleven looks (issues #48–#58). Done when the mock's hero draws its fireflies and comets on the stage, every scenario's screenshots carry their looks' effects, the switch takes them off and puts them back, and, once engine M8's PR and this one have both merged and the owner says go, they have previewed each of the eleven particle looks on the real engine (Task 11).

**Architecture:**
- **The data layer** (`src/api/`).
  - `ws-messages.ts` reads the `fx` message item by item: a zone or an item that isn't well formed is dropped, never the message, and a key it doesn't know is ignored (§12.4's "Extending it").
  - `fx.ts`'s `FxStore` keeps the latest picture, by zone, for each stream (`live`, `preview`), and a `version` that moves with every picture. React never watches it, as it never watches the frame store.
  - `LiveClient.subscribeFx(on)` sends `subscribe_fx`, sends it again at every link-up while on, stores pictures only while on, and clears the store on off and on a drop.
  - `live.ts`'s `wantFx()` counts the stages that want the channel; `use-fx.ts`'s `useFxStream(on)` is a component's way in.
- **The mocks** (`src/api/mocks/mock-fx.ts`) give each look that draws in space a simple moving picture of its kind round its lights, and `MockServer` sends the whole picture at most 30 times a second, only to a session that asked, and only when it changed.
- **The stage** (`src/stage/`).
  - `fx-writer.ts`'s `FxWriter` writes the store's picture of the zones the stage picks into typed arrays it keeps. They grow to the most it has written and never shrink.
  - `scene/fx-shaders.ts` and `scene/fx-meshes.ts` draw them: one `InstancedMesh` each for particles, rings and planes over the writer's own arrays. Every number comes from `RENDER.particle` (Main.html's fireflies, read by `npm run design:numbers`), `SPEC.window.glassAlpha` and `POOL_LIFT_M`.
  - `scene/fx-layer.tsx` puts them on the canvas.
  - `scene/draw-list.ts`'s `DrawList` gives the stage one draw tick for both layers: `StageScene` owns the cadence, the light layer and the fx layer each write what's new, and the canvas renders once if either did. The cadence wakes for a new picture as it does for a new frame.
  - `behaviour.ts` says where the effects are drawn. `StageView` works out which zones' effects it draws (`FxPick`), asks for the channel while it draws them, and draws the switch in the tools.
- **The browser:** e2e draws the effects in every stage screenshot. The mock marks the page once it has sent a picture, so a screenshot waits for it. `e2e:perf` measures the hero with its effects drawn beside the firmware scenario.

**Tech Stack:**
- Unchanged from F4: Vite 8, React 19, TypeScript 5.9 (strict, `erasableSyntaxOnly`, `verbatimModuleSyntax`), React Three Fiber's `createRoot` and three.js, zustand 5, MSW, Vitest, Playwright with axe.
- Three.js: `ShaderMaterial` with additive blending, `InstancedMesh` over `InstancedBufferAttribute`s (`DynamicDrawUsage`).
- No new dependencies. No backend change.

**Spec:**
- `docs/superpowers/specs/2026-09-23-web-app-rebuild-design.md`:
  - §13.1, row M10: "Doorbell/overlay, effects in space (`fx`), reduced motion, performance and accessibility pass". This plan is the effects in space, and only them (ruling 1).
  - Sections read for this plan: §5.4, §7.4, §7.5, §7.6, §8.1 (the stage's overlays), §8.10 (the phone's stage), §12.4 (the `fx` row, `subscribe_fx`, and "The `fx` payload"), §12.5, §14.
- `docs/superpowers/specs/2026-09-23-home-effects-engine-design.md`:
  - The M8 row: "The `fx` stream: particles, rings, planes and sun shafts drawn on the web app's stage (brought forward on 2026-10-14, after M5, so the particle looks can be tuned on the stage; sun shafts follow M6's sun)".
  - §10: "F10 Effects in space | M8".
- Engine M8's plan, `docs/superpowers/plans/2026-10-14-m8-effects-in-space.md`, written beside this one. The two meet only at §12.4's `fx` payload, which both build against as the spec fixes it.
- The renders, in the main checkout: `/home/anirudhlath/code/private/dj-ledfx/docs/design/web-app/reference/`. `Main.png` and `Main.html` draw the fireflies in the room (`<g class="ffN">`), and so do `Phone-Live` and `Phone-Zone`. `Live-PutLookOn` and `State-Reconnecting` draw none.

**What exists** (master at `3ac0dac`, plus `57455a7`, which wrote "The `fx` payload" into the web spec):
- Engine M5 serves the eleven particle looks, and M3 the tempo looks (Shockwave, Speaker waves, Scanner); M2's Ripples is a field. No engine serves `fx` yet: engine M8 does, in its own PR (ruling 18).
- `web/src/api/ws-messages.ts`:
  - `Command` already has `subscribe_fx {on}`.
  - `FxMessage` is a placeholder, `{ channel: 'fx' }`: "Typed so it's recognised; nothing reads it before F10".
- `MockServer` acks `subscribe_fx` and sends nothing.
- The stage:
  - The light layer draws on its own `useCadence`.
  - The cadence sleeps until `FrameStore.onNextFrame()` wakes it.
  - `StageTools` draws `3D | Plan` and the Labels switch. Its comment says "Effects in space" waits for the fx stream, per §7.4's "until that exists the toggle is hidden".
  - `StoredView` remembers `view` and `labels` per route.
  - `RENDER` has nothing of the fireflies.

**Execution:** in a new worktree, `~/code/.worktrees/dj-ledfx/web-f10`, on branch `feature/web-f10-effects-in-space`, from `origin/master` (Before Task 1), by the method the owner picks.
- Tasks 1 to 10 run in order. Task 10 opens the PR and never merges it.
- No review runs beyond the one the owner's method runs: reviews only on request. Every finding a review raises is fixed, Minor ones included.
- Task 11 is the owner's acceptance. It waits until engine M8's PR and this one have both merged, and then for the owner's "go" for the deploy.

**How to read the code.**
- A new file is given whole after "Create".
- A change to an existing file is a unified diff, in a `diff` block, against the file as `57455a7` and the earlier tasks leave it. Apply the blocks in the order given. Save a block to a file and run `git apply` on it (`git apply /tmp/f10-step.diff`), or make the same edit by hand.
- If master has moved past `3ac0dac` and a block no longer applies, make the edit by hand: its hunks say where.
- Every block was applied, and every count below measured, on a copy of `57455a7` (`~/code/.worktrees/dj-ledfx/plan-check-f10`); a newer master may add tests.
- Two kinds of file are never written by hand:
  - `web/src/stage/design-numbers.ts`, which `npm run design:numbers` writes (Task 4);
  - the screenshot baselines under `web/e2e/*-snapshots/`, which Playwright records after a comparison by eye (Task 8).

---

## Global Constraints

Every task's requirements include this section. Quotes are the spec's or CLAUDE.md's own words, with their sections.

**Source of truth**
- CLAUDE.md, "Web App Design":
  - "The Claude Design handoff is the only source of design truth. Don't work from memory, a summary or an earlier conversation."
  - "Behaviour, structure, data contract and copy: the web app spec. Look and layout: the reference renders."
  - "Use `tokens.css`, `icons.ts`, `looks.json` and `home.json` as they are … Never retype a token, colour, size, icon path or look description, and never restate design values in docs or in this file."
  - "Before each web app task, re-read the spec sections and look at the renders that the task names." Each task's Step 1 names them. View each PNG once per task and write down what you see; where a picture can't settle something, read the HTML beside it.
- How code reaches a design value:
  - `RENDER.particle` (Task 4), read from Main.html's fireflies by `npm run design:numbers`, for how a particle is drawn;
  - `SPEC.window.glassAlpha` (§7.1's glass pane, already generated), for how faint a ring or a plane is;
  - `POOL_LIFT_M` (`scene/light-shaders.ts`), for how far a level circle sits over the floor, as the pools do.
  - This plan names numbers by those keys and never states them. Never edit `design-numbers.ts` by hand.
  - The mock's sizes and speeds (`mock-fx.ts`) are no design value: they only keep the stage alive until engine M8 sends the real looks, and the file says so.
- The byte copies (`tokens.css`, `icons.ts`, `looks.json`, `home.json`) change only by `cp`, and F10 changes none.
- §10 Copy: the switch's label is §8.1's own, "Effects in space". F10 writes no other copy.

**What to draw** (§7.4, §7.6, §8.1, §5.4)
- §7.4: "Where the engine can describe what a look is doing in 3D (particles, fields, rings, the sun), the stage draws it faintly in the room, not only on lamps: firefly and ember particles (tiny glowing points), sun shafts through the west windows onto the bedroom floor, the doorbell's gold ring clipped to the apartment outline, the Scanner plane, Shockwave spheres. This is the "Effects in space" toggle (default on). It needs the `fx` stream (12.4); until that exists the toggle is hidden and the stage shows lamps and pools only."
- §8.1: "Overlays: top-left `3D | Plan`, "Effects in space" and "Labels" switches".
- §7.6's `live` row: "Live colours, particles, sun, labels …"; `compose`: "the chosen zone renders the **preview stream** instead of live"; `focus`: "other zones' lights hidden"; `frozen`: "Last frame, grayscale 85%, brightness 55%, no animation".
- §5.4: "`prefers-reduced-motion`: stop particles, beat pulses, thumbnail loops and live-dot pulses. The stage still updates light colours, at most once per second."

**The data contract** (§12.4, binding)
- The channel: "`fx` | when subscribed, ≤ 30 Hz | optional: particles `[x,y,z,r,g,b,size]`, rings, planes, sun shafts per zone, for "Effects in space"". The command: "`subscribe_fx {on}`".
- "The `fx` payload" (engine M8, fixed 2026-10-14 so the engine and the web app build against one shape):

  ```ts
  interface FxMessage { channel: 'fx'; zones: ZoneFx[] }      // the whole picture: each message replaces the last
  interface ZoneFx {
    zoneId: Id
    stream: 'live' | 'preview'                                 // which frames it belongs with, as frame v2's stream byte
    particles?: [x: number, y: number, z: number, r: number, g: number, b: number, size: number][]
    rings?: { center: Vec3; radius: number; width: number; rgb: Vec3; form: 'sphere' | 'circle' }[]
    planes?: { point: Vec3; normal: Vec3; width: number; rgb: Vec3; ray?: Vec3 }[]
  }
  type Vec3 = [number, number, number]
  ```

  - "Positions and lengths are metres in the home map's frame (z up), the frame the stage places the LEDs in: an effect's own space (a layer's transform, its mirror) is mapped back, and a mirrored layer sends each thing at every place the mirror shows it. Colours are linear 0–1, after the zone's brightness. Numbers are rounded to 3 decimals."
  - "What a zone sends is what its lights show at now: the engine keeps each rendered frame's `fx` beside its colours and sends the newest at or before now, the moment the live and preview frames are read at."
  - "A `circle` lies level (its axis is z); a `sphere` is a shell. A plane is infinite unless it has a `ray`, a direction in the plane: then it is the half on that side of `point` (a lighthouse beam). `width` is how thick the shell, ring or plane is drawn."
  - "A zone with nothing to draw is left out, and a message with no zones clears the stage. The server sends at most 30 a second and only to a session that sent `subscribe_fx {on: true}`, until `{on: false}`; it sends nothing while nothing changes."
  - "**Extending it:** a later kind (M6's sun `shafts`, the doorbell's ring) is a new optional key on `ZoneFx`, or a new optional field on an item. The client ignores keys it doesn't know, and the server never renames or removes one, so neither side bumps a version."
  - "**What draws what (M8's first slice):** every particle effect (M5's eleven looks) sends `particles`; Shockwave's shell and Speaker waves' kick fronts send `sphere` rings, Ripples' drops `circle` rings; Scanner sends a level plane and Shockwave's beam a plane with a `ray`. Firmware layers send nothing. Sun shafts wait for M6's sun."
- §12: "Components never call `fetch` or touch the socket directly." The stage reaches the channel through `useFxStream()` and `wantFx()`, never the client.
- §12.5: the mocks play every scenario with no engine, so they send `fx` too (Task 3).

**Performance** (§7.5, §14)
- §7.5: "**No React state per frame.** React re-renders only when geometry or selection changes." Pictures never pass through React: the store is read on the stage's cadence.
- §7.5: "pause rendering when the tab is hidden; drop to 30 fps on phone". The effects draw on the stage's one cadence, so they keep both.
- §14: "stage ≥ 55 fps p95 with 412 LEDs streaming at 60 fps on desktop, ≥ 30 fps on a recent phone; main thread idle ≥ 50% on Live; first load < 400 KB gzipped JS excluding three.js". `npm run e2e:perf` measures the first two, with the effects drawn too (Task 8). `npm run build` checks the budget.
- No allocation that grows with the pictures: the writer's arrays grow to the most it has written and are reused (ruling 15).

**Public repo and live system**
- The repo is public. None of these may appear in the plan, the code, the tests, CLAUDE.md, the commit messages or the PR: LAN addresses, MACs, SSIDs, light names, light model names, room names, the home's location or AI model names.
  - Room and look names come only from the design files, never retyped: tests read them from the fixtures, and e2e paths carry ids.
  - A test address is `127.0.0.1`, and a Govee test device `test-lamp`.
  - No model identifier in a commit or PR. The PR body ends with "🤖 Generated with [Claude Code](https://claude.com/claude-code)".
- The deployed `dj-ledfx-app-1` is never touched in Tasks 1 to 10. F10 runs on the mocks, the dev server and the test suites: no docker, no port 8080, no UDP 4002, no lights, no UFW and no master.
- Task 11 is the one exception, and only with the owner's "go" for each step. Ask before the deploy and before any step that reaches a real light; never wait for a clock window. After any run that stops the deployed app, check that `ss -ulne 'sport = :4002'` shows `uid:10001`.

**Workflow** (CLAUDE.md and the owner's standing rules)
- The executor works in `/home/anirudhlath/code/.worktrees/dj-ledfx/web-f10`, on branch `feature/web-f10-effects-in-space`, made in "Before Task 1". It works nowhere else.
- This PR merges to master on its own: it doesn't stack on engine M8's branch, and M8's doesn't stack on it. The owner merges.
- Slice simple first: ship the simplest slice that serves the goal. No speculative generality beyond the payload's own extension rule.
- Never a bare `git stash`. Use a temporary commit, or `git stash push -m <tag>` and apply that entry by its SHA.
- Run commands from the worktree root, and web commands in a subshell: `(cd web && …)`.
- During a task, run only the task's own test files. Run the gate once, before the task's commit, as its last step says.
- e2e uses :4174 and :4175 with `strictPort`, so only one worktree can run it at a time. Before every `npm run e2e` or `npm run e2e:perf`, wait until neither port is taken, for ten minutes at most:

  ```bash
  for i in $(seq 1 60); do [ "$(ss -ltn | grep -cE ':(4174|4175) ')" = 0 ] && break; sleep 10; done; ss -ltn | grep -cE ':(4174|4175) '
  ```

  It must print `0`. If it doesn't, another worktree is still running e2e: run the loop again.
- Python: `uv` only (`uv sync --extra web` for `api:check`). F10 changes no Python.
- Lines run to about 140 characters. There's no formatter. `erasableSyntaxOnly` rules out enums and parameter properties. `verbatimModuleSyntax` needs `import type` for types.
- ESLint enforces react-refresh (a `.tsx` file exports only components, so `useFxStream` lives in `use-fx.ts`) and the React Compiler's rules (no ref read during render, no `Date.now()` in render, no setState straight from an effect).
- Vitest's fake timers hang `userEvent`, so a test on fake timers drives the page with `fireEvent`.
- Context7 needs authorizing and was unavailable while this plan was written. The three.js this plan uses (`ShaderMaterial`, `InstancedMesh`, `InstancedBufferAttribute`, additive blending) is what the light layer already uses; Task 6's tests and Task 8's e2e and perf runs measured it in Chromium.

## Decisions already made

These fill gaps in the spec. The owner sees them in the plan's report, and should look at the ones marked [owner] in particular. Reviewers: don't reverse one without asking. Code comments cite them as "F10 ruling N". Each says what was decided, why, and what it costs if it's wrong.

1. **The slice.** [owner]
   - What: F10 draws §12.4's first-slice kinds (particles, `sphere` and `circle` rings, planes), live and preview, and the switch.
   - Deferred, and named so wherever they would be expected:
     - sun shafts (M6's sun);
     - the doorbell's gold ring and the overlays (M6 and M7);
     - the rest of F10's reduced-motion, performance and accessibility pass (§13.1's M10 row).
   - Why: the owner brought M8 and F10 forward on 2026-10-14 so they can see the particle looks on the stage and tune them (issues #48–#58); nothing else in M10 serves that.
   - Cost if wrong: a later slice adds a key to `readFx`, `FxWriter` and a mesh (Hand-off). Nothing here needs undoing.
2. **The switch** sits in `StageTools` between `3D | Plan` and Labels, Main.html's order, on desktop only. [owner]
   - What: it's stored per route in `StoredView.effects`, default on, beside `labels`, so Live's switch is Live's.
   - Why: §8.1 places it, §7.4 says "default on", and the view memory already keeps the Labels switch per route.
   - Cost if wrong: one field moves.
   - §7.4's "until that exists the toggle is hidden" no longer holds: the stream exists in the contract and the mock now. Until engine M8 merges, the real engine sends nothing, so the switch, on, draws nothing there. That's a spec conflict the report names.
3. **The phone always draws the effects, and has no switch.** [owner]
   - What: the phone's stage has no tools (§8.10). Phone-Live and Phone-Zone draw the fireflies.
   - Why: a switch the phone can't reach would hide them for good.
   - Cost if wrong: a later phone setting reads `StoredView.effects` too.
4. **Where they're drawn** (`stageBehaviour().effects`). [owner]
   - Live, compose and focus follow the stored switch on desktop; the phone always draws them.
   - Frozen never draws them: §7.6's "no animation", and the Reconnecting renders draw none. The store also clears on a drop (ruling 7).
   - Reduced motion never draws them: §5.4's "stop particles". The rings and planes stop with them. A later pass may keep a still picture; this slice keeps none.
   - Map mode (F7) isn't built. When it is, it draws none, by the nearest rule the spec gives (§7.4's sun is drawn "in all modes except map").
   - Why: the table is §7.6's, and `stageBehaviour()` is the one place that reads the mode.
   - Cost if wrong: one line in `behaviour.ts`.
5. **Compose draws the preview's effects on the composer's zone, and hides the live effects of the zones under it.** [owner]
   - What: a running zone with any light in the previewed zone has its live effects hidden while the preview is on.
   - Why: §7.6 "the chosen zone renders the **preview stream** instead of live"; drawing both would put two looks on one zone.
   - Differs from the renders: Live-PutLookOn draws no particles. It previews a field look; the rule draws whatever the previewed look sends.
   - Cost if wrong: a running zone that only shares one light with the preview loses all its effects for the preview's length. `fxPick` in `stage-view.tsx` is where to change it.
6. **Focus draws the effects of the zones with a light in the focused zone, and hides the rest.**
   - Why: §7.6 focus hides "other zones' lights", and their effects with them.
   - Cost if wrong: one condition in `fxPick`.
7. **The subscription.**
   - What:
     - `wantFx()` counts the stages that want the channel; the channel is on while any does.
     - The client sends `subscribe_fx` once per change, and again at every link-up while on.
     - Off clears the store, and so does a drop: the server forgets the subscription with the link, and the picture is of a moment that's gone.
     - A picture is stored only while on, so one still on its way after an off is ignored.
     - A reset lets every want go, and a want from before it can't let go of a later one.
   - Why: §12.4 "only to a session that sent `subscribe_fx {on: true}`, until `{on: false}`". The phone and desktop stages can both be mounted for a moment; StrictMode mounts twice.
   - Cost if wrong: duplicate subscriptions cost the server work, and a stale picture is drawn after a drop. Review Focus 1 and 2 pin both.
8. **Validation is per item.**
   - A zone without its `zoneId` or a known `stream` is dropped. So is an item that isn't well formed:
     - a particle with fewer than seven finite numbers, or a size not above 0;
     - a ring with a negative radius, no width, or a form it doesn't know;
     - a plane with a zero normal, no width, or a zero `ray`.
   - A message without `zones` is ignored. A key the client doesn't know is ignored, and a particle longer than seven is read as its first seven (§12.4's "Extending it").
   - Why: the other channels are checked the same way, and one bad item shouldn't blank the stage.
   - Cost if wrong: a malformed item is silently missing. Pinned in `ws-messages.test.ts`.
9. **The store** keeps the last message's picture, by zone, for each stream. A zone sent twice: the last wins. The preview stream's pictures are held while the frame store holds the preview's frames (`frames.previewHeld`, F4's), so the stage shows one look on the composer's zone.
10. **A particle is Main.html's firefly.** [owner]
    - What:
      - Its glow's radius is the particle's `size` in metres, so the reach drawn is the reach it lights the lamps with, falling off as the render's radial gradient does (`RENDER.particle.glow.stops`).
      - The core's radius in CSS px is the glow's times `RENDER.particle.core.share`, held between `minPx` and `maxPx`.
      - The core is lifted towards white by `lift` at its own intensity.
      - It's additive, not clipped to the rooms: the engine's fireflies, flock and fountain go past the zone (CLAUDE.md, Key Design Decisions), and §7.4 draws them "in the room".
    - Why: Main.html draws every firefly so: one radial gradient on every glow, and a core on a rule `design-extract.ts` checks on every firefly, throwing with the firefly's numbers if one is drawn off it.
    - Cost if wrong: only `RENDER.particle` and the particle shader change.
11. **Rings.** [owner]
    - What:
      - A `sphere` is drawn as a disc facing the camera. At each point it's as bright as the shell is thick along the line of sight there, as a share of its `width`, so its rim is brightest.
      - A `circle` is a level annulus `width` across, lifted `POOL_LIFT_M` over its centre's height.
      - Both are at `SPEC.window.glassAlpha` times their colour.
    - Why: §7.4's "faintly", and §7.1's glass pane is the stage's one number for a translucent surface. No render draws a ring.
    - Cost if wrong: a uniform per kind.
12. **Planes.** [owner]
    - What:
      - A plane is drawn inside the home's outline (its mask) and between the floor and the ceiling.
      - With a `ray`, only the half on the ray's side is drawn.
      - It's `SPEC.window.glassAlpha` face on, thickening to 1 edge on, as a pane of glass seen along it does.
    - `width` isn't drawn. A quad edge on has no area, and a slab would need six faces clipped against the outline. §12.4 says "`width` is how thick the shell, ring or plane is drawn". The writer keeps it, so a later pass can draw it. That's a spec conflict the report names.
    - Why: §7.4's "the doorbell's gold ring clipped to the apartment outline" is the spec's rule for what crosses the home, and a plane is infinite.
    - Cost if wrong: Scanner's sheet reads thin edge on, and only the plane shader changes.
13. **Depth.** The effects test depth and never write it, and add. A wall in front hides them, and they never hide one another or the lamps.
14. **Colours** are linear (the canvas is `linear` and `flat`), carry the zone's brightness (§12.4), and are clamped to 0–1 as they're written.
15. **No growing allocation.**
    - What:
      - The writer's arrays grow to the most it has written, at least doubling, and never shrink.
      - The meshes are made again only when the arrays grow (a new `generation`), and otherwise only flag their attributes for upload.
      - The writer writes only when the store's version or the pick moved.
    - Why: §7.5's "never create objects per frame".
    - Cost if wrong: a stage that once drew a crowd keeps its arrays: at most §12.4's numbers for the most the engine has sent.
16. **One draw tick.**
    - What: the light layer no longer owns a cadence. `StageScene` owns the one `useCadence`, and its `DrawList` asks each layer to write what's new and renders once if any did. The cadence's version is the frame store's plus the fx store's, and it sleeps until either moves.
    - Why: two cadences would render the canvas twice a tick, and a picture arriving while no frame does would never be drawn.
    - Cost if wrong: Review Focus 4.
17. **The mocks send `fx`.**
    - What:
      - Each look that draws in space gets a simple moving picture of its kind, round the box its streamed lights span: particles that wander or orbit, Shockwave's shell and beam, Speaker waves' front, Ripples' two drops, and Scanner's level plane.
      - A zone waiting for its input sends nothing; a crashed one holds its picture; the preview's look draws on the preview stream.
      - At most 30 a second, only to a session that asked, only when changed. Under `?still` the picture holds, so it goes out once.
      - The browser's mock marks the page (`<html data-mock-fx>`) after its first send, for e2e.
    - Why: §12.5, and e2e and the screenshots need pictures with no engine.
    - Cost if wrong: only the mock and the baselines change. The mock's numbers are no design value.
18. **Engine M8 merges on its own.** This PR needs nothing from M8's: the contract is the spec's, and the mock stands in. Either can merge first. Task 11 waits for both.
19. **The acceptance is the owner's** (Task 11): previewing each particle look on the real engine touches no light, but the deploy does, so it waits for his "go".

## Review Focus

These are the five failure modes the spec implies that are most likely to bite, most likely first. Each has a test in the task that owns the code.

1. **Subscriptions leak, double, or are lost.** Two stages mount (StrictMode, or desktop and phone for a moment), the link drops and comes back, or the data layer resets.
   - Expected: one `subscribe_fx {on: true}` while anything wants the channel, sent again once at each link-up; one `{on: false}` once nothing does; a want from before a reset can't let a later one go.
   - Pinned in:
     - Task 2: "asks for it when the stage does and lets go when it stops, once each", "asks again at every link-up while it wants the channel, once each", "asks for the fx channel while anything wants it, and lets go once nothing does", "lets a want from before a reset go without touching a later one's".
     - Task 7: `use-fx.test.ts`.
2. **A stale picture stays drawn.** After the switch goes off, the link drops, the stage freezes, or a picture arrives after an off.
   - Expected: the store is empty, and the canvas draws without them.
   - Pinned in:
     - Task 2: "stores each picture while it wants them, and none after", "forgets the picture when the link drops".
     - Task 6: "draws no effects in space while it picks none, and lets them go when it stops".
     - Task 7: "freezes on Reconnecting and thaws when the link is back".
3. **Allocation grows with the pictures.**
   - Expected: the writer reuses its arrays, and the meshes are made again only when the arrays grow.
   - Pinned in: Task 5's `fx-writer.test.ts` and Task 6's `fx-meshes.test.ts`.
4. **The canvas renders twice a tick, or never wakes for a picture.**
   - Expected: one render per cadence tick that wrote anything, and a picture alone wakes a sleeping cadence.
   - Pinned in: Task 6: "wakes for a new picture of the effects in space, as for a frame", and "draws the hero's effects in space beside its lights, rendering once a draw".
5. **The wrong zones are drawn.** A zone under the composer's preview drawn twice, or a zone outside focus drawn.
   - Expected: compose draws the preview's effects and hides the live effects of the zones under it; focus hides the zones with no light in it.
   - Pinned in: Task 5's pick test, and Task 7's compose and focus tests in `stage-view.test.tsx`.

## File Structure

```
web/
  scripts/
    design-extract.ts            Modify: RENDER.particle, from Main.html's fireflies
  src/
    api/
      ws-messages.ts             Modify: FxParticle, FxRing, FxPlane, ZoneFx, FxMessage; readFx()
      fx.ts                      Create: FxStore
      live-client.ts             Modify: the `fx` option; subscribeFx(); fx stored while on, cleared on a drop
      live.ts                    Modify: `fx`, wantFx(); reset with the data layer
      use-fx.ts                  Create: useFxStream()
      mocks/
        mock-fx.ts               Create: zoneFx(), what each look draws in space
        mock-server.ts           Modify: the fx channel; the preview's zone and look; onFx
        browser.ts               Modify: the data-mock-fx mark
    stage/
      design-numbers.ts          Regenerate (npm run design:numbers)
      fx-writer.ts               Create: FxPick, LIVE_ONLY, FxBatch, FxWriter
      cadence.ts                 Modify: wakes on a frame or a picture
      behaviour.ts               Modify: `effects`
      view-memory.ts             Modify: StoredView.effects
      stage-view.tsx             Modify: fxPick, useFxStream(), the switch
      overlays/stage-tools.tsx   Modify: the "Effects in space" switch
      scene/
        fx-shaders.ts            Create: particleMaterial(), ringMaterial(), planeMaterial()
        fx-meshes.ts             Create: FxMaterials, FxMeshes
        fx-layer.tsx             Create: FxLayer
        draw-list.ts             Create: DrawList
        light-layer.tsx          Modify: draws through the DrawList
        stage-scene.tsx          Modify: owns the cadence and the DrawList; `fx`
    test/
      stage.ts                   Modify: sceneProps' `fx`
  e2e/
    helpers.ts                   Modify: fxPictured()
    stage.spec.ts                Modify: the switch in the browser
    live.spec.ts                 Modify: screenshots wait for the picture
    compose.spec.ts              Modify: the same
    shell.spec.ts                Modify: the same
    stage.perf.ts                Modify: the hero with its effects, beside the firmware scenario
    *-snapshots/                 Re-record (Playwright), after a comparison by eye
CLAUDE.md                        Modify (Task 9)
```

Tests sit beside the code they test: `ws-messages.test.ts`, `fx.test.ts`, `live-client.test.ts`, `live.test.ts`, `use-fx.test.ts`, `mocks/mock-fx.test.ts`, `mocks/mock-server.test.ts`, `stage/design-numbers.node.test.ts`, `stage/fx-writer.test.ts`, `stage/cadence.test.ts`, `stage/behaviour.test.ts`, `stage/view-memory.test.ts`, `stage/stage-view.test.tsx`, `stage/overlays/overlays.test.tsx`, `stage/scene/fx-meshes.test.ts` and `stage/scene/stage-scene.test.tsx`.

## Before Task 1

- [ ] **Step 1: Make the worktree**

```bash
git -C /home/anirudhlath/code/private/dj-ledfx fetch origin
git -C /home/anirudhlath/code/private/dj-ledfx worktree add -b feature/web-f10-effects-in-space /home/anirudhlath/code/.worktrees/dj-ledfx/web-f10 origin/master
W=/home/anirudhlath/code/.worktrees/dj-ledfx/web-f10; cd "$W"
grep -q 'The `fx` payload' docs/superpowers/specs/2026-09-23-web-app-rebuild-design.md && grep -q "nothing reads it before F10" web/src/api/ws-messages.ts && echo "the payload is fixed, F10 isn't here"
git log --oneline -3
```

Expected: "the payload is fixed, F10 isn't here". The log's newest commit is master's. If the first `grep` fails, the plans' docs PR (with `57455a7`) hasn't merged yet: stop and tell the owner.

- [ ] **Step 2: Install, and check the pins**

```bash
uv sync --extra web
(cd web && npm ci)
(cd docs/design/web-app && sha256sum -c --ignore-missing HANDOFF.sha256 | grep -v ': OK$'; echo "pins checked")
(cd /home/anirudhlath/code/private/dj-ledfx/docs/design/web-app && sha256sum -c HANDOFF.sha256 2>/dev/null \
  | grep -E 'reference/(Main|Phone-Live|Phone-Zone|Live-PutLookOn)\.(html|png): ' | grep -v ': OK$'; echo "renders checked")
```

Expected: "pins checked" and "renders checked", with no line between them. A render that fails its pin stops the plan: tell the owner.

- [ ] **Step 3: Record the baselines**

```bash
(cd web && npm test 2>&1 | grep -E 'Test Files|Tests ' && npm run lint && npx tsc -b && echo "tsc ok" && npm run api:check && npm run build 2>&1 | tail -1)
```

Expected: everything passes. On `57455a7`:
- Vitest: `Test Files  102 passed (102)` and `Tests  1036 passed (1036)`;
- the build: `…/web/dist: no mocks, 282.3 KB of gzipped JS`.

Write down this master's own numbers. The counts below are those of `57455a7`, and a newer master adds its own to each.

- [ ] **Step 4: Record the Playwright baselines**

```bash
for i in $(seq 1 60); do [ "$(ss -ltn | grep -cE ':(4174|4175) ')" = 0 ] && break; sleep 10; done; ss -ltn | grep -cE ':(4174|4175) '
(cd web && npx playwright install chromium && npm run e2e 2>&1 | tail -3)
for i in $(seq 1 60); do [ "$(ss -ltn | grep -cE ':(4174|4175) ')" = 0 ] && break; sleep 10; done; ss -ltn | grep -cE ':(4174|4175) '
(cd web && npm run e2e:perf 2>&1 | grep -E '^\{|passed|failed')
```

Expected: each port check prints `0`. e2e: `159 passed` and `105 skipped` on `57455a7`. `e2e:perf`: `2 passed`, each with a JSON line. Write down each project's `fps`, `p95GapMs` and `busy`: Task 8 compares the hero's with them.

---

### Task 1: Read the `fx` stream into a store

§12.4 fixes the payload. The client reads it as it reads every other channel, item by item, and keeps the latest picture where the stage can read it without React: `FxStore`, which the frame store's shape follows.

**Files:**
- Modify: `web/src/api/ws-messages.ts`
- Create: `web/src/api/fx.ts`
- Test: `web/src/api/ws-messages.test.ts`, `web/src/api/fx.test.ts` (create)

**Interfaces:**
- Consumes: `Id`, `Vec3` and `FrameStream` from `contract.ts`; `IS` in `ws-messages.ts`.
- Produces:
  - `ws-messages.ts`: `FxParticle`, `FxRing`, `FxPlane`, `ZoneFx`, and `FxMessage { channel: 'fx'; zones: ZoneFx[] }`. `parseMessage()` reads the `fx` channel through `readFx()` (ruling 8).
  - `fx.ts`: `FxStore` with `live` and `preview` (`Map<Id, ZoneFx>`), `version`, `get(zoneId, stream?)`, `empty`, `apply(message)`, `clear()` and `onNextChange(wake)`; `FxStoreOptions { previewHeld?: () => boolean }` (ruling 9).

- [ ] **Step 1: Read the spec and the code**

Read §12.4 ("The `fx` payload" in full), §7.4 and §7.5. Then read `web/src/api/ws-messages.ts` (`IS`, `PAYLOADS`, `parseMessage`) and `web/src/api/frames.ts` (`version`, `onNextFrame`, `previewHeld`). Task 1 draws nothing, so it has no render to look at.

- [ ] **Step 2: Write the failing tests**

```diff
diff --git a/web/src/api/ws-messages.test.ts b/web/src/api/ws-messages.test.ts
index 714b8c8..a48d2d1 100644
--- a/web/src/api/ws-messages.test.ts
+++ b/web/src/api/ws-messages.test.ts
@@ -1,5 +1,21 @@
 import { describe, expect, it } from 'vitest'
-import { parseMessage } from './ws-messages'
+import { parseMessage, type FxMessage } from './ws-messages'
+
+/** A well-formed fx message's zone: a particle, a shell, a level ring, a plane and a half plane. */
+const ZONE = {
+  zoneId: 'living',
+  stream: 'live',
+  particles: [[1, 2, 1.5, 0.5, 0.4, 0.1, 0.2]],
+  rings: [
+    { center: [3, 4, 1], radius: 2, width: 0.3, rgb: [1, 0.5, 0], form: 'sphere' },
+    { center: [3, 4, 0], radius: 1, width: 0.2, rgb: [0, 0.5, 1], form: 'circle' },
+  ],
+  planes: [
+    { point: [3, 4, 1], normal: [0, 0, 1], width: 0.3, rgb: [1, 1, 1] },
+    { point: [3, 4, 1], normal: [1, 0, 0], width: 0.3, rgb: [1, 1, 1], ray: [0, 1, 0] },
+  ],
+}
+const fx = (...zones: unknown[]) => parseMessage(JSON.stringify({ channel: 'fx', zones })) as FxMessage
 
 describe('parseMessage', () => {
   it('reads a channel message', () => {
@@ -26,6 +42,71 @@ describe('parseMessage', () => {
     expect(parseMessage(text)).toBeNull()
   })
 
+  it('returns null for fx without its zones', () => {
+    expect(parseMessage('{"channel":"fx"}')).toBeNull()
+    expect(parseMessage('{"channel":"fx","zones":{}}')).toBeNull()
+  })
+
+  // §12.4's fx block (F10 decision 1).
+  describe('fx', () => {
+    it('reads a well-formed picture as it is', () => {
+      expect(fx(ZONE)).toEqual({ channel: 'fx', zones: [ZONE] })
+      expect(fx()).toEqual({ channel: 'fx', zones: [] })
+    })
+
+    it('drops a zone without its id or its stream, and keeps the others', () => {
+      const zones = fx({ ...ZONE, zoneId: 7 }, { ...ZONE, stream: 'later' }, { stream: 'live' }, 'living', { ...ZONE, stream: 'preview' }).zones
+      expect(zones).toEqual([{ ...ZONE, stream: 'preview' }])
+    })
+
+    it.each([
+      ['too short', [1, 2, 3, 1, 1, 1]],
+      ['a number missing', [1, 2, null, 1, 1, 1, 0.2]],
+      ['text for a number', [1, 2, '3', 1, 1, 1, 0.2]],
+      ['no size', [1, 2, 3, 1, 1, 1, 0]],
+      ['not a list', { x: 1 }],
+    ])('drops a particle that is %s, not the zone', (_, particle) => {
+      expect(fx({ ...ZONE, particles: [particle, ...ZONE.particles] }).zones[0].particles).toEqual(ZONE.particles)
+    })
+
+    it.each([
+      ['a centre that is not three numbers', { center: [3, 4], radius: 2, width: 0.3, rgb: [1, 1, 1], form: 'sphere' }],
+      ['a radius below 0', { center: [3, 4, 1], radius: -1, width: 0.3, rgb: [1, 1, 1], form: 'sphere' }],
+      ['no width', { center: [3, 4, 1], radius: 2, width: 0, rgb: [1, 1, 1], form: 'sphere' }],
+      ['a form it does not know', { center: [3, 4, 1], radius: 2, width: 0.3, rgb: [1, 1, 1], form: 'cube' }],
+      ['no colour', { center: [3, 4, 1], radius: 2, width: 0.3, form: 'sphere' }],
+    ])('drops a ring with %s', (_, ring) => {
+      expect(fx({ ...ZONE, rings: [ring, ...ZONE.rings] }).zones[0].rings).toEqual(ZONE.rings)
+    })
+
+    it.each([
+      ['no normal', { point: [3, 4, 1], normal: [0, 0, 0], width: 0.3, rgb: [1, 1, 1] }],
+      ['a ray of no length', { point: [3, 4, 1], normal: [1, 0, 0], width: 0.3, rgb: [1, 1, 1], ray: [0, 0, 0] }],
+      ['a ray that is not three numbers', { point: [3, 4, 1], normal: [1, 0, 0], width: 0.3, rgb: [1, 1, 1], ray: 'north' }],
+      ['no width', { point: [3, 4, 1], normal: [0, 0, 1], width: -1, rgb: [1, 1, 1] }],
+    ])('drops a plane with %s, rather than draw it whole', (_, plane) => {
+      expect(fx({ ...ZONE, planes: [plane, ...ZONE.planes] }).zones[0].planes).toEqual(ZONE.planes)
+    })
+
+    it("reads a list that isn't one as none", () => {
+      expect(fx({ ...ZONE, particles: 'many', rings: {}, planes: null }).zones[0]).toEqual({ zoneId: 'living', stream: 'live' })
+    })
+
+    // §12.4, "Extending it": a later kind is a new optional key, a later field a new optional one on an item.
+    it('ignores what it does not know: a key of the message, a kind of the zone, a field of an item', () => {
+      const later = {
+        ...ZONE,
+        shafts: [{ from: [0, 0, 0] }],
+        particles: [[...ZONE.particles[0], 0.5]],
+        rings: [{ ...ZONE.rings[0], fade: 0.5 }],
+      }
+      const message = parseMessage(JSON.stringify({ channel: 'fx', zones: [later], at: 12 })) as FxMessage
+      expect(message.zones[0]).not.toHaveProperty('shafts')
+      expect(message.zones[0].particles).toEqual(later.particles)
+      expect(message.zones[0].rings).toEqual(later.rings)
+    })
+  })
+
   it('passes a channel it does not know, for the caller to ignore', () => {
     expect(parseMessage('{"channel":"later","x":1}')).toEqual({ channel: 'later', x: 1 })
   })
```

Create `web/src/api/fx.test.ts`:

```ts
import { describe, expect, it, vi } from 'vitest'
import { FxStore } from './fx'
import type { ZoneFx } from './ws-messages'

const zone = (zoneId: string, stream: ZoneFx['stream'] = 'live', size = 0.2): ZoneFx => ({ zoneId, stream, particles: [[1, 2, 1, 1, 1, 1, size]] })

describe('the fx store (§12.4)', () => {
  it('keeps each zone of the latest picture, by stream', () => {
    const fx = new FxStore()
    fx.apply({ channel: 'fx', zones: [zone('living'), zone('office'), zone('living', 'preview')] })
    expect([...fx.live.keys()]).toEqual(['living', 'office'])
    expect(fx.get('living', 'preview')).toEqual(zone('living', 'preview'))
  })

  // "the whole picture: each message replaces the last"; "a message with no zones clears the stage".
  it('replaces the picture with each message, and clears it with an empty one', () => {
    const fx = new FxStore()
    fx.apply({ channel: 'fx', zones: [zone('living'), zone('office', 'preview')] })
    fx.apply({ channel: 'fx', zones: [zone('kitchen')] })
    expect([...fx.live.keys()]).toEqual(['kitchen'])
    expect(fx.preview.size).toBe(0)
    fx.apply({ channel: 'fx', zones: [] })
    expect(fx.empty).toBe(true)
  })

  it('takes the last of a zone sent twice', () => {
    const fx = new FxStore()
    fx.apply({ channel: 'fx', zones: [zone('living', 'live', 0.2), zone('living', 'live', 0.4)] })
    expect(fx.get('living')).toEqual(zone('living', 'live', 0.4))
  })

  // F4's preview session holds the preview's frames while the server may be playing a look chosen over.
  it("holds the preview's picture while its frames are held", () => {
    let held = false
    const fx = new FxStore({ previewHeld: () => held })
    fx.apply({ channel: 'fx', zones: [zone('living', 'preview', 0.2)] })
    held = true
    fx.apply({ channel: 'fx', zones: [zone('office'), zone('living', 'preview', 0.4)] })
    expect(fx.get('living', 'preview')).toEqual(zone('living', 'preview', 0.2))
    expect(fx.get('office')).toEqual(zone('office'))
    held = false
    fx.apply({ channel: 'fx', zones: [zone('living', 'preview', 0.4)] })
    expect(fx.get('living', 'preview')).toEqual(zone('living', 'preview', 0.4))
  })

  it('moves its version with every picture, and wakes whoever waits once', () => {
    const fx = new FxStore()
    const wake = vi.fn()
    fx.onNextChange(wake)
    fx.apply({ channel: 'fx', zones: [] })
    fx.apply({ channel: 'fx', zones: [zone('living')] })
    expect(fx.version).toBe(2)
    expect(wake).toHaveBeenCalledOnce()
    const stop = fx.onNextChange(wake)
    stop()
    fx.clear()
    expect(wake).toHaveBeenCalledOnce()
  })

  it('clears, moving its version only when it held something', () => {
    const fx = new FxStore()
    fx.clear()
    expect(fx.version).toBe(0)
    fx.apply({ channel: 'fx', zones: [zone('living')] })
    fx.clear()
    expect(fx.empty).toBe(true)
    expect(fx.version).toBe(2)
  })
})
```

- [ ] **Step 3: Run them to see them fail**

Run: `(cd web && npx vitest run src/api/ws-messages.test.ts src/api/fx.test.ts)`
Expected: FAIL. `fx.test.ts` fails to load (`Failed to resolve import "./fx"`), and `ws-messages.test.ts`'s fx tests fail, the first with `AssertionError: expected { channel: 'fx' } to be null`.

- [ ] **Step 4: Write the code**

```diff
diff --git a/web/src/api/ws-messages.ts b/web/src/api/ws-messages.ts
index 06205dc..9b34dd4 100644
--- a/web/src/api/ws-messages.ts
+++ b/web/src/api/ws-messages.ts
@@ -2,7 +2,7 @@
 // decks and stats are snake_case on the wire, as today; the pushed snapshots use the contract's
 // camelCase (decision 5).
 import type {
-  AttentionItem, Deck, FrameStream, Id, Inputs, LightUpdate, Overlay, RunningZone, SignalValue, TempoSource,
+  AttentionItem, Deck, FrameStream, Id, Inputs, LightUpdate, Overlay, RunningZone, SignalValue, TempoSource, Vec3,
 } from './contract'
 
 /** Today's beat (engine M1): no source, bar or server time. */
@@ -64,8 +64,37 @@ export interface AckMessage { channel: 'ack'; id: number | null; action: string;
 export interface ErrorMessage { channel: 'error'; id?: number | null; detail: string }
 export interface InputsMessage { channel: 'inputs'; inputs: Inputs }
 export interface SignalsMessage { channel: 'signals'; values: Record<string, SignalValue> }
-/** "Effects in space" (§12.4, F10). Typed so it's recognised; nothing reads it before F10. */
-export interface FxMessage { channel: 'fx' }
+/**
+ * One particle of §12.4's fx block: where it is, its colour and its radius. Places and lengths are metres in
+ * the home map's frame (z up); colours linear 0–1, after the zone's brightness.
+ */
+export type FxParticle = [x: number, y: number, z: number, r: number, g: number, b: number, size: number]
+/** A ring of light: a `sphere` is a shell, a `circle` lies level (its axis is z). `width` is how thick it's drawn. */
+export interface FxRing {
+  center: Vec3
+  radius: number
+  width: number
+  rgb: Vec3
+  form: 'sphere' | 'circle'
+}
+/** A plane of light: infinite, or with a `ray` (a direction in the plane) the half on that side of `point`. */
+export interface FxPlane {
+  point: Vec3
+  normal: Vec3
+  width: number
+  rgb: Vec3
+  ray?: Vec3
+}
+/** What one zone draws in space, with the frames of one stream. A zone with nothing to draw is left out. */
+export interface ZoneFx {
+  zoneId: Id
+  stream: FrameStream
+  particles?: FxParticle[]
+  rings?: FxRing[]
+  planes?: FxPlane[]
+}
+/** "Effects in space" (§7.4, §12.4): the whole picture, which each message replaces. */
+export interface FxMessage { channel: 'fx'; zones: ZoneFx[] }
 export type ServerMessage =
   | BeatMessage | DecksMessage | RunningMessage | LightsMessage | AttentionMessage | TransportMessage
   | StatsMessage | StatusMessage | AckMessage | ErrorMessage | InputsMessage | SignalsMessage | FxMessage
@@ -100,6 +129,61 @@ const PAYLOADS: Partial<Record<string, [field: string, kind: keyof typeof IS]>>
   transport: ['state', 'string'],
 }
 
+const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)
+const isVec3 = (value: unknown): value is Vec3 => Array.isArray(value) && value.length === 3 && value.every(finite)
+const nonZero = (v: Vec3) => v[0] !== 0 || v[1] !== 0 || v[2] !== 0
+const isRecord = (value: unknown): value is Record<string, unknown> => IS.object(value)
+const isStream = (value: unknown): value is FrameStream => value === 'live' || value === 'preview'
+
+/**
+ * A particle: seven finite numbers, its size above 0. A longer one is a later optional field (§12.4's
+ * "Extending it"), read as its first seven.
+ */
+function isParticle(value: unknown): value is FxParticle {
+  if (!Array.isArray(value) || value.length < 7) return false
+  for (let i = 0; i < 7; i++) if (!finite(value[i])) return false
+  return value[6] > 0
+}
+
+function isRing(value: unknown): value is FxRing {
+  if (!isRecord(value)) return false
+  const { center, radius, width, rgb, form } = value
+  return isVec3(center) && finite(radius) && radius >= 0 && finite(width) && width > 0 && isVec3(rgb) && (form === 'sphere' || form === 'circle')
+}
+
+/** A plane: a ray, when it has one, is a direction (not zero), or the plane isn't drawn whole by mistake. */
+function isPlane(value: unknown): value is FxPlane {
+  if (!isRecord(value)) return false
+  const { point, normal, width, rgb, ray } = value
+  return (
+    isVec3(point) && isVec3(normal) && nonZero(normal) && finite(width) && width > 0 && isVec3(rgb) && (ray === undefined || (isVec3(ray) && nonZero(ray)))
+  )
+}
+
+/** The items of `list` that `is` takes: none for a list that isn't one. */
+const itemsOf = <T>(list: unknown, is: (item: unknown) => item is T): T[] | undefined => (Array.isArray(list) ? list.filter(is) : undefined)
+
+/**
+ * §12.4's fx block, checked as the other messages are, item by item: a zone or an item that isn't well formed is
+ * dropped, not the message, and a key the client doesn't know is ignored. Null without its zones.
+ */
+function readFx(record: Record<string, unknown>): FxMessage | null {
+  if (!IS.list(record.zones)) return null
+  const zones: ZoneFx[] = []
+  for (const zone of record.zones as unknown[]) {
+    if (!isRecord(zone) || typeof zone.zoneId !== 'string' || !isStream(zone.stream)) continue
+    const read: ZoneFx = { zoneId: zone.zoneId, stream: zone.stream }
+    const particles = itemsOf(zone.particles, isParticle)
+    const rings = itemsOf(zone.rings, isRing)
+    const planes = itemsOf(zone.planes, isPlane)
+    if (particles !== undefined) read.particles = particles
+    if (rings !== undefined) read.rings = rings
+    if (planes !== undefined) read.planes = planes
+    zones.push(read)
+  }
+  return { channel: 'fx', zones }
+}
+
 /** A server message, or null for text that isn't one (bad JSON, no channel, a message missing its payload). */
 export function parseMessage(text: string): ServerMessage | null {
   let value: unknown
@@ -111,6 +195,7 @@ export function parseMessage(text: string): ServerMessage | null {
   if (typeof value !== 'object' || value === null || Array.isArray(value)) return null
   const record = value as Record<string, unknown>
   if (typeof record.channel !== 'string') return null
+  if (record.channel === 'fx') return readFx(record)
   const payload = PAYLOADS[record.channel]
   if (payload !== undefined && !IS[payload[1]](record[payload[0]])) return null
   if (record.channel === 'stats' && record.lights !== undefined && !IS.list(record.lights)) return null
```

Create `web/src/api/fx.ts`:

```ts
// "Effects in space" (§7.4, §12.4): what each zone draws in the room, beside its lights. Each fx message is
// the whole picture, so the store keeps the latest one, by zone, for each stream; it never grows past one
// message. React never watches it: the stage draws it on its own cadence (cadence.ts), and `version` moves
// with every picture stored, as the frame store's does with every frame, so the stage knows to draw.
import type { FrameStream, Id } from './contract'
import type { FxMessage, ZoneFx } from './ws-messages'

export interface FxStoreOptions {
  /**
   * Whether the preview stream's frames are held (FrameStore.previewHeld): while the server may be playing a
   * look that was chosen over, its fx are held as its frames are, so the stage shows one look on the zone.
   */
  previewHeld?: () => boolean
}

export class FxStore {
  readonly live = new Map<Id, ZoneFx>()
  readonly preview = new Map<Id, ZoneFx>()
  /** Moves with every picture stored or cleared: redraw when it has moved. */
  version = 0
  private readonly waiting = new Set<() => void>()
  private readonly previewHeld: () => boolean

  constructor({ previewHeld = () => false }: FxStoreOptions = {}) {
    this.previewHeld = previewHeld
  }

  get(zoneId: Id, stream: FrameStream = 'live'): ZoneFx | undefined {
    return (stream === 'live' ? this.live : this.preview).get(zoneId)
  }

  /** Whether there's nothing to draw. */
  get empty(): boolean {
    return this.live.size === 0 && this.preview.size === 0
  }

  /** The message's picture replaces the last one; a zone it leaves out has nothing to draw. Of a zone sent twice, the last wins. */
  apply(message: FxMessage): void {
    const held = this.previewHeld()
    this.live.clear()
    if (!held) this.preview.clear()
    for (const zone of message.zones) {
      if (zone.stream === 'live') this.live.set(zone.zoneId, zone)
      else if (!held) this.preview.set(zone.zoneId, zone)
    }
    this.bump()
  }

  /** Nothing to draw: the link dropped, or the stage stopped asking. */
  clear(): void {
    if (this.empty) return
    this.live.clear()
    this.preview.clear()
    this.bump()
  }

  /** Calls `wake` once, when the version next moves; returns what stops it waiting. */
  onNextChange(wake: () => void): () => void {
    this.waiting.add(wake)
    return () => void this.waiting.delete(wake)
  }

  private bump(): void {
    this.version += 1
    if (this.waiting.size === 0) return
    const woken = [...this.waiting]
    this.waiting.clear()
    for (const wake of woken) wake()
  }
}
```

- [ ] **Step 5: Run them to see them pass**

Run: `(cd web && npx vitest run src/api/ws-messages.test.ts src/api/fx.test.ts)`
Expected: `Test Files  2 passed (2)`, `Tests  41 passed (41)`.

- [ ] **Step 6: The gate**

```bash
(cd web && npm test 2>&1 | grep -E 'Test Files|Tests ' && npm run lint && npx tsc -b && echo "tsc ok")
```

Expected: `Test Files  103 passed (103)`, `Tests  1061 passed (1061)`, lint clean, "tsc ok".

- [ ] **Step 7: Commit**

```bash
git add web/src/api/ws-messages.ts web/src/api/ws-messages.test.ts web/src/api/fx.ts web/src/api/fx.test.ts
git commit -m "feat(web): read the fx stream's pictures into a store"
```

---

### Task 2: Ask for the `fx` channel while the stage wants it

The server sends `fx` only to a session that asked (§12.4). The client asks while the stage wants it, again at every link-up, and forgets the picture when it stops asking or the link drops (rulings 7 and 9).

**Files:**
- Modify: `web/src/api/live-client.ts`, `web/src/api/live.ts`
- Create: `web/src/api/use-fx.ts`
- Test: `web/src/api/live-client.test.ts`, `web/src/api/live.test.ts`

**Interfaces:**
- Consumes: Task 1's `FxStore` and `FxMessage`; `Command`'s `subscribe_fx`.
- Produces:
  - `LiveClientOptions.fx?: FxStore`; `LiveClient.subscribeFx(on: boolean)`.
  - `live.ts`: `export const fx: FxStore`, held with the preview's frames; `wantFx(): () => void`; `resetDataLayer()` lets every want go and clears `fx`.
  - `use-fx.ts`: `useFxStream(on: boolean): void`.

- [ ] **Step 1: Read the spec and the code**

Read §12.4's `subscribe_fx` and the payload's fourth bullet ("only to a session that sent …"). Then read `web/src/api/live-client.ts` (`subscribe()`, `receiveText()`, `drop()`, `subscribeSignals()`) and `web/src/api/live.ts`. Task 2 draws nothing.

- [ ] **Step 2: Write the failing tests**

```diff
diff --git a/web/src/api/live-client.test.ts b/web/src/api/live-client.test.ts
index acdc5b7..ee8d628 100644
--- a/web/src/api/live-client.test.ts
+++ b/web/src/api/live-client.test.ts
@@ -3,12 +3,14 @@ import { fakeSockets, type FakeSocket } from '@/test/fake-socket'
 import { HERO_NOW } from '@/test/live'
 import { BeatClock } from './beat'
 import { FrameStore, encodeFrame } from './frames'
+import { FxStore } from './fx'
 import { LiveClient, backoffMs, liveSocketUrl, measuredFps } from './live-client'
 import { createLiveStore, type LiveStore } from './live-store'
 
 let store: LiveStore
 let frames: FrameStore
 let beatClock: BeatClock
+let fx: FxStore
 let sockets: FakeSocket[]
 let client: LiveClient
 const onResync = vi.fn()
@@ -22,6 +24,7 @@ beforeEach(() => {
   store = createLiveStore()
   frames = new FrameStore()
   beatClock = new BeatClock()
+  fx = new FxStore()
   const fake = fakeSockets()
   sockets = fake.sockets
   client = new LiveClient({
@@ -29,6 +32,7 @@ beforeEach(() => {
     store,
     frames,
     beatClock,
+    fx,
     openSocket: fake.open,
     onResync,
     onLive,
@@ -389,6 +393,77 @@ describe('LiveClient', () => {
     expect(client.tap(1)).toBeNull()
   })
 
+  // F10 decision 2: the stage asks for the fx channel while it draws effects; a reconnect asks again.
+  describe('effects in space', () => {
+    const picture = { channel: 'fx', zones: [{ zoneId: 'living', stream: 'live', particles: [[1, 2, 1, 1, 1, 1, 0.2]] }] }
+    const fxCommands = (socket = latest()) => socket.sent.filter((command) => command.action === 'subscribe_fx')
+
+    it("doesn't ask for the fx channel until the stage does", () => {
+      client.start()
+      welcome()
+      expect(fxCommands()).toEqual([])
+    })
+
+    it('asks for it when the stage does and lets go when it stops, once each', () => {
+      client.start()
+      welcome()
+      client.subscribeFx(true)
+      client.subscribeFx(true)
+      client.subscribeFx(false)
+      expect(fxCommands()).toEqual([expect.objectContaining({ on: true }), expect.objectContaining({ on: false })])
+    })
+
+    // Review focus 1: no duplicate subscriptions (§14 Resilience).
+    it('asks again at every link-up while it wants the channel, once each', () => {
+      client.subscribeFx(true)
+      client.start()
+      welcome()
+      expect(fxCommands()).toEqual([expect.objectContaining({ action: 'subscribe_fx', on: true })])
+      latest().drop()
+      vi.advanceTimersByTime(backoffMs(1))
+      welcome()
+      expect(fxCommands()).toEqual([expect.objectContaining({ on: true })])
+      client.subscribeFx(false)
+      latest().drop()
+      vi.advanceTimersByTime(backoffMs(2))
+      welcome()
+      expect(fxCommands()).toEqual([])
+    })
+
+    it('stores each picture while it wants them, and none after', () => {
+      client.subscribeFx(true)
+      client.start()
+      welcome()
+      latest().say(picture)
+      expect([...fx.live.keys()]).toEqual(['living'])
+      client.subscribeFx(false)
+      expect(fx.empty).toBe(true)
+      // One the server sent before it heard the off.
+      latest().say(picture)
+      expect(fx.empty).toBe(true)
+      expect(store.getState()).not.toHaveProperty('fx')
+    })
+
+    // Review focus 2: the picture is of a moment before the drop, and the stage is frozen.
+    it('forgets the picture when the link drops', () => {
+      client.subscribeFx(true)
+      client.start()
+      welcome()
+      latest().say(picture)
+      latest().drop()
+      expect(fx.empty).toBe(true)
+    })
+
+    it('ignores a malformed picture, and counts it', () => {
+      client.subscribeFx(true)
+      client.start()
+      welcome()
+      latest().say({ channel: 'fx', zones: 'living' })
+      expect(client.malformedJson).toBe(1)
+      expect(fx.empty).toBe(true)
+    })
+  })
+
   it('stops for good: it closes the socket and never retries', () => {
     client.start()
     welcome()
diff --git a/web/src/api/live.test.ts b/web/src/api/live.test.ts
index 8fff602..1a0c3ee 100644
--- a/web/src/api/live.test.ts
+++ b/web/src/api/live.test.ts
@@ -1,7 +1,7 @@
 import { beforeEach, describe, expect, it, vi } from 'vitest'
 import { fakeSockets } from '@/test/fake-socket'
 import { HERO_NOW, startMockDataLayer } from '@/test/live'
-import { frames, liveClient, startDataLayer } from './live'
+import { frames, liveClient, resetDataLayer, startDataLayer, wantFx } from './live'
 import { liveStore } from './live-store'
 import { buildScenario } from './mocks/scenarios'
 import { queries, queryClient } from './queries'
@@ -40,3 +40,43 @@ describe('startDataLayer', () => {
     expect(sockets[0].closed).toBe(true)
   })
 })
+
+// F10 decision 2: the fx channel is on while any stage wants it.
+describe('wantFx', () => {
+  const fxCommands = (socket: { sent: { action: string }[] }) => socket.sent.filter((command) => command.action === 'subscribe_fx')
+
+  it('asks for the fx channel while anything wants it, and lets go once nothing does', () => {
+    const { sockets, open } = fakeSockets()
+    startDataLayer({ openSocket: open, url: 'ws://test/ws' })
+    sockets[0].open()
+    const first = wantFx()
+    const second = wantFx()
+    first()
+    first()
+    expect(fxCommands(sockets[0])).toEqual([expect.objectContaining({ on: true })])
+    second()
+    expect(fxCommands(sockets[0])).toEqual([expect.objectContaining({ on: true }), expect.objectContaining({ on: false })])
+  })
+
+  it('carries a want over to a client started after it', () => {
+    const release = wantFx()
+    const { sockets, open } = fakeSockets()
+    startDataLayer({ openSocket: open, url: 'ws://test/ws' })
+    sockets[0].open()
+    expect(fxCommands(sockets[0])).toEqual([expect.objectContaining({ on: true })])
+    release()
+  })
+
+  // Every test ends with a reset: a stage unmounted after it lets go of nothing a later one wants.
+  it("lets a want from before a reset go without touching a later one's", () => {
+    const stale = wantFx()
+    resetDataLayer()
+    const { sockets, open } = fakeSockets()
+    startDataLayer({ openSocket: open, url: 'ws://test/ws' })
+    sockets[0].open()
+    const release = wantFx()
+    stale()
+    expect(fxCommands(sockets[0])).toEqual([expect.objectContaining({ on: true })])
+    release()
+  })
+})
```

The reconnect test steps the backoff twice, 1 s then 2 s: the client's attempt count goes back to 0 only after a link has stayed up a while, so the second drop waits longer.

- [ ] **Step 3: Run them to see them fail**

Run: `(cd web && npx vitest run src/api/live-client.test.ts src/api/live.test.ts)`
Expected: FAIL: `Tests  8 failed | 43 passed (51)`, with `TypeError: client.subscribeFx is not a function` and `TypeError: wantFx is not a function`.

- [ ] **Step 4: Write the code**

```diff
diff --git a/web/src/api/live-client.ts b/web/src/api/live-client.ts
index 3f96d6e..49d1ea4 100644
--- a/web/src/api/live-client.ts
+++ b/web/src/api/live-client.ts
@@ -1,10 +1,12 @@
 // The one link to the server (spec §12.4, §9.4). It subscribes once per connection, stores what the
-// server says (the live store) and the frames it streams (the FrameStore), and feeds the beat clock.
+// server says (the live store), the frames it streams (the FrameStore) and, while the stage asks for them,
+// its effects in space (the FxStore), and feeds the beat clock.
 // When the link drops it says so at once and retries after 1, 2, 4 and 8 s, then every 10 s. On
 // the way back it resyncs: frame seqs, the beat clock, and REST data through onResync.
 import { ClockOffset, clientNow, normaliseBeat, type BeatClock } from './beat'
 import type { FrameStream } from './contract'
 import { decodeFrame, type FrameStore, type FrameVersion } from './frames'
+import type { FxStore } from './fx'
 import { applyMessage, type LiveStore } from './live-store'
 import { ApiError } from './rest'
 import { parseMessage, type Command } from './ws-messages'
@@ -55,6 +57,8 @@ export interface LiveClientOptions {
   store: LiveStore
   frames: FrameStore
   beatClock: BeatClock
+  /** Where the `fx` channel's pictures go, while subscribeFx() has them on. */
+  fx?: FxStore
   openSocket?: OpenSocket
   /** After a reconnect: fetch again what REST loaded (resync() in queries.ts). */
   onResync?: () => void
@@ -74,6 +78,7 @@ export class LiveClient {
   private readonly store: LiveStore
   private readonly frames: FrameStore
   private readonly beatClock: BeatClock
+  private readonly fx: FxStore | null
   private readonly openSocket: OpenSocket
   private readonly onResync: () => void
   private readonly onLive: () => void
@@ -97,6 +102,8 @@ export class LiveClient {
   private nextId = 1
   private streams: FrameStream[] = ['live']
   private signals: string[] | null = null
+  /** Whether the stage wants the `fx` channel (F10): asked for at every link-up while it does. */
+  private fxOn = false
   private retryTimer: ReturnType<typeof setTimeout> | null = null
   private tickTimer: ReturnType<typeof setInterval> | null = null
   /** Taps sent and not yet answered, by command id: the server's ack settles one, its error refuses it. */
@@ -107,6 +114,7 @@ export class LiveClient {
     this.store = options.store
     this.frames = options.frames
     this.beatClock = options.beatClock
+    this.fx = options.fx ?? null
     this.openSocket = options.openSocket ?? openWebSocket
     this.onResync = options.onResync ?? (() => {})
     this.onLive = options.onLive ?? (() => {})
@@ -153,6 +161,18 @@ export class LiveClient {
     if (this.opened) this.sendSignals(names)
   }
 
+  /**
+   * "Effects in space" (§7.4): the `fx` channel on or off (§12.4's `subscribe_fx`), sent again after a
+   * reconnect while on. The server sends nothing until asked, so the first link-up asks only while on. Off
+   * clears the store: the stage draws nothing it was sent before, and a picture still on its way is ignored.
+   */
+  subscribeFx(on: boolean): void {
+    if (on === this.fxOn) return
+    this.fxOn = on
+    if (!on) this.fx?.clear()
+    if (this.opened) this.send({ action: 'subscribe_fx', on })
+  }
+
   /**
    * §6.2's TAP over the socket (§12.4), timed by the client's clock in epoch seconds. Null while the link
    * isn't open, so the caller uses REST. The promise settles on the server's answer; a drop before it
@@ -188,6 +208,7 @@ export class LiveClient {
     this.send({ action: 'subscribe_beat', fps: BEAT_FPS })
     this.sendFrames()
     if (this.signals !== null) this.sendSignals(this.signals)
+    if (this.fxOn) this.send({ action: 'subscribe_fx', on: true })
   }
 
   private sendFrames(): void {
@@ -263,6 +284,10 @@ export class LiveClient {
       else tap.reject(new Error(message.detail))
       return
     }
+    if (message.channel === 'fx') {
+      if (this.fxOn) this.fx?.apply(message)
+      return
+    }
     if (message.channel === 'beat') {
       // The store and the clock share the one Beat.
       const beat = normaliseBeat(message, now)
@@ -278,6 +303,8 @@ export class LiveClient {
     if (this.socket !== socket) return // an old socket's late close
     this.detach()
     socket.close()
+    // The server forgets the subscription with the link, and its picture is of a moment that's gone.
+    this.fx?.clear()
     if (this.tickTimer === null) return
     this.attempt += 1
     const wasLive = this.store.getState().connection.status === 'live'
diff --git a/web/src/api/live.ts b/web/src/api/live.ts
index a0f894a..8e62d67 100644
--- a/web/src/api/live.ts
+++ b/web/src/api/live.ts
@@ -1,8 +1,9 @@
-// The app's one data layer: a frame store, a beat clock, and the live client that fills them and
-// the live store. main.tsx starts it once; F3's "Try now" and TAP (actions.ts), F4's preview and F6/F8's
-// signal subscriptions reach the client through liveClient().
+// The app's one data layer: a frame store, an fx store, a beat clock, and the live client that fills them
+// and the live store. main.tsx starts it once; F3's "Try now" and TAP (actions.ts), F4's preview, F10's
+// effects in space (wantFx()) and F6/F8's signal subscriptions reach the client through liveClient().
 import { BeatClock } from './beat'
 import { FrameStore } from './frames'
+import { FxStore } from './fx'
 import { LiveClient, liveSocketUrl, type OpenSocket } from './live-client'
 import { liveStore, resetLiveStore } from './live-store'
 import { PreviewSession } from './preview'
@@ -10,9 +11,14 @@ import { queryClient, refetchOnNews, resync } from './queries'
 
 export const frames = new FrameStore()
 export const beatClock = new BeatClock()
+/** "Effects in space" (F10): held with the preview's frames, so the stage shows one look on the composer's zone. */
+export const fx = new FxStore({ previewHeld: () => frames.previewHeld })
 
 let client: LiveClient | null = null
 let stopRefetching: (() => void) | null = null
+/** How many stages want the fx channel now (wantFx()), counted since the last reset. */
+let fxWants = 0
+let fxGeneration = 0
 
 /** The composer's preview (F4): one at a time, on the stage only. */
 export const previewSession = new PreviewSession({ frames, client: () => client })
@@ -30,15 +36,35 @@ export function startDataLayer(options: { openSocket?: OpenSocket; url?: string
     store: liveStore,
     frames,
     beatClock,
+    fx,
     openSocket: options.openSocket,
     onResync: () => void resync(queryClient),
     // The server forgets a preview with the link, and a deep link can open the composer before the link is up.
     onLive: () => previewSession.resume(),
   })
+  client.subscribeFx(fxWants > 0)
   client.start()
   return client
 }
 
+/**
+ * The stage wants its effects in space (§7.4): the `fx` channel is on while anything wants it, and off once
+ * nothing does. Returns what lets go, once; letting go twice does nothing.
+ */
+export function wantFx(): () => void {
+  fxWants += 1
+  client?.subscribeFx(true)
+  const generation = fxGeneration
+  let held = true
+  return () => {
+    // A want from before a reset was let go by it.
+    if (!held || generation !== fxGeneration) return
+    held = false
+    fxWants -= 1
+    if (fxWants === 0) client?.subscribeFx(false)
+  }
+}
+
 export function liveClient(): LiveClient | null {
   return client
 }
@@ -50,8 +76,11 @@ export function resetDataLayer(): void {
   previewSession.reset()
   stopRefetching?.()
   stopRefetching = null
+  fxWants = 0
+  fxGeneration += 1
   resetLiveStore()
   frames.clear()
+  fx.clear()
   beatClock.reset()
   queryClient.clear()
 }
```

Create `web/src/api/use-fx.ts`:

```ts
// The stage's part of "Effects in space" (§7.4): while `on`, the fx channel is asked for (wantFx()), and let
// go when it's off or the stage goes. Components never touch the socket (§12).
import { useEffect } from 'react'
import { wantFx } from './live'

export function useFxStream(on: boolean): void {
  useEffect(() => (on ? wantFx() : undefined), [on])
}
```

- [ ] **Step 5: Run them to see them pass**

Run: `(cd web && npx vitest run src/api/live-client.test.ts src/api/live.test.ts)`
Expected: `Test Files  2 passed (2)`, `Tests  51 passed (51)`.

- [ ] **Step 6: The gate**

```bash
(cd web && npm test 2>&1 | grep -E 'Test Files|Tests ' && npm run lint && npx tsc -b && echo "tsc ok")
```

Expected: `Test Files  103 passed (103)`, `Tests  1070 passed (1070)`, lint clean, "tsc ok".

- [ ] **Step 7: Commit**

```bash
git add web/src/api/live-client.ts web/src/api/live-client.test.ts web/src/api/live.ts web/src/api/live.test.ts web/src/api/use-fx.ts
git commit -m "feat(web): ask for the fx channel while the stage wants it"
```

---

### Task 3: The mocks draw their looks in space

§12.5's mocks play every scenario with no engine, so they send `fx` as engine M8 will (ruling 17): what each running zone's look, and the preview's, would draw, round its lights.

**Files:**
- Create: `web/src/api/mocks/mock-fx.ts`
- Modify: `web/src/api/mocks/mock-server.ts`
- Test: `web/src/api/mocks/mock-fx.test.ts` (create), `web/src/api/mocks/mock-server.test.ts`, `web/src/api/live.test.ts`

**Interfaces:**
- Consumes: `motifFor()` (the frame generator's hue and spread), `LightShape` and `Look` from `contract.ts`, Task 1's `ZoneFx`, `FxParticle`, `FxRing` and `FxPlane`.
- Produces:
  - `mock-fx.ts`: `FxZone {zoneId, stream, look, shapes, brightness, frozen}`, `drawsInSpace(look)`, and `zoneFx(zone, t, beats): ZoneFx | null`.
  - `MockServer`: answers `subscribe_fx {on}` (the session's `fx` and `lastFx`), sends the fx channel from its tick every `FX_MS`, and keeps the preview's `zoneId` and `look`.

- [ ] **Step 1: Read the spec and the code**

Read §12.4's "What draws what", §12.5, and the M5 and M3 looks' descriptions in `web/src/api/mocks/looks.json` (read the ids there, not the names). Then read `web/src/api/mocks/mock-server.ts`: `tick()`, `command()`, `plan()`, the preview's `POST`, `PUT` and `DELETE`, and `STREAMED`; and `motifFor()` in `frame-generator.ts`.

- [ ] **Step 2: Write the failing tests**

Create `web/src/api/mocks/mock-fx.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import type { LightShape } from '../contract'
import { parseMessage } from '../ws-messages'
import { lookFixtures } from './fixtures'
import { drawsInSpace, zoneFx, type FxZone } from './mock-fx'

const SHAPES: LightShape[] = [
  { kind: 'point', position: [1, 1, 1] },
  { kind: 'cylinder', base: [3, 2, 0], height: 1.5, radius: 0.1 },
]
const zone = (lookId: string, extra: Partial<FxZone> = {}): FxZone => ({
  zoneId: 'living',
  stream: 'live',
  look: lookFixtures.find((look) => look.id === lookId)!,
  shapes: SHAPES,
  brightness: 1,
  frozen: false,
  ...extra,
})

// §12.4's "What draws what (M8's first slice)".
const PARTICLE_LOOKS = ['fireflies', 'embers', 'rain', 'snow', 'spotlights', 'bursts', 'fountain', 'flock', 'vortex', 'comets', 'ball']

describe('zoneFx', () => {
  it.each(PARTICLE_LOOKS)('draws particles for %s', (lookId) => {
    const fx = zoneFx(zone(lookId), 3, 6)!
    expect(fx.particles!.length).toBeGreaterThan(0)
    expect(fx.rings).toBeUndefined()
    expect(fx.planes).toBeUndefined()
  })

  it('draws Shockwave as a shell and a beam with a ray, Speaker waves as a shell, Ripples as level circles and Scanner as a level plane', () => {
    const shockwave = zoneFx(zone('shockwave'), 3, 6.5)!
    expect(shockwave.rings!.map((ring) => ring.form)).toEqual(['sphere'])
    expect(shockwave.planes![0].ray).toBeDefined()
    expect(zoneFx(zone('speakers'), 3, 6.5)!.rings!.map((ring) => ring.form)).toEqual(['sphere'])
    const ripples = zoneFx(zone('ripples'), 3, 6.5)!
    expect(ripples.rings!.map((ring) => [ring.form, ring.center[2]])).toEqual([['circle', 0], ['circle', 0]])
    const scanner = zoneFx(zone('scanner'), 3, 6.5)!.planes!
    expect(scanner.map((plane) => [plane.normal, plane.ray])).toEqual([[[0, 0, 1], undefined]])
    // Between the zone's lowest and highest points.
    expect(scanner[0].point[2]).toBeGreaterThanOrEqual(0)
    expect(scanner[0].point[2]).toBeLessThanOrEqual(1.5)
  })

  it('draws nothing for a look with nothing in space, a zone with no placed lights or one at no brightness', () => {
    expect(drawsInSpace({ id: 'homesunset' })).toBe(false)
    expect(zoneFx(zone('homesunset'), 3, 6)).toBeNull()
    expect(zoneFx(zone('fireflies', { shapes: [] }), 3, 6)).toBeNull()
    expect(zoneFx(zone('fireflies', { brightness: 0 }), 3, 6)).toBeNull()
  })

  it('moves with time and the beat, holds a crashed zone, and scales its colours by the brightness', () => {
    expect(zoneFx(zone('fireflies'), 3, 6)).not.toEqual(zoneFx(zone('fireflies'), 3.5, 6))
    expect(zoneFx(zone('scanner'), 3, 6)).not.toEqual(zoneFx(zone('scanner'), 3, 6.5))
    expect(zoneFx(zone('comets', { frozen: true }), 3, 6)).toEqual(zoneFx(zone('comets', { frozen: true }), 9, 13))
    const full = zoneFx(zone('scanner'), 3, 6)!.planes![0].rgb
    const half = zoneFx(zone('scanner', { brightness: 0.5 }), 3, 6)!.planes![0].rgb
    half.forEach((channel, i) => expect(channel).toBeCloseTo(full[i] / 2, 2))
  })

  // The mock speaks what the client reads: every picture survives parseMessage whole.
  it.each([...PARTICLE_LOOKS, 'shockwave', 'speakers', 'ripples', 'scanner'])('sends %s as the client reads it, rounded to 3 decimals', (lookId) => {
    const zones = [zoneFx(zone(lookId), 3.21, 7.3)!]
    const text = JSON.stringify({ channel: 'fx', zones })
    expect(parseMessage(text)).toEqual({ channel: 'fx', zones })
    for (const number of text.match(/-?\d+\.\d+/g) ?? []) expect(number.split('.')[1].length).toBeLessThanOrEqual(3)
  })
})
```

```diff
diff --git a/web/src/api/live.test.ts b/web/src/api/live.test.ts
index 1a0c3ee..f621247 100644
--- a/web/src/api/live.test.ts
+++ b/web/src/api/live.test.ts
@@ -1,7 +1,7 @@
 import { beforeEach, describe, expect, it, vi } from 'vitest'
 import { fakeSockets } from '@/test/fake-socket'
 import { HERO_NOW, startMockDataLayer } from '@/test/live'
-import { frames, liveClient, resetDataLayer, startDataLayer, wantFx } from './live'
+import { frames, fx, liveClient, resetDataLayer, startDataLayer, wantFx } from './live'
 import { liveStore } from './live-store'
 import { buildScenario } from './mocks/scenarios'
 import { queries, queryClient } from './queries'
@@ -79,4 +79,12 @@ describe('wantFx', () => {
     expect(fxCommands(sockets[0])).toEqual([expect.objectContaining({ on: true })])
     release()
   })
+
+  it("hears the mock hero's picture once asked", async () => {
+    const release = wantFx()
+    startMockDataLayer()
+    await vi.advanceTimersByTimeAsync(1100)
+    expect([...fx.live.keys()].sort()).toEqual(['living', 'office'])
+    release()
+  })
 })
diff --git a/web/src/api/mocks/mock-server.test.ts b/web/src/api/mocks/mock-server.test.ts
index bcab571..83823a5 100644
--- a/web/src/api/mocks/mock-server.test.ts
+++ b/web/src/api/mocks/mock-server.test.ts
@@ -5,7 +5,7 @@ import type { Deck, Home, Inputs, Light, Look, Placement, PreviewStarted, Recent
 import { FrameStore, decodeFrame } from '../frames'
 import { LiveClient } from '../live-client'
 import { createLiveStore } from '../live-store'
-import type { ClientCommand, RunningMessage } from '../ws-messages'
+import type { ClientCommand, FxMessage, RunningMessage } from '../ws-messages'
 import { inMemorySockets } from './in-memory-socket'
 import { RECENT_LIMIT, beatMessage, snapshotMessages, statsMessage, type MockServer } from './mock-server'
 import { COPIED_EFFECT, HOME_TOTALS } from './fixtures'
@@ -207,6 +207,80 @@ describe('a connection', () => {
   })
 })
 
+// F10: the mock draws in space, so "Effects in space" is built and tested with no engine.
+describe('the fx channel', () => {
+  const pictures = (socket: ReturnType<typeof connect>): FxMessage[] => socket.json().filter((message) => message.channel === 'fx')
+  const drawn = (picture: FxMessage | undefined) => picture?.zones.map((zone) => [zone.zoneId, zone.stream])
+
+  it("sends nothing until it's asked, then the hero's fireflies and comets, at most 30 a second", () => {
+    const socket = connect(startMockServer())
+    vi.advanceTimersByTime(500)
+    expect(pictures(socket)).toEqual([])
+    socket.send({ action: 'subscribe_fx', on: true })
+    expect(socket.json().at(-1)).toEqual({ channel: 'ack', id: 1, action: 'subscribe_fx' })
+    vi.advanceTimersByTime(1000)
+    const heard = pictures(socket)
+    expect(heard.length).toBeGreaterThan(20)
+    expect(heard.length).toBeLessThanOrEqual(31)
+    // The whole home's sunset draws nothing in space (§12.4: a zone with nothing to draw is left out).
+    expect(drawn(heard.at(-1))).toEqual([['living', 'live'], ['office', 'live']])
+    expect(heard.at(-1)!.zones.every((zone) => zone.particles!.length > 0)).toBe(true)
+  })
+
+  it('stops when asked to, and starts again with the picture as it is', () => {
+    const socket = connect(startMockServer({ still: true }))
+    socket.send({ action: 'subscribe_fx', on: true })
+    vi.advanceTimersByTime(200)
+    socket.send({ action: 'subscribe_fx', on: false })
+    socket.clear()
+    vi.advanceTimersByTime(500)
+    expect(pictures(socket)).toEqual([])
+    socket.send({ action: 'subscribe_fx', on: true })
+    vi.advanceTimersByTime(200)
+    expect(pictures(socket)).toHaveLength(1)
+  })
+
+  // §12.4: nothing while nothing changes. ?still holds the picture, so it goes out once.
+  it('sends a held picture once under ?still', () => {
+    const socket = connect(startMockServer({ still: true }))
+    socket.send({ action: 'subscribe_fx', on: true })
+    vi.advanceTimersByTime(1000)
+    expect(pictures(socket)).toHaveLength(1)
+  })
+
+  it("draws the preview's look on the preview stream while it's on, and nothing for it after", () => {
+    const server = startMockServer({ still: true })
+    const socket = connect(server)
+    socket.send({ action: 'subscribe_fx', on: true })
+    const { previewId } = server.handle('POST', '/api/preview', { zoneId: 'bedroom', lookId: 'scanner' }).body as PreviewStarted
+    vi.advanceTimersByTime(200)
+    const preview = pictures(socket).at(-1)!.zones.find((zone) => zone.stream === 'preview')!
+    expect(preview.zoneId).toBe('bedroom')
+    expect(preview.planes).toHaveLength(1)
+    server.handle('PUT', `/api/preview/${previewId}`, { look: { id: 'shockwave', category: 'tempo' } })
+    vi.advanceTimersByTime(200)
+    expect(pictures(socket).at(-1)!.zones.find((zone) => zone.stream === 'preview')!.rings).toHaveLength(1)
+    server.handle('DELETE', `/api/preview/${previewId}`)
+    vi.advanceTimersByTime(200)
+    expect(drawn(pictures(socket).at(-1))).toEqual([['living', 'live'], ['office', 'live']])
+  })
+
+  it("draws a started look's rings and planes, and nothing for a zone waiting for its input", () => {
+    const server = startMockServer({ still: true })
+    const socket = connect(server)
+    socket.send({ action: 'subscribe_fx', on: true })
+    server.handle('POST', '/api/zones/office/start', { lookId: 'shockwave' })
+    vi.advanceTimersByTime(200)
+    const office = pictures(socket).at(-1)!.zones.find((zone) => zone.zoneId === 'office')!
+    expect([office.rings?.length, office.planes?.length, office.particles]).toEqual([1, 1, undefined])
+    const waiting = connect(startMockServer({ scenario: 'waiting', still: true }))
+    waiting.send({ action: 'subscribe_fx', on: true })
+    vi.advanceTimersByTime(200)
+    const sleeping = buildScenario('waiting', HERO_NOW).running.filter((zone) => zone.state === 'waiting').map((zone) => zone.zoneId)
+    expect(pictures(waiting).at(-1)!.zones.map((zone) => zone.zoneId)).not.toEqual(expect.arrayContaining(sleeping))
+  })
+})
+
 describe('the REST API', () => {
   it('starts a look with take-over, and pushes running and lights', () => {
     const server = startMockServer()
```

- [ ] **Step 3: Run them to see them fail**

Run: `(cd web && npx vitest run src/api/mocks/mock-fx.test.ts src/api/mocks/mock-server.test.ts src/api/live.test.ts)`
Expected: FAIL: `mock-fx.test.ts` fails to load (`Failed to resolve import "./mock-fx"`), and `Tests  6 failed | 53 passed (59)`, the first `AssertionError: expected [] to deeply equal [ 'living', 'office' ]`.

- [ ] **Step 4: Write the code**

Create `web/src/api/mocks/mock-fx.ts`:

```ts
// What the mock's zones draw in space (§12.4's `fx` payload), so "Effects in space" can be built and tested
// with no engine. Like the frame generator's motifs, these only keep the stage alive: each look gets a
// simple moving picture of its kind (particles that wander or orbit, Shockwave's shell and beam, Speaker
// waves' fronts, Ripples' drops, Scanner's plane) round the box its lights' placements span. The hues are
// the frame generator's, and the sizes and speeds are picked here; they are no design value, and engine M8
// sends the real looks.
import type { Id, LightShape, Look, Vec3 } from '../contract'
import type { FxParticle, FxPlane, FxRing, ZoneFx } from '../ws-messages'
import { motifFor } from './frame-generator'

/** The kinds of picture the mock draws: one per look that draws in space (§12.4's "What draws what"). */
type FxKind = 'wander' | 'orbit' | 'shockwave' | 'speakers' | 'ripples' | 'scanner'

// M5's eleven particle looks, and M3's four tempo looks and Ripples that send rings and planes.
const KIND_OF: Partial<Record<Id, FxKind>> = {
  fireflies: 'wander',
  embers: 'wander',
  rain: 'wander',
  snow: 'wander',
  spotlights: 'wander',
  bursts: 'wander',
  fountain: 'wander',
  flock: 'wander',
  vortex: 'orbit',
  comets: 'orbit',
  ball: 'orbit',
  shockwave: 'shockwave',
  speakers: 'speakers',
  ripples: 'ripples',
  scanner: 'scanner',
}

/** How many particles a wandering look draws, and how many each orbiting head trails. */
const WANDERERS = 12
const TRAIL = 6
/** A particle's glow, metres: about Fireflies' default glow size. */
const WANDER_SIZE = 0.4
const ORBIT_SIZE = 0.3
/** How thick a shell, a ring or a plane is drawn, metres. */
const SHELL_WIDTH = 0.3
const PLANE_WIDTH = 0.15

/** One zone of the picture: the look it runs (or previews), on which lights, how bright, and whether it's held. */
export interface FxZone {
  zoneId: Id
  stream: ZoneFx['stream']
  look: Pick<Look, 'id' | 'category'>
  shapes: readonly LightShape[]
  brightness: number
  /** A crashed zone holds its picture, as it holds its last frame. */
  frozen: boolean
}

/** Whether a look draws anything in space. */
export const drawsInSpace = (look: Pick<Look, 'id'>): boolean => KIND_OF[look.id ?? ''] !== undefined

/** §12.4: numbers rounded to 3 decimals. */
const round3 = (value: number): number => Math.round(value * 1000) / 1000
const rounded = ([x, y, z]: Vec3): Vec3 => [round3(x), round3(y), round3(z)]

/** A hue at full saturation, as linear 0–1 floats times `level`. */
function hueRgb(hue: number, level: number): Vec3 {
  const h = (((hue % 360) + 360) % 360) / 60
  const x = 1 - Math.abs((h % 2) - 1)
  const [r, g, b]: Vec3 = h < 1 ? [1, x, 0] : h < 2 ? [x, 1, 0] : h < 3 ? [0, 1, x] : h < 4 ? [0, x, 1] : h < 5 ? [x, 0, 1] : [1, 0, x]
  const white = 0.15 // a little white, as the frame generator's 0.85 saturation
  const lift = (channel: number) => ((channel + white) / (1 + white)) * level
  return rounded([lift(r), lift(g), lift(b)])
}

/** The points a light's placement puts it at: enough to find the box its zone spans. */
function shapePoints(shape: LightShape): Vec3[] {
  switch (shape.kind) {
    case 'point':
      return [shape.position]
    case 'line':
    case 'bent-line':
      return shape.path
    case 'cylinder': {
      const [x, y, z] = shape.base
      return [shape.base, [x, y, z + shape.height]]
    }
    case 'grid':
      return [shape.center]
  }
}

/** The box a zone's lights span: its centre, its half-size across, and its lowest and highest points. */
function boxOf(shapes: readonly LightShape[]): { centre: Vec3; reach: number; low: number; high: number } | null {
  const points = shapes.flatMap(shapePoints)
  if (points.length === 0) return null
  const min: Vec3 = [Infinity, Infinity, Infinity]
  const max: Vec3 = [-Infinity, -Infinity, -Infinity]
  for (const point of points) {
    for (let axis = 0; axis < 3; axis++) {
      min[axis] = Math.min(min[axis], point[axis])
      max[axis] = Math.max(max[axis], point[axis])
    }
  }
  const centre: Vec3 = [(min[0] + max[0]) / 2, (min[1] + max[1]) / 2, (min[2] + max[2]) / 2]
  // At least a metre, so one bulb's picture still moves.
  const reach = Math.max(1, Math.hypot(max[0] - min[0], max[1] - min[1]) / 2)
  return { centre, reach, low: min[2], high: Math.max(max[2], min[2] + 0.5) }
}

/**
 * What one zone draws at `t` seconds and `beats` beats into the music, or null for nothing (§12.4: a zone
 * with nothing to draw is left out): a look that draws nothing in space, a zone with no placed lights, or
 * one at no brightness (a zone waiting for its input waits dark).
 */
export function zoneFx(zone: FxZone, t: number, beats: number): ZoneFx | null {
  const kind = KIND_OF[zone.look.id ?? '']
  const box = boxOf(zone.shapes)
  if (kind === undefined || box === null || zone.brightness <= 0) return null
  const at = zone.frozen ? 0 : t
  const beat = zone.frozen ? 0 : beats
  const { hue, spread } = motifFor(zone.look)
  const level = Math.min(1, zone.brightness)
  const [cx, cy, cz] = box.centre
  const out: ZoneFx = { zoneId: zone.zoneId, stream: zone.stream }
  switch (kind) {
    case 'wander': {
      const particles: FxParticle[] = []
      for (let i = 0; i < WANDERERS; i++) {
        const angle = at * 0.3 + i * 2.39
        const swing = box.reach * (0.4 + 0.6 * ((i * 0.618) % 1))
        const [r, g, b] = hueRgb(hue + (spread * i) / WANDERERS, level * (0.5 + 0.5 * Math.sin(at * 1.3 + i)) ** 2)
        const [x, y, z] = rounded([cx + swing * Math.cos(angle), cy + swing * Math.sin(angle * 1.1), cz + 0.4 * Math.sin(at * 0.7 + i)])
        particles.push([x, y, z, r, g, b, WANDER_SIZE])
      }
      out.particles = particles
      break
    }
    case 'orbit': {
      // Two heads opposite, once round a bar, each with a fading trail.
      const particles: FxParticle[] = []
      for (const head of [0, Math.PI]) {
        for (let k = 0; k <= TRAIL; k++) {
          const angle = (beat - k * 0.08) * (Math.PI / 2) + head
          const [r, g, b] = hueRgb(hue + (head === 0 ? 0 : spread), level * (1 - k / (TRAIL + 1)))
          const [x, y, z] = rounded([cx + box.reach * Math.cos(angle), cy + box.reach * Math.sin(angle), cz])
          particles.push([x, y, z, r, g, b, round3(ORBIT_SIZE * (1 - k / (TRAIL + 2)))])
        }
      }
      out.particles = particles
      break
    }
    case 'shockwave': {
      // A shell out from the centre each beat, and a beam turning once a bar.
      const turn = (beat / 4) * 2 * Math.PI
      out.rings = [{ center: rounded(box.centre), radius: round3((beat % 1) * box.reach * 1.5), width: SHELL_WIDTH, rgb: hueRgb(hue, level), form: 'sphere' } satisfies FxRing]
      out.planes = [
        {
          point: rounded(box.centre),
          normal: rounded([-Math.sin(turn), Math.cos(turn), 0]),
          width: PLANE_WIDTH,
          rgb: hueRgb(hue + spread, level),
          ray: rounded([Math.cos(turn), Math.sin(turn), 0]),
        } satisfies FxPlane,
      ]
      break
    }
    case 'speakers':
      // A kick front from the centre each beat.
      out.rings = [{ center: rounded(box.centre), radius: round3((beat % 1) * box.reach), width: SHELL_WIDTH, rgb: hueRgb(hue, level * (1 - (beat % 1))), form: 'sphere' }]
      break
    case 'ripples': {
      // Two drops on the floor, half a cycle apart.
      const rings: FxRing[] = []
      for (const offset of [0, 0.5]) {
        const grown = (at * 0.4 + offset) % 1
        const center = rounded([cx + (offset - 0.25) * box.reach, cy, 0])
        rings.push({ center, radius: round3(grown * box.reach), width: SHELL_WIDTH, rgb: hueRgb(hue + spread * offset, level * (1 - grown)), form: 'circle' })
      }
      out.rings = rings
      break
    }
    case 'scanner': {
      // A level plane up and down the zone's height once a bar.
      const height = box.low + (box.high - box.low) * (0.5 - 0.5 * Math.cos((beat / 4) * 2 * Math.PI))
      out.planes = [{ point: rounded([cx, cy, height]), normal: [0, 0, 1], width: PLANE_WIDTH, rgb: hueRgb(hue, level) }]
      break
    }
  }
  return out
}
```

```diff
diff --git a/web/src/api/mocks/mock-server.ts b/web/src/api/mocks/mock-server.ts
index bfe4f00..40d95f2 100644
--- a/web/src/api/mocks/mock-server.ts
+++ b/web/src/api/mocks/mock-server.ts
@@ -15,6 +15,7 @@ import { PATH_PARAM } from '../rest'
 import type { BeatV1, BeatV2, ServerMessage, StatsMessage } from '../ws-messages'
 import { coversOf, lightPlan, partId, runningZone } from './fixtures'
 import { motifFor, paint, type MotifSpec } from './frame-generator'
+import { zoneFx, type FxZone } from './mock-fx'
 import { asEngineM1, buildScenario, type ScenarioBeat, type ScenarioName, type ScenarioState } from './scenarios'
 
 const FRAME_MS = 1000 / 60
@@ -24,6 +25,8 @@ const STATS_MS = 1000
 const LIGHTS_MS = 5000
 const STATUS_MS = 10_000
 const SIGNALS_MS = 100
+/** §12.4: the fx channel sends at most 30 a second. */
+const FX_MS = 1000 / 30
 /** After a stall longer than this (a hidden tab), frames pick up from now rather than catch up. */
 const STALL_MS = 100
 /** How many looks "Start again" keeps, as engine M2 does (its Spec Ruling 19). */
@@ -71,6 +74,9 @@ interface Session extends MockSession {
   beatMs: number | null
   nextBeatAt: number
   signals: string[] | null
+  /** Whether it asked for the fx channel (`subscribe_fx {on: true}`), and the last picture it was sent, as sent. */
+  fx: boolean
+  lastFx: string | null
 }
 
 /** A light the mock streams, and the buffer it paints into. */
@@ -290,7 +296,7 @@ export class MockServer {
   private nextId = 0
   private timer: ReturnType<typeof setInterval> | null = null
   private live: Painted[] = []
-  private preview: { id: Id; lights: Painted[]; watchedAt: number } | null = null
+  private preview: { id: Id; zoneId: Id; look: Pick<Look, 'id' | 'category'>; lights: Painted[]; watchedAt: number } | null = null
   /** Each light's last seq, per stream: they run on across a replan, as the engine's do. */
   private readonly seqs: Record<FrameStream, Map<Id, number>> = { live: new Map(), preview: new Map() }
   /** When each light's placement was confirmed; the seed's confirmed lights have no time. */
@@ -303,6 +309,7 @@ export class MockServer {
   private nextLightsAt: number
   private nextStatusAt: number
   private nextSignalsAt: number
+  private nextFxAt: number
   private firstConnectAt: number | null = null
   private refusing = false
   /** The scenario's own beat: the source it plays, which drives the clock whenever nothing holds it. */
@@ -331,6 +338,7 @@ export class MockServer {
     this.nextLightsAt = this.startedAt + LIGHTS_MS
     this.nextStatusAt = this.startedAt + STATUS_MS
     this.nextSignalsAt = this.startedAt
+    this.nextFxAt = this.startedAt
     this.plan()
   }
 
@@ -357,6 +365,8 @@ export class MockServer {
       beatMs: null,
       nextBeatAt: 0,
       signals: null,
+      fx: false,
+      lastFx: null,
     }
     this.sessions.add(session)
     this.firstConnectAt ??= this.clock()
@@ -407,6 +417,8 @@ export class MockServer {
       return
     }
     if (this.protocol === 2 && action === 'subscribe_fx') {
+      session.fx = command.on === true
+      session.lastFx = null // a new subscription hears the picture as it is, unchanged or not
       this.ack(session, id, action)
       return
     }
@@ -472,6 +484,10 @@ export class MockServer {
       this.nextSignalsAt += SIGNALS_MS
       for (const session of this.sessions) if (session.signals !== null) this.sendJson(session, this.signals(now, session.signals))
     }
+    if (now >= this.nextFxAt) {
+      this.nextFxAt = Math.max(this.nextFxAt + FX_MS, now)
+      this.sendFx(now)
+    }
     if (now >= this.nextStatsAt) {
       this.nextStatsAt += STATS_MS
       this.broadcast(statsMessage(this.state, this.protocol))
@@ -603,6 +619,52 @@ export class MockServer {
     }
   }
 
+  // ── Effects in space ─────────────────────────────────────────────────────────────────────
+
+  /**
+   * The fx channel (§12.4): the whole picture, live and preview, to each session that asked for it, and
+   * only when it changed since the last one that session heard. Under ?still the picture holds, so it
+   * goes out once.
+   */
+  private sendFx(now: number): void {
+    let wanted = false
+    for (const session of this.sessions) wanted ||= session.fx
+    if (!wanted) return
+    const t = this.beatElapsedS(now)
+    const beats = position(this.state, t)
+    const zones = this.fxZones().flatMap((zone) => zoneFx(zone, t, beats) ?? [])
+    const text = JSON.stringify({ channel: 'fx', zones })
+    for (const session of this.sessions) {
+      if (!session.fx || session.lastFx === text) continue
+      session.lastFx = text
+      session.link.send(text)
+    }
+  }
+
+  /** What each running zone, and the preview, would draw: a zone waiting for its input waits dark, and a crashed one holds. */
+  private fxZones(): FxZone[] {
+    const shapes = (ids: readonly Id[]) =>
+      ids.flatMap((id) => {
+        const light = this.state.lights.find((candidate) => candidate.id === id)
+        return light?.shape != null && STREAMED.has(light.status) ? [light.shape] : []
+      })
+    const zones: FxZone[] = this.state.running.map((zone) => ({
+      zoneId: zone.zoneId,
+      stream: 'live',
+      look: this.state.looks.find((candidate) => candidate.id === zone.lookId) ?? { id: zone.lookId, category: 'ambient' },
+      shapes: shapes(zone.lights),
+      brightness: zone.state === 'waiting' ? 0 : zone.brightness,
+      frozen: zone.state === 'crashed',
+    }))
+    if (this.preview !== null) {
+      const { zoneId, look, lights } = this.preview
+      const lightIds = lights.map((light) => light.id)
+      const previewShapes = lightIds.flatMap((id) => this.state.lights.find((light) => light.id === id)?.shape ?? [])
+      zones.push({ zoneId, stream: 'preview', look, shapes: previewShapes, brightness: 1, frozen: false })
+    }
+    return zones
+  }
+
   // ── REST ─────────────────────────────────────────────────────────────────────────────────
 
   /** One request. `path` may carry a query, which is ignored. A method a path doesn't serve is a 404. */
@@ -1132,6 +1194,8 @@ export class MockServer {
           const id = this.newId('preview')
           this.preview = {
             id,
+            zoneId: zone.id,
+            look,
             lights: zone.lights.map((lightId) => this.painted(lightId, lights.get(lightId)?.leds ?? 0, spec, 1, false)),
             watchedAt: this.clock(),
           }
@@ -1150,6 +1214,7 @@ export class MockServer {
     if (body.look !== undefined) {
       const spec = motifFor(body.look)
       for (const light of this.preview.lights) light.spec = spec
+      this.preview.look = body.look
     }
     return noContent
   }
```

- [ ] **Step 5: Run them to see them pass**

Run: `(cd web && npx vitest run src/api/mocks/mock-fx.test.ts src/api/mocks/mock-server.test.ts src/api/live.test.ts)`
Expected: `Test Files  3 passed (3)`, `Tests  88 passed (88)`.

- [ ] **Step 6: The gate**

```bash
(cd web && npm test 2>&1 | grep -E 'Test Files|Tests ' && npm run lint && npx tsc -b && echo "tsc ok")
```

Expected: `Test Files  104 passed (104)`, `Tests  1105 passed (1105)`, lint clean, "tsc ok".

- [ ] **Step 7: Commit**

```bash
git add web/src/api/mocks/mock-fx.ts web/src/api/mocks/mock-fx.test.ts web/src/api/mocks/mock-server.ts web/src/api/mocks/mock-server.test.ts web/src/api/live.test.ts
git commit -m "feat(web): the mocks draw their looks in space"
```

---

### Task 4: A particle's look, from Main.html's fireflies

Main.html draws each firefly as a glow with one radial gradient round a small core. `design-extract.ts` reads that into `RENDER.particle` (ruling 10), checks every firefly against the rule, and names the one drawn off it.

**Files:**
- Modify: `web/scripts/design-extract.ts`
- Regenerate: `web/src/stage/design-numbers.ts` (`npm run design:numbers`)
- Test: `web/src/stage/design-numbers.node.test.ts`

**Interfaces:**
- Consumes: `readHandoff()`'s `main` (Main.html's text) and the extractor's helpers.
- Produces: `RENDER.particle { glow: { stops: {at, alpha}[] }, core: { lift, share, minPx, maxPx } }`, from `fireflies(mainHtml, main)`, which `extractRender()` calls; the test reaches it through `extractRender()` on an edited Main.html.

- [ ] **Step 1: Read the spec and the render**

Read §7.4. Look at `Main.png` once, at the fireflies in the room, and write down what you see: a soft glow, and a brighter, whiter point in it. Then read the fireflies' markup in `Main.html` (`grep -o '<g class="ff[0-9]*">.\{0,400\}' Main.html | head -3`, and the `radialGradient` they fill from) and `web/scripts/design-extract.ts`.

- [ ] **Step 2: Write the failing tests**

```diff
diff --git a/web/src/stage/design-numbers.node.test.ts b/web/src/stage/design-numbers.node.test.ts
index bf8d300..b874c8a 100644
--- a/web/src/stage/design-numbers.node.test.ts
+++ b/web/src/stage/design-numbers.node.test.ts
@@ -68,6 +68,23 @@ describe('the design numbers', () => {
     expect(LIVE_RENDER.selectedZoneNote.button).toMatch(/^#/)
   })
 
+  // §7.4: "firefly and ember particles (tiny glowing points)". F10 draws every particle as Main.html draws a firefly.
+  it('draw a particle as a glow fading to nothing at its edge, round a smaller, whiter core', () => {
+    const { glow, core } = RENDER.particle
+    expect(glow.stops.map((stop) => stop.at)).toEqual([0, ...glow.stops.slice(1, -1).map((stop) => stop.at), 1])
+    expect(glow.stops.at(-1)!.alpha).toBe(0)
+    expect(core.lift).toBeGreaterThan(0)
+    expect(core.lift).toBeLessThan(1)
+    expect(core.share).toBeLessThan(glow.stops[1].at)
+    expect(core.minPx).toBeLessThan(core.maxPx)
+  })
+
+  // A firefly whose core no longer keeps the rule is named, with its sizes.
+  it.runIf(handoff.read !== null)('name the firefly drawn off the rule', () => {
+    const swollen = (html: string) => html.replace(/(<g class="ff0"><circle [^>]+><\/circle><circle cx="[\d.]+" cy="[\d.]+" r=")[\d.]+"/, '$13"')
+    expect(() => extractRender(edited('Main', swollen))).toThrow(/fireflies: each a glow and a core draw a core of [\d.]+ px on a glow of [\d.]+ px, off the rule/)
+  })
+
   it('name the sentence that moved', () => {
     expect(() => extractSpec('')).toThrow(/§7\.1 Floors/)
     expect(() => extractLive('')).toThrow(/§4\.4/)
```

- [ ] **Step 3: Run them to see them fail**

Run: `(cd web && npx vitest run src/stage/design-numbers.node.test.ts)`
Expected: FAIL: `Tests  2 failed | 14 passed (16)`, with `TypeError: Cannot destructure property 'glow' of 'RENDER.particle' as it is undefined.`

- [ ] **Step 4: Write the code**

```diff
diff --git a/web/scripts/design-extract.ts b/web/scripts/design-extract.ts
index cae4add..5d5b01a 100644
--- a/web/scripts/design-extract.ts
+++ b/web/scripts/design-extract.ts
@@ -278,6 +278,52 @@ export function checkPins(pins: string, names: readonly string[], readBytes: (na
 const RGBA = String.raw`rgba\((\d+),(\d+),(\d+),([\d.]+)\)`
 const re = (source: string) => new RegExp(source)
 
+const channels = (hex: string) => [1, 3, 5].map((at) => parseInt(hex.slice(at, at + 2), 16))
+/** Two decimals: the renders' own colours are rounded to whole bytes, so a share read from them is good to about that. */
+const hundredths = (value: number) => Math.round(value * 100) / 100
+
+/**
+ * Main.html's fireflies (§7.4: "firefly and ember particles (tiny glowing points)"), each a glow and a
+ * core: the glow's radial falloff, the same for every firefly; how far the core's colour is lifted from
+ * the glow's towards white; and the core's size, a share of the glow's radius held between the smallest
+ * and largest cores the render draws. The share is the largest firefly's, and every core the render
+ * draws must come within 0.05 px of that rule, or this fails.
+ */
+function fireflies(mainHtml: string, main: string) {
+  const where = 'Main.html, the fireflies: each a glow and a core'
+  const flies = matches(main, {
+    where,
+    pattern: /<g class="ff\d+"><circle cx="[\d.]+" cy="[\d.]+" r="([\d.]+)" fill="url\(#([\w-]+)\)"><\/circle><circle cx="[\d.]+" cy="[\d.]+" r="([\d.]+)" fill="(#[0-9a-f]{6})"><\/circle><\/g>/,
+  })
+  const gradients = new Map(
+    [...new Set(flies.map((fly) => fly[2]))].map((id) => {
+      const body = same(mainHtml, { where: `Main.html, a firefly's gradient #${id}`, pattern: re(String.raw`<radialGradient id="${id}">([\s\S]*?)</radialGradient>`) })[1]
+      const stops = matches(body, {
+        where: `Main.html, the stops of a firefly's gradient #${id}`,
+        pattern: /<stop offset="([\d.]+)" stop-color="(#[0-9a-f]{6})" stop-opacity="([\d.]+)"><\/stop>/,
+      })
+      return [id, { colour: stops[0][2], stops: stops.map((stop) => ({ at: n(stop[1]), alpha: n(stop[3]) })) }] as const
+    }),
+  )
+  const falloffs = [...new Set([...gradients.values()].map((gradient) => JSON.stringify(gradient.stops)))]
+  if (falloffs.length !== 1) throw new Error(`design numbers: ${where} fall off ${falloffs.length} ways, not one`)
+  const lifts = flies.map((fly) => {
+    const glow = channels(gradients.get(fly[2])!.colour)
+    const core = channels(fly[4])
+    return core.reduce((sum, c, i) => sum + c - glow[i], 0) / glow.reduce((sum, g) => sum + 255 - g, 0)
+  })
+  const lift = hundredths(lifts.reduce((sum, value) => sum + value, 0) / lifts.length)
+  if (lifts.some((value) => Math.abs(value - lift) > 0.02)) throw new Error(`design numbers: ${where} lift their cores by more than one share`)
+  const sizes = flies.map((fly) => ({ glow: n(fly[1]), core: n(fly[3]) }))
+  const largest = sizes.reduce((a, b) => (b.glow > a.glow ? b : a))
+  const share = Math.round((largest.core / largest.glow) * 1000) / 1000
+  const minPx = Math.min(...sizes.map((size) => size.core))
+  const maxPx = Math.max(...sizes.map((size) => size.core))
+  const off = sizes.find(({ glow, core }) => Math.abs(Math.min(maxPx, Math.max(minPx, glow * share)) - core) > 0.05)
+  if (off !== undefined) throw new Error(`design numbers: ${where} draw a core of ${off.core} px on a glow of ${off.glow} px, off the rule`)
+  return { glow: { stops: JSON.parse(falloffs[0]) as { at: number; alpha: number }[] }, core: { lift, share, minPx, maxPx } }
+}
+
 /** RENDER: what the stage takes from the renders, where neither the spec nor tokens.css says it. */
 export function extractRender(read: ReadText): Record<string, unknown> {
   const tokens = read('tokens.css')
@@ -365,6 +411,8 @@ export function extractRender(read: ReadText): Record<string, unknown> {
     pattern: re(String.raw`<path d="M[\d.]+ [\d.]+ L([\d.]+) ([\d.]+)"[^>]*></path><path d="M([\d.]+) ([\d.]+) q([\d.]+) (-?[\d.]+) ([\d.]+) 0 t([\d.]+) 0 M[\d.]+ ([\d.]+) q[^"]*" stroke="${RGBA}" stroke-width="([\d.]+)"`),
   })
 
+  const particle = fireflies(mainHtml, main)
+
   // The strips' segments are drawn in their colour; the dark ones in a token (§7.3: "visible even when dark").
   const strokes = matches(main, {
     where: "Main.html, the strips' segments",
@@ -434,6 +482,7 @@ export function extractRender(read: ReadText): Record<string, unknown> {
       swatchGlowPx: n(tip[6]),
       leader: { lengthPx: n(leader[3]), widthPx: n(leader[4]), colour: colour(tokens, leader[5]), angleDeg: n(leader[6]) },
     },
+    particle,
     ownEffect: { ringPx: n(ring[1]), ...rgba(tokens, ring, 2), widthPx: n(ring[6]), dashPx: n(ring[7]), gapPx: n(ring[8]) },
     streamedCopy: {
       dxPx: n(waves[3]) - n(waves[1]),
```

- [ ] **Step 5: Regenerate the numbers**

```bash
(cd web && npm run design:numbers && git diff --stat src/stage/design-numbers.ts src/design/live-numbers.ts)
```

Expected: `src/stage/design-numbers.ts` alone changes, by 24 lines, and `git diff web/src/stage/design-numbers.ts` is exactly:

```diff
diff --git a/web/src/stage/design-numbers.ts b/web/src/stage/design-numbers.ts
index 7c110c0..1b8a1bf 100644
--- a/web/src/stage/design-numbers.ts
+++ b/web/src/stage/design-numbers.ts
@@ -244,6 +244,30 @@ export const RENDER = {
       "angleDeg": -69.7
     }
   },
+  "particle": {
+    "glow": {
+      "stops": [
+        {
+          "at": 0,
+          "alpha": 0.9
+        },
+        {
+          "at": 0.3,
+          "alpha": 0.25
+        },
+        {
+          "at": 1,
+          "alpha": 0
+        }
+      ]
+    },
+    "core": {
+      "lift": 0.5,
+      "share": 0.222,
+      "minPx": 0.9,
+      "maxPx": 1.4
+    }
+  },
   "ownEffect": {
     "ringPx": 7.5,
     "colour": "--color-text",
```

If any number differs, the pinned Main.html isn't the one this plan read: stop and tell the owner.

- [ ] **Step 6: Run them to see them pass**

Run: `(cd web && npx vitest run src/stage/design-numbers.node.test.ts)`
Expected: `Test Files  1 passed (1)`, `Tests  16 passed (16)`.

- [ ] **Step 7: The gate**

```bash
(cd web && npm test 2>&1 | grep -E 'Test Files|Tests ' && npm run lint && npx tsc -b && echo "tsc ok")
```

Expected: `Test Files  104 passed (104)`, `Tests  1107 passed (1107)`, lint clean, "tsc ok".

- [ ] **Step 8: Commit**

```bash
git add web/scripts/design-extract.ts web/src/stage/design-numbers.ts web/src/stage/design-numbers.node.test.ts
git commit -m "feat(web): read a particle's look from Main.html's fireflies"
```

---

### Task 5: Write the pictures into arrays the stage keeps

`FxWriter` turns the store's picture of the zones the stage picks into what the GPU draws: one instance per particle, ring and plane, in three's world, into arrays it keeps (ruling 15).

**Files:**
- Create: `web/src/stage/fx-writer.ts`
- Test: `web/src/stage/fx-writer.test.ts` (create)

**Interfaces:**
- Consumes: Task 1's `FxStore` and items.
- Produces:
  - `FxPick { preview: Id | null; hidden: ReadonlySet<Id> }` and `LIVE_ONLY`.
  - `FxBatch(sizes)`: `count`, `generation`, `arrays`, `capacity`, `reserve(count)`.
  - `FxWriter`: `particles` (centre 3, colour 3, size 1), `rings` (centre 3, colour 3, shape 3: radius, width, form with a circle 1), `planes` (point 3, unit normal 3, ray 3 or zeros, colour 3, width 1), and `write(fx, pick): boolean`.

- [ ] **Step 1: Read the code**

Read `web/src/stage/frame-writer.ts` (its arrays kept in place, and `write()` saying whether anything changed) and `toWorld()` in `web/src/stage/plan.ts`: three's world is the plan's x, then up, then the plan's y.

- [ ] **Step 2: Write the failing test**

Create `web/src/stage/fx-writer.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { FxStore } from '@/api/fx'
import type { ZoneFx } from '@/api/ws-messages'
import { FxWriter, LIVE_ONLY, type FxPick } from './fx-writer'

const living: ZoneFx = {
  zoneId: 'living',
  stream: 'live',
  particles: [
    [1, 2, 3, 0.5, 2, -1, 0.4],
    [4, 5, 6, 0.1, 0.2, 0.3, 0.2],
  ],
}
const office: ZoneFx = {
  zoneId: 'office',
  stream: 'live',
  rings: [{ center: [1, 2, 0], radius: 1.5, width: 0.3, rgb: [1, 0, 0], form: 'circle' }],
  planes: [{ point: [1, 2, 3], normal: [0, 0, 2], width: 0.1, rgb: [0, 1, 0], ray: [1, 0, 0] }],
}
const preview: ZoneFx = { zoneId: 'office', stream: 'preview', rings: [{ center: [0, 0, 1], radius: 1, width: 0.2, rgb: [0, 0, 1], form: 'sphere' }] }

function store(...zones: ZoneFx[]): FxStore {
  const fx = new FxStore()
  fx.apply({ channel: 'fx', zones })
  return fx
}

describe('FxWriter', () => {
  it("writes each particle in three's world, its colour clamped to 0–1", () => {
    const writer = new FxWriter()
    expect(writer.write(store(living), LIVE_ONLY)).toBe(true)
    const [centres, colours, sizes] = writer.particles.arrays
    expect(writer.particles.count).toBe(2)
    expect([...centres.slice(0, 6)]).toEqual([1, 3, 2, 4, 6, 5])
    expect([...colours.slice(0, 3)]).toEqual([0.5, 1, 0])
    expect(sizes[0]).toBeCloseTo(0.4)
  })

  it('writes rings with their form, and planes with a unit normal and their ray', () => {
    const writer = new FxWriter()
    writer.write(store(office), LIVE_ONLY)
    const [centres, , shapes] = writer.rings.arrays
    expect([...centres.slice(0, 3), ...shapes.slice(0, 3)].map((value) => Math.round(value * 10) / 10)).toEqual([1, 0, 2, 1.5, 0.3, 1])
    const [points, normals, rays, , widths] = writer.planes.arrays
    expect([...points.slice(0, 3), ...normals.slice(0, 3), ...rays.slice(0, 3)]).toEqual([1, 3, 2, 0, 1, 0, 1, 0, 0])
    expect(widths[0]).toBeCloseTo(0.1)
  })

  it("draws the preview of the picked zone only, and leaves the hidden zones' live fx out", () => {
    const writer = new FxWriter()
    const fx = store(living, office, preview)
    writer.write(fx, LIVE_ONLY)
    expect([writer.particles.count, writer.rings.count, writer.planes.count]).toEqual([2, 1, 1])
    writer.write(fx, { preview: 'office', hidden: new Set(['office']) })
    expect([writer.particles.count, writer.rings.count, writer.planes.count]).toEqual([2, 1, 0])
    expect(writer.rings.arrays[2][2]).toBe(0) // the preview's sphere
  })

  it('writes nothing again until the store has a new picture or the stage picks other zones', () => {
    const writer = new FxWriter()
    const fx = store(living)
    const pick: FxPick = { preview: null, hidden: new Set() }
    expect(writer.write(fx, pick)).toBe(true)
    expect(writer.write(fx, pick)).toBe(false)
    fx.apply({ channel: 'fx', zones: [] })
    expect(writer.write(fx, pick)).toBe(true)
    expect(writer.particles.count).toBe(0)
    expect(writer.write(fx, { ...pick })).toBe(true)
  })

  // Frame-writer style: a picture as large as one before it allocates nothing.
  it('keeps its arrays as long as they hold the picture, and grows them to the largest', () => {
    const writer = new FxWriter()
    const fx = new FxStore()
    const many = (count: number): ZoneFx => ({
      zoneId: 'living',
      stream: 'live',
      particles: Array.from({ length: count }, (_, i) => [i, 0, 0, 1, 1, 1, 0.2] as [number, number, number, number, number, number, number]),
    })
    fx.apply({ channel: 'fx', zones: [many(10)] })
    writer.write(fx, LIVE_ONLY)
    const [generation, arrays] = [writer.particles.generation, writer.particles.arrays]
    fx.apply({ channel: 'fx', zones: [many(3)] })
    writer.write(fx, LIVE_ONLY)
    fx.apply({ channel: 'fx', zones: [many(16)] })
    writer.write(fx, LIVE_ONLY)
    expect([writer.particles.generation, writer.particles.arrays]).toEqual([generation, arrays])
    fx.apply({ channel: 'fx', zones: [many(40)] })
    writer.write(fx, LIVE_ONLY)
    expect(writer.particles.generation).toBe(generation + 1)
    expect(writer.particles.capacity).toBe(40)
    fx.apply({ channel: 'fx', zones: [many(2)] })
    writer.write(fx, LIVE_ONLY)
    expect(writer.particles.capacity).toBe(40)
  })
})
```

- [ ] **Step 3: Run it to see it fail**

Run: `(cd web && npx vitest run src/stage/fx-writer.test.ts)`
Expected: FAIL to load: `Failed to resolve import "./fx-writer"`.

- [ ] **Step 4: Write the code**

Create `web/src/stage/fx-writer.ts`:

```ts
// Turns the fx store's pictures into what the GPU draws for "Effects in space" (§7.4, §12.4): each
// particle, ring and plane as one instance, its places in three's world (plan.ts's toWorld) and its
// colour clamped to 0–1. As the frame writer does, it writes into arrays it keeps: they grow to the
// most it has ever written and never shrink, so a picture allocates nothing once the stage has seen
// its largest, and the fx layer hands these very arrays to three. It writes only when the store has a
// new picture or the stage picks other zones, and says whether it did.
import type { Id } from '@/api/contract'
import type { FxStore } from '@/api/fx'
import type { FxPlane, FxRing, ZoneFx } from '@/api/ws-messages'

/** Which zones the stage draws: every live zone but the hidden ones, and the preview of one zone. */
export interface FxPick {
  /** The zone whose preview stream's fx are drawn (§7.6 compose), or null for none. */
  preview: Id | null
  /** Live zones whose fx aren't drawn: under the composer's preview, or outside focus's zone. */
  hidden: ReadonlySet<Id>
}

export const LIVE_ONLY: FxPick = { preview: null, hidden: new Set() }

/** One kind of instance: its arrays, `sizes` floats each, and how many it holds now. */
export class FxBatch {
  count = 0
  /** Moves whenever the arrays are replaced by larger ones: the meshes then make new attributes. */
  generation = 0
  arrays: Float32Array[]
  private readonly sizes: readonly number[]

  constructor(sizes: readonly number[]) {
    this.sizes = sizes
    this.arrays = sizes.map(() => new Float32Array(0))
  }

  get capacity(): number {
    return this.arrays[0].length / this.sizes[0]
  }

  /** Room for `count`: at least double, so a growing picture makes new arrays only now and then. */
  reserve(count: number): void {
    if (count <= this.capacity) return
    const capacity = Math.max(count, this.capacity * 2, MIN_CAPACITY)
    this.arrays = this.sizes.map((size) => new Float32Array(capacity * size))
    this.generation += 1
  }
}

const MIN_CAPACITY = 16
const NONE: readonly never[] = []

const clamp01 = (value: number) => Math.min(1, Math.max(0, value))

/** A plan point (x, y, z up) into `out` at `at` as three's world point (x, z, y). */
function world(out: Float32Array, at: number, x: number, y: number, z: number): void {
  out[at] = x
  out[at + 1] = z
  out[at + 2] = y
}

function colour(out: Float32Array, at: number, r: number, g: number, b: number): void {
  out[at] = clamp01(r)
  out[at + 1] = clamp01(g)
  out[at + 2] = clamp01(b)
}

export class FxWriter {
  /** centre (3), colour (3), size: the glow's radius, metres (1). */
  readonly particles = new FxBatch([3, 3, 1])
  /** centre (3), colour (3), shape: radius, width and form, 0 a sphere and 1 a circle (3). */
  readonly rings = new FxBatch([3, 3, 3])
  /** point (3), normal (3), ray (3; 0 for none), colour (3), width (1). */
  readonly planes = new FxBatch([3, 3, 3, 3, 1])
  private version = -1
  private pick: FxPick | null = null
  /** The zones written, reused from write to write. */
  private readonly zones: ZoneFx[] = []

  /** Writes the store's picture of the picked zones; false when nothing changed since the last write. */
  write(fx: FxStore, pick: FxPick): boolean {
    if (fx.version === this.version && pick === this.pick) return false
    this.version = fx.version
    this.pick = pick
    const zones = this.zones
    zones.length = 0
    for (const zone of fx.live.values()) if (!pick.hidden.has(zone.zoneId)) zones.push(zone)
    const preview = pick.preview === null ? undefined : fx.get(pick.preview, 'preview')
    if (preview !== undefined) zones.push(preview)
    let particles = 0
    let rings = 0
    let planes = 0
    for (const zone of zones) {
      particles += zone.particles?.length ?? 0
      rings += zone.rings?.length ?? 0
      planes += zone.planes?.length ?? 0
    }
    this.particles.reserve(particles)
    this.rings.reserve(rings)
    this.planes.reserve(planes)
    this.particles.count = 0
    this.rings.count = 0
    this.planes.count = 0
    for (const zone of zones) {
      for (const particle of zone.particles ?? NONE) this.particle(particle)
      for (const ring of zone.rings ?? NONE) this.ring(ring)
      for (const plane of zone.planes ?? NONE) this.plane(plane)
    }
    return true
  }

  private particle([x, y, z, r, g, b, size]: readonly number[]): void {
    const i = this.particles.count++
    const [centres, colours, sizes] = this.particles.arrays
    world(centres, i * 3, x, y, z)
    colour(colours, i * 3, r, g, b)
    sizes[i] = size
  }

  private ring({ center, radius, width, rgb, form }: FxRing): void {
    const i = this.rings.count++
    const [centres, colours, shapes] = this.rings.arrays
    world(centres, i * 3, center[0], center[1], center[2])
    colour(colours, i * 3, rgb[0], rgb[1], rgb[2])
    shapes[i * 3] = radius
    shapes[i * 3 + 1] = width
    shapes[i * 3 + 2] = form === 'circle' ? 1 : 0
  }

  private plane({ point, normal, ray, rgb, width }: FxPlane): void {
    const i = this.planes.count++
    const [points, normals, rays, colours, widths] = this.planes.arrays
    world(points, i * 3, point[0], point[1], point[2])
    const length = Math.hypot(normal[0], normal[1], normal[2])
    world(normals, i * 3, normal[0] / length, normal[1] / length, normal[2] / length)
    if (ray === undefined) world(rays, i * 3, 0, 0, 0)
    else world(rays, i * 3, ray[0], ray[1], ray[2])
    colour(colours, i * 3, rgb[0], rgb[1], rgb[2])
    widths[i] = width
  }
}
```

- [ ] **Step 5: Run it to see it pass**

Run: `(cd web && npx vitest run src/stage/fx-writer.test.ts)`
Expected: `Tests  5 passed (5)`.

- [ ] **Step 6: The gate**

```bash
(cd web && npm test 2>&1 | grep -E 'Test Files|Tests ' && npm run lint && npx tsc -b && echo "tsc ok")
```

Expected: `Test Files  105 passed (105)`, `Tests  1112 passed (1112)`, lint clean, "tsc ok".

- [ ] **Step 7: Commit**

```bash
git add web/src/stage/fx-writer.ts web/src/stage/fx-writer.test.ts
git commit -m "feat(web): write the fx pictures into arrays the stage keeps"
```

---

### Task 6: Draw the effects on the stage's cadence

The meshes, their shaders, and the layer that puts them on the canvas, drawing on the stage's one cadence beside the lights (rulings 10 to 16). `StageScene` takes an `fx` pick, null while it draws none. `StageView` passes null until Task 7.

**Files:**
- Create: `web/src/stage/scene/fx-shaders.ts`, `web/src/stage/scene/fx-meshes.ts`, `web/src/stage/scene/draw-list.ts`, `web/src/stage/scene/fx-layer.tsx`
- Modify: `web/src/stage/cadence.ts`, `web/src/stage/scene/light-layer.tsx`, `web/src/stage/scene/stage-scene.tsx`, `web/src/stage/stage-view.tsx`, `web/src/test/stage.ts`
- Test: `web/src/stage/cadence.test.ts`, `web/src/stage/scene/fx-meshes.test.ts` (create), `web/src/stage/scene/stage-scene.test.tsx`

**Interfaces:**
- Consumes: Task 4's `RENDER.particle`; `SPEC.window.glassAlpha`; `POOL_LIFT_M` and `maskTexture()` (`light-shaders.ts`); `roomMask()`; `bounds()` (`plan.ts`); `CameraPose` (`zoom`, `back`); Task 5's `FxWriter`, `FxBatch` and `FxPick`; Task 2's `fx` store.
- Produces:
  - `fx-shaders.ts`: `particleMaterial()`, `ringMaterial()`, `planeMaterial(bounds: PlaneBounds)`.
  - `fx-meshes.ts`: `FxMaterials(home)` with `setView(pose)` and `dispose()`; `FxMeshes(writer, materials)` with `group`, `update()` and `dispose()`.
  - `draw-list.ts`: `Drawer`, `DrawList` with `add(drawer)` and `draw()`.
  - `fx-layer.tsx`: `FxLayer({home, pick, pose, drawList})`.
  - `StageSceneProps.fx: FxPick | null`. `LightLayerProps.drawList` takes `cadenceMs`'s place.

- [ ] **Step 1: Read the spec, the render and the code**

Read §7.4, §7.5 and §7.1's glass pane. Look at `Main.png` once more, at the fireflies over the floor and the lamps. Then read:
- `web/src/stage/scene/light-shaders.ts` (`POOL_LIFT_M`, `maskTexture()`, the halo's additive material);
- `web/src/stage/scene/light-meshes.ts` and `light-layer.tsx`;
- `web/src/stage/scene/stage-scene.tsx`, `web/src/stage/cadence.ts` and `web/src/stage/camera.ts` (`CameraPose.zoom`, pixels per metre, and `back`).

The plane material's normal attribute is `planeNormal`: three's `ShaderMaterial` declares `attribute vec3 normal` itself, and a second declaration doesn't compile.

- [ ] **Step 2: Write the failing tests**

Create `web/src/stage/scene/fx-meshes.test.ts`:

```ts
import { InstancedMesh } from 'three'
import { describe, expect, it } from 'vitest'
import { FxStore } from '@/api/fx'
import type { ZoneFx } from '@/api/ws-messages'
import { heroPose } from '@/test/stage'
import { buildScenario } from '@/api/mocks/scenarios'
import { HERO_NOW } from '@/test/live'
import { RENDER, SPEC } from '../design-numbers'
import { FxWriter, LIVE_ONLY } from '../fx-writer'
import { FxMaterials, FxMeshes } from './fx-meshes'

const { home } = buildScenario('hero', HERO_NOW)

const particles = (count: number): ZoneFx => ({
  zoneId: 'living',
  stream: 'live',
  particles: Array.from({ length: count }, (_, i) => [i, 1, 1, 1, 1, 1, 0.3] as [number, number, number, number, number, number, number]),
})

function drawn(...zones: ZoneFx[]) {
  const fx = new FxStore()
  const writer = new FxWriter()
  const meshes = new FxMeshes(writer, new FxMaterials(home))
  const show = (...next: ZoneFx[]) => {
    fx.apply({ channel: 'fx', zones: next })
    writer.write(fx, LIVE_ONLY)
    meshes.update()
    return meshes.group.children as InstancedMesh[]
  }
  return { show, meshes, first: show(...zones) }
}

describe('the effects in space (§7.4)', () => {
  it('draws as many of each as the picture holds, one mesh each', () => {
    const { first } = drawn(particles(3), {
      zoneId: 'office',
      stream: 'live',
      rings: [{ center: [1, 1, 0], radius: 1, width: 0.2, rgb: [1, 1, 1], form: 'circle' }],
    })
    expect(first.map((mesh) => mesh.count)).toEqual([3, 1])
    expect(first.every((mesh) => mesh.frustumCulled === false)).toBe(true)
  })

  it('keeps its meshes while the arrays hold the picture, hides one with nothing to draw, and makes a new one when they grow', () => {
    const { show, first } = drawn(particles(3))
    const [mesh] = first
    expect(show(particles(10))).toEqual([mesh])
    expect(show()[0].visible).toBe(false)
    const [grown] = show(particles(40))
    expect(grown).not.toBe(mesh)
    expect(grown.count).toBe(40)
  })

  it("lets go of its meshes, and the materials of theirs, when they're done", () => {
    const { meshes } = drawn(particles(3))
    meshes.dispose()
    expect(meshes.group.children).toEqual([])
  })

  it("draws the particles as the render's fireflies, and planes and rings at the glass's alpha", () => {
    const materials = new FxMaterials(home)
    for (const stop of RENDER.particle.glow.stops) expect(materials.particle.fragmentShader).toContain(`${stop.alpha}`)
    expect(materials.ring.uniforms.glassAlpha.value).toBe(SPEC.window.glassAlpha)
    expect(materials.plane.uniforms.glassAlpha.value).toBe(SPEC.window.glassAlpha)
    expect(materials.plane.uniforms.ceiling.value).toBe(home.ceiling)
    const pose = heroPose()
    materials.setView(pose)
    expect(materials.particle.uniforms.pxPerM.value).toBe(pose.zoom)
    expect(materials.plane.uniforms.back.value.toArray()).toEqual(pose.back)
  })
})
```

```diff
diff --git a/web/src/stage/cadence.test.ts b/web/src/stage/cadence.test.ts
index 4b1202b..c2fec68 100644
--- a/web/src/stage/cadence.test.ts
+++ b/web/src/stage/cadence.test.ts
@@ -1,5 +1,6 @@
 import { renderHook } from '@testing-library/react'
 import { beforeEach, describe, expect, it, vi } from 'vitest'
+import { fx } from '@/api/live'
 import { pushFrame } from '@/test/live'
 import { Cadence, useCadence } from './cadence'
 import { SPEC } from './design-numbers'
@@ -77,6 +78,22 @@ describe('useCadence', () => {
     expect(draw).toHaveBeenCalledTimes(2)
   })
 
+  // F10: a picture of the effects in space is something new to draw, as a frame is.
+  it('wakes for a new picture of the effects in space, as for a frame', () => {
+    const draw = vi.fn()
+    renderHook(() => useCadence(1000 / SPEC.target.fps, draw))
+    nextFrame()
+    vi.advanceTimersToNextFrame()
+    expect(vi.getTimerCount()).toBe(0)
+    fx.apply({ channel: 'fx', zones: [{ zoneId: 'living', stream: 'live', particles: [[1, 1, 1, 1, 1, 1, 0.2]] }] })
+    expect(vi.getTimerCount()).toBe(1)
+    vi.advanceTimersToNextFrame()
+    expect(draw).toHaveBeenCalledTimes(2)
+    // Woken once: the frame store's wait went with the picture's.
+    pushFrame('rope', (seq += 1), [7, 8, 9])
+    expect(vi.getTimerCount()).toBe(1)
+  })
+
   it('stops when the stage goes', () => {
     const draw = vi.fn()
     const { unmount } = renderHook(() => useCadence(1000 / SPEC.target.fps, draw))
diff --git a/web/src/stage/scene/stage-scene.test.tsx b/web/src/stage/scene/stage-scene.test.tsx
index 3387cf2..66a33cb 100644
--- a/web/src/stage/scene/stage-scene.test.tsx
+++ b/web/src/stage/scene/stage-scene.test.tsx
@@ -4,11 +4,13 @@ import { Profiler, type ReactNode } from 'react'
 import { InstancedMesh, type Object3D, OrthographicCamera, type WebGLRenderer } from 'three'
 import { LineSegments2 } from 'three/addons/lines/LineSegments2.js'
 import { beforeEach, describe, expect, it, vi } from 'vitest'
+import { fx, wantFx } from '@/api/live'
 import { liveStore } from '@/api/live-store'
 import { HERO_NOW, pushFrame, startMockDataLayer } from '@/test/live'
 import { sceneProps } from '@/test/stage'
 import { SPEC } from '../design-numbers'
 import { FrameWriter } from '../frame-writer'
+import { LIVE_ONLY } from '../fx-writer'
 import type { RGB } from '@/lib/light-colour'
 import { HomeScene } from './home-scene'
 import { StageScene } from './stage-scene'
@@ -147,6 +149,47 @@ describe('the stage scene (§7.2, §7.5)', () => {
     expect(after.materials.every((material) => before.materials.includes(material))).toBe(true)
   })
 
+  // F10: the effects in space draw on the lights' cadence, so the canvas renders once a draw for both.
+  it("draws the hero's effects in space beside its lights, rendering once a draw", async () => {
+    startMockDataLayer()
+    const release = wantFx()
+    const props = sceneProps('hero', { cadenceMs: 1000 / SPEC.target.fps, fx: LIVE_ONLY })
+    let gl: WebGLRenderer | undefined
+    function Renderer() {
+      gl = useThree((state) => state.gl)
+      return null
+    }
+    const { renderer } = await renderScene(
+      <>
+        <StageScene {...props} />
+        <Renderer />
+      </>,
+    )
+    await vi.advanceTimersByTimeAsync(1000)
+    expect(fx.live.size).toBeGreaterThan(0)
+    const scene = renderer.scene.instance as Object3D
+    const fxMeshes = () => scene.children.at(-1)!.children as InstancedMesh[]
+    expect(fxMeshes()[0].count).toBeGreaterThan(0)
+    const render = vi.spyOn(gl!, 'render')
+    const draws = vi.spyOn(props.writer, 'write')
+    await vi.advanceTimersByTimeAsync(1000)
+    expect(render.mock.calls.length).toBeGreaterThan(0)
+    expect(render.mock.calls.length).toBeLessThanOrEqual(draws.mock.calls.length)
+    release()
+  })
+
+  it('draws no effects in space while it picks none, and lets them go when it stops', async () => {
+    startMockDataLayer()
+    const release = wantFx()
+    const props = sceneProps('hero', { cadenceMs: 1000 / SPEC.target.fps })
+    const { renderer } = await renderScene(<StageScene {...props} fx={LIVE_ONLY} />)
+    const scene = renderer.scene.instance as Object3D
+    const count = scene.children.length
+    await renderer.update(<StageScene {...props} />)
+    expect(scene.children.length).toBe(count - 1)
+    release()
+  })
+
   it('lets go of the home when the stage goes', async () => {
     const dispose = vi.spyOn(HomeScene.prototype, 'dispose')
     const { renderer } = await renderScene(<StageScene {...sceneProps()} />)
```

- [ ] **Step 3: Run them to see them fail**

Run: `(cd web && npx vitest run src/stage/cadence.test.ts src/stage/scene/fx-meshes.test.ts src/stage/scene/stage-scene.test.tsx)`
Expected: FAIL. `fx-meshes.test.ts` fails to load (`Failed to resolve import "./fx-meshes"`), and `Tests  2 failed | 20 passed (22)`: "wakes for a new picture of the effects in space, as for a frame" (`expected +0 to be 1`) and "draws no effects in space while it picks none, and lets them go when it stops".

- [ ] **Step 4: The shaders and the meshes**

Create `web/src/stage/scene/fx-shaders.ts`:

```ts
// "Effects in space" (§7.4): what the zones' looks are doing in the room, drawn faintly over it. All
// three add (additive blending, as the halos and pools do) and test depth without writing it, so a
// wall in front hides them and they never hide one another.
// - A particle is Main.html's firefly (RENDER.particle): a glow whose radius is the particle's `size`
//   in metres, so the reach drawn is the reach it lights the lamps with, falling off as the render's
//   gradient does, round a core of a share of the glow's radius in CSS px, held between the render's
//   smallest and largest cores, its colour lifted towards white at its own intensity.
// - A ring's `sphere` is a shell seen through: a disc facing the camera, as bright at each point as
//   the shell is thick along the line of sight there, so its rim is brightest. A `circle` lies level,
//   an annulus `width` across, on the floor's pools' lift.
// - A plane is a sheet through the home, clipped to its outline and between its floor and ceiling;
//   with a `ray`, only the half on that side of its point.
// Their brightness is the stage's one number for a translucent surface, SPEC.window.glassAlpha (§7.1's
// glass pane), times the colour, which carries the zone's brightness (§12.4).
import { AdditiveBlending, DoubleSide, ShaderMaterial, Vector2, Vector3, type DataTexture } from 'three'
import { RENDER, SPEC } from '../design-numbers'
import type { RoomMask } from '../room-mask'
import { POOL_LIFT_M } from './light-shaders'

/** A GLSL float literal. */
const glsl = (value: number): string => (Number.isInteger(value) ? `${value}.0` : `${value}`)

/** RENDER.particle's glow: straight lines between the render's gradient stops, 0 past the last. */
const GLOW = /* glsl */ `
  float glow(float r) {
    ${RENDER.particle.glow.stops
      .slice(1)
      .map((stop, i) => {
        const from = RENDER.particle.glow.stops[i]
        return `if (r <= ${glsl(stop.at)}) return mix(${glsl(from.alpha)}, ${glsl(stop.alpha)}, (r - ${glsl(from.at)}) / ${glsl(stop.at - from.at)});`
      })
      .join('\n    ')}
    return 0.0;
  }
`

const ADDS = { blending: AdditiveBlending, transparent: true, depthWrite: false } as const

/** Particles: a quad per particle facing the camera, `size` metres in radius, or wide enough for its core. */
export function particleMaterial(): ShaderMaterial {
  const { share, minPx, maxPx, lift } = RENDER.particle.core
  return new ShaderMaterial({
    uniforms: { pxPerM: { value: 1 } },
    vertexShader: /* glsl */ `
      attribute vec3 centre;
      attribute vec3 colour;
      attribute float size;
      uniform float pxPerM;
      varying vec2 vOffsetM;
      varying vec3 vColour;
      varying float vSize;
      void main() {
        float quad = max(size, ${glsl(maxPx)} / pxPerM);
        vec4 view = modelViewMatrix * vec4(centre, 1.0);
        view.xy += position.xy * quad;
        gl_Position = projectionMatrix * view;
        vOffsetM = position.xy * quad;
        vColour = colour;
        vSize = size;
      }
    `,
    fragmentShader: /* glsl */ `
      ${GLOW}
      uniform float pxPerM;
      varying vec2 vOffsetM;
      varying vec3 vColour;
      varying float vSize;
      void main() {
        float d = length(vOffsetM);
        float corePx = clamp(vSize * pxPerM * ${glsl(share)}, ${glsl(minPx)}, ${glsl(maxPx)});
        float core = 1.0 - smoothstep(corePx - 0.5, corePx + 0.5, d * pxPerM);
        float halo = glow(d / vSize);
        if (core <= 0.0 && halo <= 0.0) discard;
        float intensity = max(vColour.r, max(vColour.g, vColour.b));
        vec3 lifted = vColour + ${glsl(lift)} * (vec3(intensity) - vColour);
        gl_FragColor = vec4(mix(vColour * halo, lifted, core), 1.0);
      }
    `,
    ...ADDS,
  })
}

/** Rings: a sphere's disc faces the camera, and a circle's lies level; `shape` is radius, width and form (1 a circle). */
export function ringMaterial(): ShaderMaterial {
  return new ShaderMaterial({
    uniforms: { glassAlpha: { value: SPEC.window.glassAlpha }, lift: { value: POOL_LIFT_M } },
    vertexShader: /* glsl */ `
      attribute vec3 centre;
      attribute vec3 colour;
      attribute vec3 shape;
      uniform float lift;
      varying vec2 vOffsetM;
      varying vec3 vColour;
      varying vec3 vShape;
      void main() {
        float outer = shape.x + shape.y * 0.5;
        vOffsetM = position.xy * outer;
        if (shape.z > 0.5) {
          vec3 world = centre + vec3(vOffsetM.x, lift, vOffsetM.y);
          gl_Position = projectionMatrix * viewMatrix * vec4(world, 1.0);
        } else {
          vec4 view = modelViewMatrix * vec4(centre, 1.0);
          view.xy += vOffsetM;
          gl_Position = projectionMatrix * view;
        }
        vColour = colour;
        vShape = shape;
      }
    `,
    fragmentShader: /* glsl */ `
      uniform float glassAlpha;
      varying vec2 vOffsetM;
      varying vec3 vColour;
      varying vec3 vShape;
      void main() {
        float rho = length(vOffsetM);
        float outer = vShape.x + vShape.y * 0.5;
        float inner = max(0.0, vShape.x - vShape.y * 0.5);
        if (rho > outer) discard;
        float alpha;
        if (vShape.z > 0.5) {
          if (rho < inner) discard;
          alpha = glassAlpha;
        } else {
          // The shell's thickness along the line of sight here, as a share of its width.
          float chord = 2.0 * (sqrt(max(outer * outer - rho * rho, 0.0)) - sqrt(max(inner * inner - rho * rho, 0.0)));
          alpha = min(1.0, glassAlpha * chord / vShape.y);
        }
        gl_FragColor = vec4(vColour * alpha, 1.0);
      }
    `,
    ...ADDS,
    side: DoubleSide,
  })
}

/** Where a plane may draw: the home's outline as a room mask (one room), its floor and ceiling, and the sphere round it. */
export interface PlaneBounds {
  mask: RoomMask
  texture: DataTexture
  ceilingM: number
  /** The home's middle, in three's world, and how far its farthest corner is from there. */
  centre: [number, number, number]
  reachM: number
}

/**
 * Planes: a square in the plane round the point nearest the home's middle, as wide as the home, drawn
 * inside its outline, between its floor and ceiling and, with a ray, on the ray's side only. Face on it
 * is glassAlpha; turned away it thickens, as a pane of glass seen along it does, to 1.
 */
export function planeMaterial({ mask, texture, ceilingM, centre, reachM }: PlaneBounds): ShaderMaterial {
  return new ShaderMaterial({
    uniforms: {
      mask: { value: texture },
      maskOrigin: { value: new Vector2(...mask.origin) },
      maskSize: { value: new Vector2(mask.width * mask.cellM, mask.height * mask.cellM) },
      ceiling: { value: ceilingM },
      homeCentre: { value: new Vector3(...centre) },
      reach: { value: reachM },
      back: { value: new Vector3(0, 0, 1) },
      glassAlpha: { value: SPEC.window.glassAlpha },
    },
    vertexShader: /* glsl */ `
      attribute vec3 point;
      attribute vec3 planeNormal; // three declares its own normal
      attribute vec3 ray;
      attribute vec3 colour;
      uniform vec3 homeCentre;
      uniform float reach;
      varying vec3 vWorld;
      varying vec3 vPoint;
      varying vec3 vNormal;
      varying vec3 vRay;
      varying vec3 vColour;
      void main() {
        vec3 middle = homeCentre - dot(homeCentre - point, planeNormal) * planeNormal;
        vec3 across = abs(planeNormal.y) < 0.99 ? vec3(0.0, 1.0, 0.0) : vec3(1.0, 0.0, 0.0);
        vec3 u = normalize(cross(planeNormal, across));
        vec3 v = cross(planeNormal, u);
        vWorld = middle + (u * position.x + v * position.y) * reach;
        gl_Position = projectionMatrix * viewMatrix * vec4(vWorld, 1.0);
        vPoint = point;
        vNormal = planeNormal;
        vRay = ray;
        vColour = colour;
      }
    `,
    fragmentShader: /* glsl */ `
      uniform sampler2D mask;
      uniform vec2 maskOrigin;
      uniform vec2 maskSize;
      uniform float ceiling;
      uniform vec3 back;
      uniform float glassAlpha;
      varying vec3 vWorld;
      varying vec3 vPoint;
      varying vec3 vNormal;
      varying vec3 vRay;
      varying vec3 vColour;
      void main() {
        if (vWorld.y < 0.0 || vWorld.y > ceiling) discard;
        if (dot(vRay, vRay) > 0.0 && dot(vWorld - vPoint, vRay) < 0.0) discard;
        vec2 uv = (vWorld.xz - maskOrigin) / maskSize;
        if (uv.x < 0.0 || uv.y < 0.0 || uv.x > 1.0 || uv.y > 1.0 || texture2D(mask, uv).r == 0.0) discard;
        float facing = abs(dot(vNormal, back));
        float alpha = min(1.0, glassAlpha / max(facing, glassAlpha));
        gl_FragColor = vec4(vColour * alpha, 1.0);
      }
    `,
    ...ADDS,
    side: DoubleSide,
  })
}
```

Create `web/src/stage/scene/fx-meshes.ts`:

```ts
// "Effects in space"'s three objects (§7.4): one InstancedMesh each for the particles, the rings and
// the planes. Their attributes are the fx writer's own arrays, so a picture is written once and only
// flagged here; each mesh draws as many instances as the writer wrote, and is made again only when the
// writer's arrays grow. Their materials, and the outline's mask, are FxMaterials: made once per home.
import { DynamicDrawUsage, Group, InstancedBufferAttribute, InstancedMesh, PlaneGeometry, type DataTexture, type ShaderMaterial } from 'three'
import type { Home } from '@/api/contract'
import type { CameraPose } from '../camera'
import type { FxBatch, FxWriter } from '../fx-writer'
import { bounds } from '../plan'
import { roomMask } from '../room-mask'
import { particleMaterial, planeMaterial, ringMaterial } from './fx-shaders'
import { maskTexture } from './light-shaders'

/** The fx's materials and the home outline's mask: once per home. */
export class FxMaterials {
  readonly particle = particleMaterial()
  readonly ring = ringMaterial()
  readonly plane: ShaderMaterial
  private readonly texture: DataTexture

  constructor(home: Pick<Home, 'outline' | 'ceiling'>) {
    // The outline as one room: a plane draws only inside the home (§7.4: "clipped to the apartment outline").
    const mask = roomMask([{ polygon: home.outline }])
    this.texture = maskTexture(mask)
    const { min, max } = bounds(home.outline)
    const [halfX, halfY, halfZ] = [(max[0] - min[0]) / 2, (max[1] - min[1]) / 2, home.ceiling / 2]
    this.plane = planeMaterial({
      mask,
      texture: this.texture,
      ceilingM: home.ceiling,
      // In three's world (plan.ts's toWorld): x, then up, then the plan's y.
      centre: [min[0] + halfX, halfZ, min[1] + halfY],
      reachM: Math.hypot(halfX, halfY, halfZ),
    })
  }

  /** The pose's scale and the way the camera looks. */
  setView(pose: CameraPose): void {
    this.particle.uniforms.pxPerM.value = pose.zoom
    this.plane.uniforms.back.value.set(...pose.back)
  }

  dispose(): void {
    for (const item of [this.particle, this.ring, this.plane, this.texture]) item.dispose()
  }
}

/** The attributes each kind's batch feeds, in the writer's order of its arrays. */
const NAMES = {
  particles: ['centre', 'colour', 'size'],
  rings: ['centre', 'colour', 'shape'],
  planes: ['point', 'planeNormal', 'ray', 'colour', 'width'],
} as const

type Kind = keyof typeof NAMES

interface Drawn {
  mesh: InstancedMesh | null
  generation: number
  attributes: InstancedBufferAttribute[]
}

export class FxMeshes {
  readonly group = new Group()
  private readonly writer: FxWriter
  private readonly materials: Record<Kind, ShaderMaterial>
  private readonly drawn: Record<Kind, Drawn> = {
    particles: { mesh: null, generation: -1, attributes: [] },
    rings: { mesh: null, generation: -1, attributes: [] },
    planes: { mesh: null, generation: -1, attributes: [] },
  }

  constructor(writer: FxWriter, materials: FxMaterials) {
    this.writer = writer
    this.materials = { particles: materials.particle, rings: materials.ring, planes: materials.plane }
  }

  /** After FxWriter.write(): draws as many of each as it wrote, sending them to the GPU. */
  update(): void {
    for (const kind of Object.keys(NAMES) as Kind[]) this.updateKind(kind, this.writer[kind])
  }

  private updateKind(kind: Kind, batch: FxBatch): void {
    const drawn = this.drawn[kind]
    if (drawn.generation !== batch.generation) this.remake(kind, batch)
    if (drawn.mesh === null) return
    drawn.mesh.count = batch.count
    drawn.mesh.visible = batch.count > 0
    for (const attribute of drawn.attributes) attribute.needsUpdate = true
  }

  /** New arrays, larger ones: a new mesh over them. */
  private remake(kind: Kind, batch: FxBatch): void {
    const drawn = this.drawn[kind]
    this.drop(drawn)
    drawn.generation = batch.generation
    if (batch.capacity === 0) return
    const geometry = new PlaneGeometry(2, 2)
    drawn.attributes = batch.arrays.map((array, i) => {
      const attribute = new InstancedBufferAttribute(array, array.length / batch.capacity).setUsage(DynamicDrawUsage)
      geometry.setAttribute(NAMES[kind][i], attribute)
      return attribute
    })
    const mesh = new InstancedMesh(geometry, this.materials[kind], batch.capacity)
    // The instance matrices stay identity, so three's bounds would be wrong: never cull.
    mesh.frustumCulled = false
    drawn.mesh = mesh
    this.group.add(mesh)
  }

  private drop(drawn: Drawn): void {
    if (drawn.mesh === null) return
    this.group.remove(drawn.mesh)
    drawn.mesh.geometry.dispose()
    drawn.mesh.dispose()
    drawn.mesh = null
    drawn.attributes = []
  }

  dispose(): void {
    for (const drawn of Object.values(this.drawn)) this.drop(drawn)
  }
}
```

- [ ] **Step 5: One draw tick, and the layer**

Create `web/src/stage/scene/draw-list.ts`:

```ts
// The canvas's layers draw on the stage's one cadence (cadence.ts): StageScene asks each in turn to
// write what's new into its meshes, and renders once in that animation frame if any did. Two layers
// each on a cadence of their own would render the canvas twice.
/** Writes what's new into a layer's meshes; whether it wrote anything. */
export type Drawer = () => boolean

export class DrawList {
  private readonly drawers = new Set<Drawer>()

  /** Adds `drawer`; returns what takes it out. */
  add(drawer: Drawer): () => void {
    this.drawers.add(drawer)
    return () => void this.drawers.delete(drawer)
  }

  /** Every layer draws; whether any wrote something, so the canvas has something new to show. */
  draw(): boolean {
    let changed = false
    for (const drawer of this.drawers) changed = drawer() || changed
    return changed
  }
}
```

Create `web/src/stage/scene/fx-layer.tsx`:

```tsx
// "Effects in space" on the canvas (§7.4): the fx store's picture of the zones the stage picks, drawn
// on the stage's cadence beside the lights (draw-list.ts). Pictures never pass through React: the
// layer writes the store's newest into its meshes' arrays when the cadence asks, and a new pick (the
// composer's preview, focus's zone) is written at once.
import { useThree } from '@react-three/fiber'
import { useEffect, useLayoutEffect, useMemo } from 'react'
import type { Home } from '@/api/contract'
import { fx } from '@/api/live'
import type { CameraPose } from '../camera'
import { FxWriter, type FxPick } from '../fx-writer'
import type { DrawList } from './draw-list'
import { FxMaterials, FxMeshes } from './fx-meshes'

export interface FxLayerProps {
  home: Pick<Home, 'outline' | 'ceiling'>
  /** Which zones' fx it draws. */
  pick: FxPick
  pose: CameraPose
  drawList: DrawList
}

export function FxLayer({ home, pick, pose, drawList }: FxLayerProps) {
  const { outline, ceiling } = home
  const materials = useMemo(() => new FxMaterials({ outline, ceiling }), [outline, ceiling])
  const writer = useMemo(() => new FxWriter(), [])
  const meshes = useMemo(() => new FxMeshes(writer, materials), [writer, materials])
  const invalidate = useThree((state) => state.invalidate)
  useEffect(() => () => materials.dispose(), [materials])
  // Gone, the picture goes with it: the canvas draws once more without it.
  useEffect(
    () => () => {
      meshes.dispose()
      invalidate()
    },
    [meshes, invalidate],
  )
  useLayoutEffect(() => {
    materials.setView(pose)
    invalidate()
  }, [materials, pose, invalidate])
  useLayoutEffect(() => {
    writer.write(fx, pick)
    meshes.update()
    invalidate()
  }, [writer, meshes, pick, invalidate])
  useLayoutEffect(
    () =>
      drawList.add(() => {
        if (!writer.write(fx, pick)) return false
        meshes.update()
        return true
      }),
    [drawList, writer, meshes, pick],
  )
  return <primitive object={meshes.group} />
}
```

```diff
diff --git a/web/src/stage/cadence.ts b/web/src/stage/cadence.ts
index 79edeb8..4fbed03 100644
--- a/web/src/stage/cadence.ts
+++ b/web/src/stage/cadence.ts
@@ -1,12 +1,12 @@
-// When the stage draws (§7.5): only once a frame has arrived since its last draw, and no more often
-// than its rate, the stage behaviour's cadenceMs (behaviour.ts); none at all while that's null (§7.6
-// frozen). It rides the browser's animation frames, so a hidden tab draws nothing (§7.5, "pause
-// rendering when the tab is hidden"), and after an animation frame with nothing new to draw it
-// sleeps, asking for none until the frame store has another frame. It is the stage's one draw tick:
-// the canvas draws on it, and whatever else shows the frames (the light tooltip) follows it through
-// onStageDraw().
+// When the stage draws (§7.5): only once a frame or a picture of the effects in space (§7.4) has
+// arrived since its last draw, and no more often than its rate, the stage behaviour's cadenceMs
+// (behaviour.ts); none at all while that's null (§7.6 frozen). It rides the browser's animation
+// frames, so a hidden tab draws nothing (§7.5, "pause rendering when the tab is hidden"), and after
+// an animation frame with nothing new to draw it sleeps, asking for none until the frame store has
+// another frame or the fx store another picture. It is the stage's one draw tick: the canvas draws
+// on it, and whatever else shows the frames (the light tooltip) follows it through onStageDraw().
 import { useEffect, useEffectEvent } from 'react'
-import { frames } from '@/api/live'
+import { frames, fx } from '@/api/live'
 
 /** Half a 60 Hz animation frame: the slack until the cadence has measured the screen's. */
 const DEFAULT_SLACK_MS = 1000 / 60 / 2
@@ -28,7 +28,7 @@ export class Cadence {
     this.intervalMs = intervalMs
   }
 
-  /** `now` is the animation frame's time; `version` the frame store's. */
+  /** `now` is the animation frame's time; `version` what the stage draws from's (drawnVersion()). */
   due(now: number, version: number): boolean {
     if (this.frameAt !== null && now > this.frameAt) this.slackMs = (now - this.frameAt) / 2
     this.frameAt = now
@@ -51,6 +51,24 @@ export class Cadence {
   }
 }
 
+/** What the stage draws from: both stores' versions only grow, so their sum moves whenever either does. */
+const drawnVersion = () => frames.version + fx.version
+
+/** Calls `wake` once, at the next frame or the next picture, whichever comes first; returns what stops it waiting. */
+function onNextDrawable(wake: () => void): () => void {
+  const stop = () => {
+    stopFrame()
+    stopFx()
+  }
+  const woken = () => {
+    stop()
+    wake()
+  }
+  const stopFrame = frames.onNextFrame(woken)
+  const stopFx = fx.onNextChange(woken)
+  return stop
+}
+
 const listeners = new Set<() => void>()
 
 /** Calls `listener` right after each of the stage's draws; returns what stops it. */
@@ -74,11 +92,12 @@ export function useCadence(intervalMs: number | null, draw: (now: number) => voi
     const cadence = new Cadence(intervalMs)
     let stopWaiting = () => {}
     const tick = (now: number) => {
-      if (cadence.due(now, frames.version)) due(now)
-      else if (cadence.drawn(frames.version)) {
+      const version = drawnVersion()
+      if (cadence.due(now, version)) due(now)
+      else if (cadence.drawn(version)) {
         // A whole animation frame with nothing new to draw: nothing is streaming.
         cadence.sleep()
-        stopWaiting = frames.onNextFrame(() => (handle = requestAnimationFrame(tick)))
+        stopWaiting = onNextDrawable(() => (handle = requestAnimationFrame(tick)))
         return
       }
       handle = requestAnimationFrame(tick)
diff --git a/web/src/stage/scene/light-layer.tsx b/web/src/stage/scene/light-layer.tsx
index 5ce61c4..9e858dd 100644
--- a/web/src/stage/scene/light-layer.tsx
+++ b/web/src/stage/scene/light-layer.tsx
@@ -3,14 +3,15 @@
 // a light shows is written into them in place, and drawn at once. Frames never pass through React:
 // the light layer draws on the stage's cadence (cadence.ts), writing the frame store's latest bytes
 // into the meshes' own arrays, then drawing the canvas in that animation frame — unless the write
-// changed nothing (frames with the same bytes), when there's nothing to upload or draw.
+// changed nothing (frames with the same bytes), when there's nothing to upload or draw. The cadence
+// is StageScene's, which the effects in space draw on too (draw-list.ts).
 import { useThree } from '@react-three/fiber'
 import { useEffect, useLayoutEffect, useMemo } from 'react'
 import { frames } from '@/api/live'
-import { useCadence } from '../cadence'
 import type { CameraPose } from '../camera'
 import type { FrameWriter, WriterEntry } from '../frame-writer'
 import type { RoomMask } from '../room-mask'
+import type { DrawList } from './draw-list'
 import { LightMaterials, LightMeshes } from './light-meshes'
 
 export interface LightLayerProps {
@@ -19,15 +20,14 @@ export interface LightLayerProps {
   entries: readonly WriterEntry[]
   mask: RoomMask
   pose: CameraPose
-  /** The stage behaviour's (behaviour.ts): null while frames don't redraw the stage. */
-  cadenceMs: number | null
+  /** The stage's cadence's layers: this one writes the newest frames there. */
+  drawList: DrawList
 }
 
-export function LightLayer({ writer, entries, mask, pose, cadenceMs }: LightLayerProps) {
+export function LightLayer({ writer, entries, mask, pose, drawList }: LightLayerProps) {
   const materials = useMemo(() => new LightMaterials(mask), [mask])
   const meshes = useMemo(() => new LightMeshes(writer, materials), [writer, materials])
   const invalidate = useThree((state) => state.invalidate)
-  const advance = useThree((state) => state.advance)
   useEffect(() => () => materials.dispose(), [materials])
   useEffect(() => () => meshes.dispose(), [meshes])
   useLayoutEffect(() => {
@@ -41,11 +41,15 @@ export function LightLayer({ writer, entries, mask, pose, cadenceMs }: LightLaye
     meshes.update()
     invalidate()
   }, [writer, meshes, entries, invalidate])
-  useCadence(cadenceMs, (now) => {
-    if (!writer.write(frames)) return
-    meshes.update()
-    advance(now)
-  })
+  useLayoutEffect(
+    () =>
+      drawList.add(() => {
+        if (!writer.write(frames)) return false
+        meshes.update()
+        return true
+      }),
+    [drawList, writer, meshes],
+  )
   return (
     <>
       {meshes.pools !== null && <primitive object={meshes.pools} />}
diff --git a/web/src/stage/scene/stage-scene.tsx b/web/src/stage/scene/stage-scene.tsx
index e45c54c..eb49fb2 100644
--- a/web/src/stage/scene/stage-scene.tsx
+++ b/web/src/stage/scene/stage-scene.tsx
@@ -1,12 +1,17 @@
-// Everything on the stage's canvas: the camera where the pose puts it (§7.2), the static home, and
-// the lights, which draw on the stage's cadence (§7.5).
+// Everything on the stage's canvas: the camera where the pose puts it (§7.2), the static home, the
+// lights, and the effects in space (§7.4) while the stage draws them. The lights and the effects draw
+// on the stage's one cadence (§7.5): each writes what's new, and the canvas renders once if any did.
 import { useThree } from '@react-three/fiber'
-import { useLayoutEffect } from 'react'
+import { useLayoutEffect, useMemo } from 'react'
 import type { OrthographicCamera } from 'three'
 import type { Home } from '@/api/contract'
+import { useCadence } from '../cadence'
 import { applyPose, type CameraPose } from '../camera'
+import type { FxPick } from '../fx-writer'
 import type { FrameWriter, WriterEntry } from '../frame-writer'
 import type { RoomMask } from '../room-mask'
+import { DrawList } from './draw-list'
+import { FxLayer } from './fx-layer'
 import { LightLayer } from './light-layer'
 import { StaticHome } from './static-home'
 
@@ -19,20 +24,28 @@ export interface StageSceneProps {
   pose: CameraPose
   /** The stage behaviour's (behaviour.ts): null while frames don't redraw the stage. */
   cadenceMs: number | null
+  /** Which zones' effects in space it draws (§7.4), or null while it draws none. */
+  fx: FxPick | null
 }
 
-export function StageScene({ home, writer, entries, mask, pose, cadenceMs }: StageSceneProps) {
+export function StageScene({ home, writer, entries, mask, pose, cadenceMs, fx }: StageSceneProps) {
   const camera = useThree((state) => state.camera)
   const invalidate = useThree((state) => state.invalidate)
+  const advance = useThree((state) => state.advance)
+  const drawList = useMemo(() => new DrawList(), [])
   useLayoutEffect(() => {
     // The canvas is made orthographic (stage-canvas.tsx).
     applyPose(camera as OrthographicCamera, pose)
     invalidate()
   }, [camera, pose, invalidate])
+  useCadence(cadenceMs, (now) => {
+    if (drawList.draw()) advance(now)
+  })
   return (
     <>
       <StaticHome home={home} pose={pose} />
-      <LightLayer writer={writer} entries={entries} mask={mask} pose={pose} cadenceMs={cadenceMs} />
+      <LightLayer writer={writer} entries={entries} mask={mask} pose={pose} drawList={drawList} />
+      {fx !== null && <FxLayer home={home} pick={fx} pose={pose} drawList={drawList} />}
     </>
   )
 }
diff --git a/web/src/stage/stage-view.tsx b/web/src/stage/stage-view.tsx
index 77a0908..9d0bb7d 100644
--- a/web/src/stage/stage-view.tsx
+++ b/web/src/stage/stage-view.tsx
@@ -214,6 +214,7 @@ export function StageView({ data, variant, route, roomTo, roomState, outlined =
                 mask={mask}
                 pose={pose}
                 cadenceMs={behaviour.cadenceMs}
+                fx={null}
               />
               <StageSvg pose={pose} marks={marks} labels={labels} sun={sunDrawn} outline={outline} compose={composeShape} />
               {focusZone !== undefined && framing !== null && (
diff --git a/web/src/test/stage.ts b/web/src/test/stage.ts
index 6246a13..c3547d0 100644
--- a/web/src/test/stage.ts
+++ b/web/src/test/stage.ts
@@ -43,7 +43,7 @@ export function stageWriter(
 /** What StageView hands the canvas for a scenario's home and lights: at Main.png's size, fitted, and not drawing. */
 export function sceneProps(name: ScenarioName = 'hero', overrides: Partial<StageSceneProps> = {}): StageSceneProps {
   const { home, lights } = buildScenario(name, HERO_NOW)
-  return { home, ...stageWriter(lights, { rooms: home.rooms }), mask: roomMask(home.rooms), pose: heroPose(), cadenceMs: null, ...overrides }
+  return { home, ...stageWriter(lights, { rooms: home.rooms }), mask: roomMask(home.rooms), pose: heroPose(), cadenceMs: null, fx: null, ...overrides }
 }
 
 /** A scenario's REST answers and live store, as Live finds them once it's connected. */
```

- [ ] **Step 6: Run them to see them pass**

Run: `(cd web && npx vitest run src/stage/cadence.test.ts src/stage/scene/fx-meshes.test.ts src/stage/scene/stage-scene.test.tsx)`
Expected: `Test Files  3 passed (3)`, `Tests  26 passed (26)`.

jsdom has no WebGL, so these tests check the meshes, the counts and the renders, not the shaders. The shaders compile and draw in Chromium in Task 8 (the e2e switch test and the screenshots). If one fails to compile there, the browser's console names the line.

- [ ] **Step 7: The gate**

```bash
(cd web && npm test 2>&1 | grep -E 'Test Files|Tests ' && npm run lint && npx tsc -b && echo "tsc ok")
```

Expected: `Test Files  106 passed (106)`, `Tests  1119 passed (1119)`, lint clean, "tsc ok".

- [ ] **Step 8: Commit**

```bash
git add web/src/stage/scene web/src/stage/cadence.ts web/src/stage/cadence.test.ts web/src/stage/stage-view.tsx web/src/test/stage.ts
git commit -m "feat(web): draw the effects in space on the stage's cadence"
```

---

### Task 7: The switch, and the stage's pick of zones

§8.1's "Effects in space" switch in the tools, remembered per route (ruling 2); where the effects are drawn (rulings 3 and 4); which zones' effects (rulings 5 and 6); and the subscription while they're drawn.

**Files:**
- Modify: `web/src/stage/behaviour.ts`, `web/src/stage/view-memory.ts`, `web/src/stage/overlays/stage-tools.tsx`, `web/src/stage/stage-view.tsx`
- Test: `web/src/stage/behaviour.test.ts`, `web/src/stage/view-memory.test.ts`, `web/src/stage/overlays/overlays.test.tsx`, `web/src/stage/stage-view.test.tsx`, `web/src/api/use-fx.test.ts` (create)

**Interfaces:**
- Consumes: Task 2's `useFxStream()`; Task 5's `FxPick`; Task 6's `StageSceneProps.fx`; `Switch` (`src/design/switch.tsx`).
- Produces:
  - `StageOptions.effects` and `StageBehaviour.effects`.
  - `StoredView.effects`, default true.
  - `StageToolsProps.effects` and `onEffects`.
  - `StageView` passes `fx={drawsFx ? fxPick : null}` to the canvas.

- [ ] **Step 1: Read the spec and the renders**

Read §7.4, §7.6, §8.1's overlay line, §8.10's stage and §5.4's reduced motion. Look at `Main.png`'s top left once, the tools row: `3D | Plan`, "Effects in space", "Labels"; and at `Phone-Live.png`, whose stage has no tools and draws the fireflies. Read the tools' markup in `Main.html` for their order. Then read `behaviour.ts`, `view-memory.ts`, `overlays/stage-tools.tsx` and `stage-view.tsx` (`previewed`, `focusZone`, `running`, `webgl`, `pose`).

- [ ] **Step 2: Write the failing tests**

Create `web/src/api/use-fx.test.ts`:

```ts
import { renderHook } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { fakeSockets } from '@/test/fake-socket'
import { startDataLayer } from './live'
import { useFxStream } from './use-fx'

describe('useFxStream', () => {
  it('asks for the fx channel while the stage draws the effects in space, and lets go when it stops or goes', () => {
    const { sockets, open } = fakeSockets()
    startDataLayer({ openSocket: open, url: 'ws://test/ws' })
    sockets[0].open()
    const asked = () => sockets[0].sent.filter((command) => command.action === 'subscribe_fx').map((command) => command.on)
    const { rerender, unmount } = renderHook(({ on }) => useFxStream(on), { initialProps: { on: false } })
    expect(asked()).toEqual([])
    rerender({ on: true })
    rerender({ on: false })
    rerender({ on: true })
    unmount()
    expect(asked()).toEqual([true, false, true, false])
  })
})
```

```diff
diff --git a/web/src/stage/behaviour.test.ts b/web/src/stage/behaviour.test.ts
index ff10a93..e5facc7 100644
--- a/web/src/stage/behaviour.test.ts
+++ b/web/src/stage/behaviour.test.ts
@@ -4,7 +4,7 @@ import { stageBehaviour, type StageOptions } from './behaviour'
 import { SPEC } from './design-numbers'
 
 const behaviour = (options: Partial<StageOptions>) =>
-  stageBehaviour({ mode: 'live', variant: 'desktop', reducedMotion: false, labels: true, ...options })
+  stageBehaviour({ mode: 'live', variant: 'desktop', reducedMotion: false, labels: true, effects: true, ...options })
 
 describe("the stage's behaviour in each mode (§7.6) and on the phone (§8.10)", () => {
   it('is all there on desktop Live, labels as the Labels switch says', () => {
@@ -15,6 +15,7 @@ describe("the stage's behaviour in each mode (§7.6) and on the phone (§8.10)",
       overlays: true,
       legend: true,
       labels: true,
+      effects: true,
       sunLabel: true,
       greyed: false,
       previewTag: null,
@@ -33,6 +34,7 @@ describe("the stage's behaviour in each mode (§7.6) and on the phone (§8.10)",
       overlays: false,
       legend: false,
       labels: false,
+      effects: true,
       sunLabel: false,
       greyed: false,
       previewTag: null,
@@ -51,6 +53,7 @@ describe("the stage's behaviour in each mode (§7.6) and on the phone (§8.10)",
       overlays: true,
       legend: true,
       labels: true,
+      effects: true,
       sunLabel: true,
       greyed: false,
       previewTag: 'card',
@@ -73,6 +76,20 @@ describe("the stage's behaviour in each mode (§7.6) and on the phone (§8.10)",
     expect(behaviour({ variant: 'phone' }).cadenceMs).toBeCloseTo(1000 / SPEC.phoneFps)
   })
 
+  // §7.4: the "Effects in space" switch, default on (view-memory.ts). The phone has no switch and draws them
+  // (Phone-Live, Phone-Zone); the Reconnecting renders draw none, and §5.4's reduced motion stops particles.
+  it('draws the effects in space as the switch says, always on the phone, and never while frozen or still', () => {
+    expect(behaviour({ effects: false }).effects).toBe(false)
+    expect(behaviour({ mode: 'compose', effects: false }).effects).toBe(false)
+    expect(behaviour({ mode: 'focus', effects: false }).effects).toBe(false)
+    expect(behaviour({ variant: 'phone', effects: false }).effects).toBe(true)
+    expect(behaviour({ mode: 'focus', variant: 'phone', effects: false }).effects).toBe(true)
+    expect(behaviour({ mode: 'frozen' }).effects).toBe(false)
+    expect(behaviour({ mode: 'frozen', variant: 'phone' }).effects).toBe(false)
+    expect(behaviour({ reducedMotion: true }).effects).toBe(false)
+    expect(behaviour({ variant: 'phone', reducedMotion: true }).effects).toBe(false)
+  })
+
   // §5.4: "The stage still updates light colours, at most once per second."
   it('draws slowly with reduced motion', () => {
     expect(behaviour({ reducedMotion: true }).cadenceMs).toBe(LIVE_SPEC.reducedMotionMs)
diff --git a/web/src/stage/overlays/overlays.test.tsx b/web/src/stage/overlays/overlays.test.tsx
index fafdabe..269523b 100644
--- a/web/src/stage/overlays/overlays.test.tsx
+++ b/web/src/stage/overlays/overlays.test.tsx
@@ -151,8 +151,8 @@ describe('the light tooltip (§8.1)', () => {
     return null
   }
 
-  function renderOnStage(options: Omit<StageOptions, 'mode' | 'labels'>) {
-    const { cadenceMs } = stageBehaviour({ mode: 'live', labels: true, ...options })
+  function renderOnStage(options: Omit<StageOptions, 'mode' | 'labels' | 'effects'>) {
+    const { cadenceMs } = stageBehaviour({ mode: 'live', labels: true, effects: true, ...options })
     render(
       <>
         <DrawTick cadenceMs={cadenceMs} />
diff --git a/web/src/stage/stage-view.test.tsx b/web/src/stage/stage-view.test.tsx
index 327e38e..00eb08b 100644
--- a/web/src/stage/stage-view.test.tsx
+++ b/web/src/stage/stage-view.test.tsx
@@ -23,7 +23,7 @@ import { STAGE_LABEL } from './stage-pending'
 import { sunPosition, sunScene } from './sun'
 import Stage from './stage'
 import type { StageVariant } from './stage-view'
-import { readStageView } from './view-memory'
+import { DEFAULT_STAGE_VIEW, readStageView, writeStageView } from './view-memory'
 import { hasWebGL2 } from './webgl'
 import { zonePolygons } from './zone-shape'
 
@@ -71,6 +71,8 @@ describe('the stage on Live (§7, §8.1)', () => {
   it("lays the overlays out in Main.html's order", async () => {
     const { state } = await openLive()
     const overlays = [
+      screen.getByRole('group', { name: 'View' }),
+      screen.getByRole('switch', { name: 'Effects in space' }),
       screen.getByRole('switch', { name: 'Labels' }),
       screen.getByText(sunPosition(state.inputs.sun)!),
       screen.getByRole('list', { name: 'What the lights show' }),
@@ -132,6 +134,19 @@ describe('the stage on Live (§7, §8.1)', () => {
     expect(readStageView(window.localStorage, 'live').labels).toBe(false)
   })
 
+  // §7.4: "This is the "Effects in space" toggle (default on)"; Main.html draws it on.
+  it('draws the effects in space of every running zone with the switch on, and hides them with it, remembered for Live', async () => {
+    await openLive()
+    const effects = screen.getByRole('switch', { name: 'Effects in space' })
+    expect(effects).toHaveAttribute('aria-checked', 'true')
+    expect(drawn.props!.fx).toEqual({ preview: null, hidden: new Set() })
+    await userEvent.click(effects)
+    expect(drawn.props!.fx).toBeNull()
+    expect(readStageView(window.localStorage, 'live').effects).toBe(false)
+    await userEvent.click(effects)
+    expect(drawn.props!.fx).not.toBeNull()
+  })
+
   it('turns to Plan, orbits a step at a time, zooms in to the last step, and fits again', async () => {
     await openLive()
     await userEvent.click(screen.getByRole('button', { name: 'Plan' }))
@@ -153,18 +168,22 @@ describe('the stage on Live (§7, §8.1)', () => {
     act(() => liveStore.setState({ connection: { status: 'reconnecting', attempt: 1 } }))
     // No draws for frames (§7.6 "no animation"), and the picture greyed.
     expect(canvas().dataset.cadence).toBe('null')
+    // State-Reconnecting draws no effects in space.
+    expect(drawn.props!.fx).toBeNull()
     expect(picture().style.filter).toBe(`grayscale(${SPEC.frozen.grayscale}) brightness(${SPEC.frozen.brightness})`)
     expect(screen.queryByRole('navigation', { name: 'Rooms' })).not.toBeInTheDocument()
     // State-Reconnecting.png's stage is the greyed picture alone: "Controls come back when the link does".
     const overlays = () => [
+      screen.queryByRole('switch', { name: 'Effects in space' }),
       screen.queryByRole('switch', { name: 'Labels' }),
       screen.queryByRole('button', { name: 'Rotate view' }),
       screen.queryByRole('list', { name: 'What the lights show' }),
       screen.queryByText(sunPosition(liveStore.getState().inputs!.sun)!),
     ]
-    expect(overlays()).toEqual([null, null, null, null])
+    expect(overlays()).toEqual([null, null, null, null, null])
     act(() => liveStore.setState({ connection: live }))
     expect(canvas().dataset.cadence).toBe(String(1000 / SPEC.target.fps))
+    expect(drawn.props!.fx).not.toBeNull()
     expect(picture().style.filter).toBe('')
     expect(screen.getByRole('navigation', { name: 'Rooms' })).toBeInTheDocument()
     for (const overlay of overlays()) expect(overlay).toBeInTheDocument()
@@ -262,7 +281,11 @@ describe('the stage on Live (§7, §8.1)', () => {
 
   it("draws the phone's stage without labels or overlays", async () => {
     setViewportWidth(LIVE_SPEC.phoneStage.width)
+    // Phone-Live draws the effects in space with no switch, whatever the desktop's says.
+    writeStageView(window.localStorage, 'live', { ...DEFAULT_STAGE_VIEW, effects: false })
     const { state } = await openLive()
+    expect(screen.queryByRole('switch', { name: 'Effects in space' })).not.toBeInTheDocument()
+    expect(drawn.props!.fx).toEqual({ preview: null, hidden: new Set() })
     expect(screen.queryByText(state.home.rooms[0].name)).not.toBeInTheDocument()
     expect(screen.queryByRole('switch', { name: 'Labels' })).not.toBeInTheDocument()
     expect(screen.queryByRole('list', { name: 'What the lights show' })).not.toBeInTheDocument()
@@ -345,6 +368,8 @@ describe('the stage in focus (§7.6)', () => {
     expect(screen.queryByRole('navigation', { name: 'Rooms' })).not.toBeInTheDocument()
     expect(screen.queryByRole('switch', { name: 'Labels' })).not.toBeInTheDocument()
     expect(picture().querySelector('[data-vignette]')).not.toBeNull()
+    // Phone-Zone draws the zone's effects in space: the zones with no light in it draw none.
+    expect(drawn.props!.fx).toEqual({ preview: null, hidden: new Set(['home', 'office']) })
 
     act(() => liveStore.setState({ connection: { status: 'reconnecting', attempt: 1 } }))
     expect(drawn.props!.pose).toEqual(framed)
@@ -420,8 +445,12 @@ describe('the stage in compose (§7.6)', () => {
     expect(screen.queryByText(sunPosition(state.inputs.sun)!)).not.toBeInTheDocument()
     expect(screen.queryByRole('navigation', { name: 'Rooms' })).not.toBeInTheDocument()
 
+    // The preview's effects in space are drawn on the zone, in place of those of the look its lights run.
+    expect(drawn.props!.fx).toEqual({ preview: 'living', hidden: new Set(['living']) })
+
     // The preview ends: the lights draw the live stream again, and the card goes.
     await act(() => router.navigate('/live/put?zone=living&look=embers', { replace: true }))
+    expect(drawn.props!.fx).toEqual({ preview: null, hidden: new Set() })
     expect(streams(zone.lights)).toEqual({ zone: new Set(['live']), rest: new Set(['live']) })
     expect(stage.getByText(lookName('fireflies'))).toHaveClass('fill-text')
     expect(document.querySelector('[data-preview-card]')).toBeNull()
diff --git a/web/src/stage/view-memory.test.ts b/web/src/stage/view-memory.test.ts
index d7590fe..5b8e3db 100644
--- a/web/src/stage/view-memory.test.ts
+++ b/web/src/stage/view-memory.test.ts
@@ -20,7 +20,7 @@ function throwingStorage(): Storage {
   return { length: 0, clear: refuse, getItem: refuse, key: refuse, removeItem: refuse, setItem: refuse }
 }
 
-const PLAN: StoredView = { view: { mode: 'plan', rotateDeg: -SPEC.rotate.stepDeg, zoom: ZOOM_STEPS[2] }, labels: false }
+const PLAN: StoredView = { view: { mode: 'plan', rotateDeg: -SPEC.rotate.stepDeg, zoom: ZOOM_STEPS[2] }, labels: false, effects: false }
 
 beforeEach(() => {
   window.localStorage.clear()
@@ -37,12 +37,12 @@ describe('the remembered view (§7.2)', () => {
   // Review focus 5: an old app's, another tab's or a hand-edited value; private mode; a full disk.
   it("ignores a stored view it can't read, and survives storage that throws", () => {
     const storage = window.localStorage
-    for (const junk of ['{', '"plan"', '[]', 'null', '{"mode":"top","rotateDeg":7,"zoom":9,"labels":"yes"}']) {
+    for (const junk of ['{', '"plan"', '[]', 'null', '{"mode":"top","rotateDeg":7,"zoom":9,"labels":"yes","effects":1}']) {
       storage.setItem('dj-ledfx:stage-view:live', junk)
       expect(readStageView(storage, 'live')).toEqual(DEFAULT_STAGE_VIEW)
     }
     storage.setItem('dj-ledfx:stage-view:live', JSON.stringify({ mode: 'plan', rotateDeg: 'x', zoom: ZOOM_STEPS[1] }))
-    expect(readStageView(storage, 'live')).toEqual({ view: { mode: 'plan', rotateDeg: 0, zoom: ZOOM_STEPS[1] }, labels: true })
+    expect(readStageView(storage, 'live')).toEqual({ view: { mode: 'plan', rotateDeg: 0, zoom: ZOOM_STEPS[1] }, labels: true, effects: true })
 
     const blocked = throwingStorage()
     expect(readStageView(blocked, 'live')).toEqual(DEFAULT_STAGE_VIEW)
@@ -50,6 +50,14 @@ describe('the remembered view (§7.2)', () => {
     expect(readStageView(null, 'live')).toEqual(DEFAULT_STAGE_VIEW)
   })
 
+  // §7.4: the "Effects in space" toggle is "default on"; a view stored before it existed keeps it on.
+  it('keeps the effects in space on unless they were turned off', () => {
+    const storage = window.localStorage
+    expect(DEFAULT_STAGE_VIEW.effects).toBe(true)
+    storage.setItem('dj-ledfx:stage-view:live', JSON.stringify({ mode: 'plan', rotateDeg: 0, zoom: 1, labels: false }))
+    expect(readStageView(storage, 'live').effects).toBe(true)
+  })
+
   it('steps the rotation round within its range, and the zoom up to its last step', () => {
     const { stepDeg, maxDeg } = SPEC.rotate
     expect(nextRotation(0)).toBe(stepDeg)
```

- [ ] **Step 3: Run them to see them fail**

Run: `(cd web && npx vitest run src/api/use-fx.test.ts src/stage/behaviour.test.ts src/stage/view-memory.test.ts src/stage/overlays/overlays.test.tsx src/stage/stage-view.test.tsx)`
Expected: FAIL: 14 tests fail, among them `Unable to find an accessible element with the role "switch" and name "Effects in space"`, and the behaviour and view-memory objects missing `effects`.

- [ ] **Step 4: Write the code**

```diff
diff --git a/web/src/stage/behaviour.ts b/web/src/stage/behaviour.ts
index 82c9f6c..90514a7 100644
--- a/web/src/stage/behaviour.ts
+++ b/web/src/stage/behaviour.ts
@@ -20,6 +20,8 @@ export interface StageOptions {
   reducedMotion: boolean
   /** The Labels switch (§8.1). */
   labels: boolean
+  /** The "Effects in space" switch (§7.4, §8.1). */
+  effects: boolean
 }
 
 export interface StageBehaviour {
@@ -49,6 +51,12 @@ export interface StageBehaviour {
   outlinePx: number
   /** The rooms' labels (§7.6). */
   labels: boolean
+  /**
+   * §7.4's effects in space, drawn faintly in the room: as the switch says, and always on the phone, which
+   * has no switch (§8.10: Phone-Live and Phone-Zone draw them). §7.6 frozen has "no animation", and the
+   * Reconnecting renders draw none; §5.4's reduced motion stops particles, and so stops them all.
+   */
+  effects: boolean
   /** The sun's mono label (§7.4); Phone-Live.png draws the sun without it. */
   sunLabel: boolean
   /** The picture greyed as SPEC.frozen says (§7.6 frozen). */
@@ -66,7 +74,7 @@ export interface StageBehaviour {
   cadenceMs: number | null
 }
 
-export function stageBehaviour({ mode, variant, reducedMotion, labels }: StageOptions): StageBehaviour {
+export function stageBehaviour({ mode, variant, reducedMotion, labels, effects }: StageOptions): StageBehaviour {
   const live = mode === 'live'
   const compose = mode === 'compose'
   const phone = variant === 'phone'
@@ -80,6 +88,7 @@ export function stageBehaviour({ mode, variant, reducedMotion, labels }: StageOp
     legend: !phone && (live || compose),
     outlinePx: phone ? LIVE_RENDER.phoneOutlinePx : SPEC.compose.outlinePx,
     labels: !phone && !focus && labels,
+    effects: mode !== 'frozen' && !reducedMotion && (phone || effects),
     sunLabel: !phone && !focus,
     greyed: mode === 'frozen',
     previewTag: compose ? (phone ? 'tag' : 'card') : null,
diff --git a/web/src/stage/overlays/stage-tools.tsx b/web/src/stage/overlays/stage-tools.tsx
index 0c70543..f391b0b 100644
--- a/web/src/stage/overlays/stage-tools.tsx
+++ b/web/src/stage/overlays/stage-tools.tsx
@@ -1,6 +1,7 @@
-// §8.1 top left: `3D | Plan` and the Labels switch. "Effects in space" waits for the fx stream
-// (§7.4: "until that exists the toggle is hidden"). Live's preview-only label takes the stage's top and
-// sets `--stage-top-shift` to its foot, so the tools start under it.
+// §8.1 top left: `3D | Plan`, the "Effects in space" switch (§7.4) and the Labels switch, in Main.html's
+// order. The switch shows now the fx stream exists (§7.4: "until that exists the toggle is hidden").
+// Live's preview-only label takes the stage's top and sets `--stage-top-shift` to its foot, so the
+// tools start under it.
 import { Segmented } from '@/design/segmented'
 import { Switch } from '@/design/switch'
 import type { ViewMode } from '../camera'
@@ -14,15 +15,18 @@ const MODES = [
 export interface StageToolsProps {
   mode: ViewMode
   onMode: (mode: ViewMode) => void
+  effects: boolean
+  onEffects: (effects: boolean) => void
   labels: boolean
   onLabels: (labels: boolean) => void
 }
 
-export function StageTools({ mode, onMode, labels, onLabels }: StageToolsProps) {
+export function StageTools({ mode, onMode, effects, onEffects, labels, onLabels }: StageToolsProps) {
   const { leftPx, topPx, gapPx } = RENDER.tools
   return (
     <div className="absolute flex items-center" style={{ left: leftPx, top: `calc(var(--stage-top-shift, 0px) + ${topPx}px)`, gap: gapPx }}>
       <Segmented label="View" value={mode} options={MODES} onValueChange={onMode} />
+      <Switch label="Effects in space" checked={effects} onCheckedChange={onEffects} />
       <Switch label="Labels" checked={labels} onCheckedChange={onLabels} />
     </div>
   )
diff --git a/web/src/stage/stage-view.tsx b/web/src/stage/stage-view.tsx
index 9d0bb7d..30e5e0d 100644
--- a/web/src/stage/stage-view.tsx
+++ b/web/src/stage/stage-view.tsx
@@ -7,6 +7,7 @@
 import { useMemo, useState, type MouseEvent, type PointerEvent } from 'react'
 import { useNavigate } from 'react-router'
 import type { Id, Room } from '@/api/contract'
+import { useFxStream } from '@/api/use-fx'
 import { useElementSize } from '@/lib/use-element-size'
 import { sameEntries, useStable } from '@/lib/use-stable'
 import { useReducedMotion } from '@/lib/use-media-query'
@@ -15,6 +16,7 @@ import { stageBodies } from './bodies'
 import { FIT_VIEW, fitPose, projectPoint } from './camera'
 import { SPEC } from './design-numbers'
 import { FrameWriter, sameLayout, writerEntries } from './frame-writer'
+import type { FxPick } from './fx-writer'
 import { looksOn, stageLabels } from './labels'
 import { anchorOf, lightMarks, statusesOf } from './marks'
 import { Legend } from './overlays/legend'
@@ -92,7 +94,7 @@ export function StageView({ data, variant, route, roomTo, roomState, outlined =
   const previewing = composeZone === undefined ? null : (compose?.previewing ?? null)
   // The composer's stage is the composer's before its zone is known too: not Live's, for a moment, while the zones load.
   const mode = frozen ? 'frozen' : focusZone !== undefined ? 'focus' : compose !== null ? 'compose' : 'live'
-  const behaviour = stageBehaviour({ mode, variant, reducedMotion, labels: stored.labels })
+  const behaviour = stageBehaviour({ mode, variant, reducedMotion, labels: stored.labels, effects: stored.effects })
   // The phone's stage has no view controls, so it shows the fitted view (§8.10).
   const view = behaviour.overlays ? stored.view : FIT_VIEW
   const [webgl] = useState(hasWebGL2)
@@ -124,6 +126,19 @@ export function StageView({ data, variant, route, roomTo, roomState, outlined =
   // §7.6 compose: "the chosen zone renders the preview stream instead of live", while it draws a look there.
   const previewedLights = previewing === null || composeZone === undefined ? null : composeZone.lights
   const previewed = useMemo(() => (previewedLights === null ? null : new Set(previewedLights)), [previewedLights])
+  // §7.4's effects in space, of the zones whose lights the stage draws from the live stream: in compose, not
+  // those under the preview, whose own fx it draws instead; in focus, only those with a light in the zone.
+  const fxPick = useMemo((): FxPick => {
+    const among = previewed ?? (focusZone === undefined ? null : new Set(focusZone.lights))
+    const hidden = new Set<Id>()
+    for (const zone of running) {
+      const inside = among !== null && zone.lights.some((id) => among.has(id))
+      if (previewed !== null ? inside : among !== null && !inside) hidden.add(zone.zoneId)
+    }
+    return { preview: previewed === null || composeZone === undefined ? null : composeZone.id, hidden }
+  }, [previewed, focusZone, running, composeZone])
+  const drawsFx = webgl && pose !== null && behaviour.effects
+  useFxStream(drawsFx)
   // The engine pushes `lights` every few seconds while a look plays. The writer's arrays (and the
   // meshes over them) are made from which bodies are drawn alone, and take each push's colours (and
   // a preview's stream) in place; the marks, from each light's status alone (I1).
@@ -214,7 +229,7 @@ export function StageView({ data, variant, route, roomTo, roomState, outlined =
                 mask={mask}
                 pose={pose}
                 cadenceMs={behaviour.cadenceMs}
-                fx={null}
+                fx={drawsFx ? fxPick : null}
               />
               <StageSvg pose={pose} marks={marks} labels={labels} sun={sunDrawn} outline={outline} compose={composeShape} />
               {focusZone !== undefined && framing !== null && (
@@ -236,6 +251,8 @@ export function StageView({ data, variant, route, roomTo, roomState, outlined =
           <StageTools
             mode={view.mode}
             onMode={(mode) => store({ ...stored, view: { ...view, mode } })}
+            effects={stored.effects}
+            onEffects={(on) => store({ ...stored, effects: on })}
             labels={stored.labels}
             onLabels={(on) => store({ ...stored, labels: on })}
           />
diff --git a/web/src/stage/view-memory.ts b/web/src/stage/view-memory.ts
index b333b4c..47f95d1 100644
--- a/web/src/stage/view-memory.ts
+++ b/web/src/stage/view-memory.ts
@@ -6,13 +6,15 @@ import { browserStorage } from '@/lib/storage'
 import { FIT_VIEW, type View } from './camera'
 import { SPEC } from './design-numbers'
 
-/** What the stage remembers per route: the camera's view, and whether the room labels show. */
+/** What the stage remembers per route: the camera's view, and whether the room labels and the effects in space show. */
 export interface StoredView {
   view: View
   labels: boolean
+  /** §7.4: "This is the "Effects in space" toggle (default on)". */
+  effects: boolean
 }
 
-export const DEFAULT_STAGE_VIEW: StoredView = { view: FIT_VIEW, labels: true }
+export const DEFAULT_STAGE_VIEW: StoredView = { view: FIT_VIEW, labels: true, effects: true }
 
 /** "Zoom in" steps through these; Fit goes back to the first (decision 5). */
 export const ZOOM_STEPS = [1, 1.25, 1.5, 2] as const
@@ -32,7 +34,7 @@ export function readStageView(storage: Storage | null, route: string): StoredVie
     return DEFAULT_STAGE_VIEW
   }
   if (typeof stored !== 'object' || stored === null) return DEFAULT_STAGE_VIEW
-  const { mode, rotateDeg, zoom, labels } = stored as Record<string, unknown>
+  const { mode, rotateDeg, zoom, labels, effects } = stored as Record<string, unknown>
   return {
     view: {
       mode: mode === 'plan' || mode === '3d' ? mode : FIT_VIEW.mode,
@@ -40,13 +42,14 @@ export function readStageView(storage: Storage | null, route: string): StoredVie
       zoom: isZoom(zoom) ? zoom : FIT_VIEW.zoom,
     },
     labels: typeof labels === 'boolean' ? labels : DEFAULT_STAGE_VIEW.labels,
+    effects: typeof effects === 'boolean' ? effects : DEFAULT_STAGE_VIEW.effects,
   }
 }
 
 /** Stores the view for `route`; a storage that refuses is ignored. */
-export function writeStageView(storage: Storage | null, route: string, { view, labels }: StoredView): void {
+export function writeStageView(storage: Storage | null, route: string, { view, labels, effects }: StoredView): void {
   try {
-    storage?.setItem(KEY + route, JSON.stringify({ ...view, labels }))
+    storage?.setItem(KEY + route, JSON.stringify({ ...view, labels, effects }))
   } catch {
     // Full, or blocked: the view just isn't remembered.
   }
```

- [ ] **Step 5: Run them to see them pass**

Run: `(cd web && npx vitest run src/api/use-fx.test.ts src/stage/behaviour.test.ts src/stage/view-memory.test.ts src/stage/overlays/overlays.test.tsx src/stage/stage-view.test.tsx)`
Expected: `Test Files  5 passed (5)`, `Tests  66 passed (66)`.

- [ ] **Step 6: The gate**

```bash
(cd web && npm test 2>&1 | grep -E 'Test Files|Tests ' && npm run lint && npx tsc -b && echo "tsc ok")
```

Expected: `Test Files  107 passed (107)`, `Tests  1123 passed (1123)`, lint clean, "tsc ok".

- [ ] **Step 7: Commit**

```bash
git add web/src/stage web/src/api/use-fx.test.ts
git commit -m "feat(web): the Effects in space switch, and the stage's pick of zones"
```

---

### Task 8: The effects in space in the browser, and the baselines with them

The shaders compile only in a browser, and every stage screenshot now carries its looks' effects. This task:
- adds the switch's own e2e test;
- makes every stage screenshot wait for the mock's first picture (`fxPictured()`), so a screenshot never races it;
- measures the hero with its effects drawn;
- re-records the baselines after a comparison by eye.

**Files:**
- Modify: `web/src/api/mocks/mock-server.ts` (`onFx`), `web/src/api/mocks/browser.ts` (the mark), `web/e2e/helpers.ts` (`fxPictured()`), `web/e2e/stage.spec.ts`, `web/e2e/live.spec.ts`, `web/e2e/compose.spec.ts`, `web/e2e/shell.spec.ts`, `web/e2e/stage.perf.ts`
- Test: `web/src/api/mocks/mock-server.test.ts`
- Re-record: the 23 baselines Step 6 lists

**Interfaces:**
- Consumes: Task 3's fx channel; Task 7's switch.
- Produces:
  - `MockServerOptions.onFx?: () => void`, called after each fx send.
  - In the browser's mock, `<html data-mock-fx>` once a picture has gone out.
  - `fxPictured(page)` in `e2e/helpers.ts`.

- [ ] **Step 1: Read the code**

Read `web/src/api/mocks/browser.ts`, `web/e2e/helpers.ts` (`open()`, `openStage()`, `stageCanvas()`), the screenshot tests in `live.spec.ts`, `compose.spec.ts` and `shell.spec.ts`, and `web/e2e/stage.perf.ts`.

The race this task closes: a screenshot taken before the mock's first fx send shows the stage without its effects, and one taken after shows them. So a baseline recorded either way fails the other way some of the time. Under `?still` the mock sends one picture and holds it; the page waits for its mark before it shoots.

- [ ] **Step 2: Write the failing test**

```diff
diff --git a/web/src/api/mocks/mock-server.test.ts b/web/src/api/mocks/mock-server.test.ts
index 83823a5..afe0b19 100644
--- a/web/src/api/mocks/mock-server.test.ts
+++ b/web/src/api/mocks/mock-server.test.ts
@@ -240,12 +240,14 @@ describe('the fx channel', () => {
     expect(pictures(socket)).toHaveLength(1)
   })
 
-  // §12.4: nothing while nothing changes. ?still holds the picture, so it goes out once.
-  it('sends a held picture once under ?still', () => {
-    const socket = connect(startMockServer({ still: true }))
+  // §12.4: nothing while nothing changes. ?still holds the picture, so it goes out once, and says so (browser.ts marks the page for e2e).
+  it('sends a held picture once under ?still, and says when it does', () => {
+    const onFx = vi.fn()
+    const socket = connect(startMockServer({ still: true, onFx }))
     socket.send({ action: 'subscribe_fx', on: true })
     vi.advanceTimersByTime(1000)
     expect(pictures(socket)).toHaveLength(1)
+    expect(onFx).toHaveBeenCalledOnce()
   })
 
   it("draws the preview's look on the preview stream while it's on, and nothing for it after", () => {
```

Run: `(cd web && npx vitest run src/api/mocks/mock-server.test.ts)`
Expected: FAIL: `Tests  1 failed | 51 passed (52)`, with `expected "vi.fn()" to be called once, but got 0 times`.

- [ ] **Step 3: The mark**

```diff
diff --git a/web/src/api/mocks/browser.ts b/web/src/api/mocks/browser.ts
index cdc5e31..8deabec 100644
--- a/web/src/api/mocks/browser.ts
+++ b/web/src/api/mocks/browser.ts
@@ -5,8 +5,14 @@ import type { MockChoice } from './choice'
 import { mockHandlers } from './handlers'
 import { MockServer } from './mock-server'
 
+/**
+ * e2e's sign that the stage has a picture of the effects in space to draw (e2e/helpers.ts, fxPictured()):
+ * a screenshot waits for it, or it races the picture's arrival.
+ */
+const markFx = () => document.documentElement.setAttribute('data-mock-fx', '')
+
 export async function startMocks(choice: MockChoice): Promise<MockServer> {
-  const server = new MockServer(choice)
+  const server = new MockServer({ ...choice, onFx: markFx })
   const worker = setupWorker(...mockHandlers(server, liveSocketUrl()))
   await worker.start({
     serviceWorker: { url: `${import.meta.env.BASE_URL}mockServiceWorker.js` },
diff --git a/web/src/api/mocks/mock-server.ts b/web/src/api/mocks/mock-server.ts
index 40d95f2..b41088e 100644
--- a/web/src/api/mocks/mock-server.ts
+++ b/web/src/api/mocks/mock-server.ts
@@ -63,6 +63,8 @@ export interface MockServerOptions {
   clock?: () => number
   /** Epoch ms: the API's times and the beat's server_time. */
   wallClock?: () => number
+  /** Called whenever a picture of the effects in space goes out: the mock build marks the page for e2e (browser.ts). */
+  onFx?: () => void
 }
 
 interface Session extends MockSession {
@@ -291,6 +293,7 @@ export class MockServer {
   private readonly still: boolean
   private readonly clock: () => number
   private readonly wallClock: () => number
+  private readonly onFx: () => void
   private readonly startedAt: number
   private readonly sessions = new Set<Session>()
   private nextId = 0
@@ -325,6 +328,7 @@ export class MockServer {
     this.still = options.still ?? false
     this.clock = options.clock ?? (() => performance.now())
     this.wallClock = options.wallClock ?? (() => Date.now())
+    this.onFx = options.onFx ?? (() => {})
     const state = buildScenario(options.scenario ?? 'hero', new Date(this.wallClock()))
     this.state = this.protocol === 1 ? asEngineM1(state) : state
     this.ownBeat = { ...this.state.beat }
@@ -638,6 +642,7 @@ export class MockServer {
       if (!session.fx || session.lastFx === text) continue
       session.lastFx = text
       session.link.send(text)
+      this.onFx()
     }
   }
 
```

Run: `(cd web && npx vitest run src/api/mocks/mock-server.test.ts)`
Expected: `Tests  52 passed (52)`.

- [ ] **Step 4: The e2e changes**

```diff
diff --git a/web/e2e/compose.spec.ts b/web/e2e/compose.spec.ts
index 7b9cda9..3b07e06 100644
--- a/web/e2e/compose.spec.ts
+++ b/web/e2e/compose.spec.ts
@@ -1,6 +1,6 @@
 import { expect, test, type Locator, type Page } from '@playwright/test'
 import { LIVE_RENDER, LIVE_SPEC } from '../src/design/live-numbers'
-import { absoluteEscapes, expectRingWhole, mainScroll, notch, open, SLACK, settled, stageCanvas, walkLooks, type Insets } from './helpers'
+import { absoluteEscapes, expectRingWhole, fxPictured, mainScroll, notch, open, SLACK, settled, stageCanvas, walkLooks, type Insets } from './helpers'
 
 // The hero moment (spec §12.5): Wednesday 23 September, 19:14 in the home's time zone (timezoneId in the config).
 const HERO_TIME = new Date('2026-09-23T19:14:00-05:00')
@@ -133,6 +133,7 @@ for (const size of ['desktop', 'phone'] as const) {
       test(`${state.name}${state.render === null ? '' : `, as ${size === 'desktop' ? 'Live' : 'Phone'}-${state.render}`}`, async ({ page }) => {
         await open(page, still(state.path))
         await expect(stageCanvas(page)).toBeVisible()
+        await fxPictured(page)
         await expect(state.ready(page)).toBeVisible()
         // As live.spec.ts: on desktop, the banner's frame rate settled.
         if (size === 'desktop') await expect(page.getByRole('banner').getByText('60 fps')).toBeVisible({ timeout: 10_000 })
diff --git a/web/e2e/helpers.ts b/web/e2e/helpers.ts
index efe7ca9..5bab746 100644
--- a/web/e2e/helpers.ts
+++ b/web/e2e/helpers.ts
@@ -27,6 +27,15 @@ export function stageCanvas(page: Page): Locator {
   return stageOf(page).locator('canvas')
 }
 
+/**
+ * The mock has sent the stage a picture of the effects in space (src/api/mocks/browser.ts marks the page),
+ * which it draws in the next animation frame: a screenshot of a stage that draws them waits for it, or it
+ * can settle before the picture lands. A stage frozen before it asked for one never gets one.
+ */
+export async function fxPictured(page: Page): Promise<void> {
+  await expect(page.locator('html[data-mock-fx]')).toHaveCount(1)
+}
+
 /** open(), then Live's stage once its canvas shows. */
 export async function openStage(page: Page, path = '/next/live'): Promise<Locator> {
   await open(page, path)
diff --git a/web/e2e/live.spec.ts b/web/e2e/live.spec.ts
index 610ad57..c15f9e7 100644
--- a/web/e2e/live.spec.ts
+++ b/web/e2e/live.spec.ts
@@ -1,5 +1,5 @@
 import { expect, test, type Locator, type Page } from '@playwright/test'
-import { absoluteEscapes, mainScroll, open, settled, stageCanvas } from './helpers'
+import { absoluteEscapes, fxPictured, mainScroll, open, settled, stageCanvas } from './helpers'
 
 // The hero moment (spec §12.5): Wednesday 23 September, 19:14 in Dallas (timezoneId in the config).
 const HERO_TIME = new Date('2026-09-23T19:14:00-05:00')
@@ -72,6 +72,7 @@ for (const [size, states] of [['desktop', DESKTOP], ['phone', PHONE]] as const)
       test(`${state.name}${state.render === null ? '' : `, as ${state.render}`}`, async ({ page }) => {
         await open(page, still(state.path), state.quiet && state.ready(page))
         if (state.path.startsWith('/next/live')) await expect(stageCanvas(page)).toBeVisible()
+        if (state.path.startsWith('/next/live') && state.name !== 'reconnecting') await fxPictured(page)
         await expect(state.ready(page)).toBeVisible()
         // As shell.spec.ts's openStill: Live's tempo drawn, and on desktop the frame rate settled where the banner has one.
         if (state.path.startsWith('/next/live?')) await expect(page.getByRole('banner').getByRole('group', { name: 'Tempo' })).toBeVisible()
diff --git a/web/e2e/shell.spec.ts b/web/e2e/shell.spec.ts
index b38096e..c6e3a3f 100644
--- a/web/e2e/shell.spec.ts
+++ b/web/e2e/shell.spec.ts
@@ -1,6 +1,6 @@
 import AxeBuilder from '@axe-core/playwright'
 import { expect, test, type Locator, type Page } from '@playwright/test'
-import { notch, open, stageCanvas, type Insets } from './helpers'
+import { fxPictured, notch, open, stageCanvas, type Insets } from './helpers'
 
 // The hero moment (spec §12.5): Wednesday 23 September, 19:14 in Dallas (timezoneId in the config).
 const HERO_TIME = new Date('2026-09-23T19:14:00-05:00')
@@ -101,6 +101,7 @@ test.beforeEach(async ({ page }) => {
 test('Live', async ({ page }) => {
   await openStill(page, '/next/live')
   await expect(stageCanvas(page)).toBeVisible()
+  await fxPictured(page)
   await expect(page).toHaveScreenshot('live.png')
 })
 
diff --git a/web/e2e/stage.perf.ts b/web/e2e/stage.perf.ts
index 227bf89..1ec0359 100644
--- a/web/e2e/stage.perf.ts
+++ b/web/e2e/stage.perf.ts
@@ -76,9 +76,20 @@ function p95Gap(renders: readonly number[]): number {
   return gaps[Math.floor(0.95 * (gaps.length - 1))]
 }
 
-test('the stage keeps its frame rate with every LED streaming, and the main thread stays idle', async ({ page, isMobile }) => {
-  const { renderer, renders, busy } = await measure(page, '/next/live?scenario=firmware', isMobile ? PHONE_CPU_SLOWDOWN : 1)
-  console.log(JSON.stringify({ project: isMobile ? 'phone' : 'desktop', renderer, fps: renders.length / (WINDOW_MS / 1000), p95GapMs: p95Gap(renders), busy }))
+// The firmware scenario streams every LED in the home; the hero draws its effects in space beside its
+// frames (§7.4: the fx channel at up to 30 Hz), so both stores wake the stage's one cadence.
+for (const [what, scenario] of [
+  ['with every LED streaming', 'firmware'],
+  ['with the effects in space drawn', 'hero'],
+] as const) {
+  test(`the stage keeps its frame rate ${what}, and the main thread stays idle`, async ({ page, isMobile }) => {
+    await measured(page, isMobile, scenario)
+  })
+}
+
+async function measured(page: Page, isMobile: boolean, scenario: string) {
+  const { renderer, renders, busy } = await measure(page, `/next/live?scenario=${scenario}`, isMobile ? PHONE_CPU_SLOWDOWN : 1)
+  console.log(JSON.stringify({ project: isMobile ? 'phone' : 'desktop', scenario, renderer, fps: renders.length / (WINDOW_MS / 1000), p95GapMs: p95Gap(renders), busy }))
   expect(renderer, 'measured on the GPU, not the software renderer').not.toMatch(/SwiftShader|llvmpipe|none/i)
   if (isMobile) {
     // The phone draws at most SPEC.phoneFps (§7.5): every one of those, give or take the window's ends.
@@ -87,4 +98,4 @@ test('the stage keeps its frame rate with every LED streaming, and the main thre
     expect(1000 / p95Gap(renders)).toBeGreaterThanOrEqual(SPEC.quality.desktopFps)
   }
   expect(busy).toBeLessThanOrEqual(1 - SPEC.quality.idle)
-})
+}
diff --git a/web/e2e/stage.spec.ts b/web/e2e/stage.spec.ts
index 75af3a3..2a1060a 100644
--- a/web/e2e/stage.spec.ts
+++ b/web/e2e/stage.spec.ts
@@ -2,7 +2,7 @@ import { expect, test } from '@playwright/test'
 import { open, openStage, stageCanvas } from './helpers'
 
 // The stage in the browser, on the mock (the hero unless the path asks for another scenario): §8.1's
-// room click and §7.6's frozen mode. The phone's stage has no labels or overlays (§8.10), and
+// room click, §7.6's frozen mode and §7.4's effects in space. The phone's stage has no labels or overlays (§8.10), and
 // stage-view.test.tsx covers it, so this needs one project.
 test.describe('the stage', () => {
   test.skip(({ isMobile }) => isMobile)
@@ -20,6 +20,35 @@ test.describe('the stage', () => {
     await page.waitForURL((url) => `${url.pathname}${url.search}` === href)
   })
 
+  // §7.4: "This is the "Effects in space" toggle (default on)". Under ?still the mock holds its frames and
+  // sends one picture of the effects in space, so the canvas is the same draw after draw: the switch takes
+  // the hero's fireflies and comets off it and puts them back, and Live remembers it off.
+  test('draws the effects in space, and the switch takes them off and back, remembered', async ({ page }) => {
+    const stage = await openStage(page, '/next/live?still')
+    const effects = stage.getByRole('switch', { name: 'Effects in space' })
+    await expect(effects).toHaveAttribute('aria-checked', 'true')
+    const canvas = stageCanvas(page)
+    const shot = () => canvas.screenshot()
+    // Drawn with the picture: it changes once more after the first draw, as the picture lands, then holds.
+    await expect.poll(async () => (await shot()).equals(await shot()), { timeout: 5000 }).toBe(true)
+    await effects.click()
+    await expect(effects).toHaveAttribute('aria-checked', 'false')
+    await expect.poll(async () => (await shot()).equals(await shot())).toBe(true)
+    const off = await shot()
+    await effects.click()
+    await expect.poll(async () => (await shot()).equals(off), { timeout: 5000 }).toBe(false)
+    // Off again, and after a reload still off: putting them on changes the picture.
+    await effects.click()
+    await page.reload()
+    const reloaded = page.getByRole('switch', { name: 'Effects in space' })
+    await expect(reloaded).toHaveAttribute('aria-checked', 'false')
+    await expect(canvas).toBeVisible()
+    await expect.poll(async () => (await shot()).equals(await shot())).toBe(true)
+    const stillOff = await shot()
+    await reloaded.click()
+    await expect.poll(async () => (await shot()).equals(stillOff), { timeout: 5000 }).toBe(false)
+  })
+
   // Review focus 3, in the browser: the reconnecting scenario drops the link a second after it connects. The
   // rooms' links come with the stage, before its canvas, whose shaders can take most of that second to compile.
   test('freezes when the link drops: greyed, and no room opens the composer', async ({ page }) => {
```

- [ ] **Step 5: Run e2e, and compare the failures by eye**

```bash
for i in $(seq 1 60); do [ "$(ss -ltn | grep -cE ':(4174|4175) ')" = 0 ] && break; sleep 10; done; ss -ltn | grep -cE ':(4174|4175) '
(cd web && npm run e2e 2>&1 | tail -30)
```

Expected: the new stage test passes, and about 23 screenshots fail on their baselines: every one whose stage draws a look that draws in space, and every desktop Live state, whose tools row now has the switch.

That the stage test passes is the shaders' proof: under `?still` the canvas changes when the switch puts the effects back, so they compiled and drew. If it fails with the canvas unchanged, open `/next/live?still` in the dev server on the mocks (`npm run dev`, then `http://localhost:5174/next/live?scenario=hero&still`) and read the console for a shader error.

For each failure, open Playwright's report (`npx playwright show-report`) and compare the actual with the expected and with its render:
- Desktop Live states: the tools row reads `3D | Plan`, "Effects in space" (on), "Labels", as Main.png's does.
- The hero (Live, shell's Live, preview only, transition, problems): small glowing points in the room round the zones running Fireflies and Comets, faint against the floor, as Main.png's fireflies are. Nothing else on the stage moved.
- Compose: the previewed look's effects on the composer's zone, and no live effects of the zones under it (ruling 5).
- The phone: the same points on the phone's stage, as Phone-Live.png's.

If anything else changed, go back to the task that owns it. Write down what you saw for each, for the PR.

- [ ] **Step 6: Re-record, and check they hold**

```bash
for i in $(seq 1 60); do [ "$(ss -ltn | grep -cE ':(4174|4175) ')" = 0 ] && break; sleep 10; done; ss -ltn | grep -cE ':(4174|4175) '
(cd web && npm run e2e -- --update-snapshots 2>&1 | tail -3 && git status --short e2e)
```

Expected: these 23 baselines change, and no other file under `e2e/` besides the specs Step 4 changed:

- `web/e2e/compose.spec.ts-snapshots/no-lights-desktop-linux.png`
- `web/e2e/compose.spec.ts-snapshots/no-look-desktop-linux.png`
- `web/e2e/compose.spec.ts-snapshots/no-look-phone-linux.png`
- `web/e2e/compose.spec.ts-snapshots/no-match-desktop-linux.png`
- `web/e2e/compose.spec.ts-snapshots/preview-desktop-linux.png`
- `web/e2e/compose.spec.ts-snapshots/preview-phone-linux.png`
- `web/e2e/compose.spec.ts-snapshots/waits-for-music-desktop-linux.png`
- `web/e2e/live.spec.ts-snapshots/doorbell-desktop-linux.png`
- `web/e2e/live.spec.ts-snapshots/firmware-desktop-linux.png`
- `web/e2e/live.spec.ts-snapshots/first-run-desktop-linux.png`
- `web/e2e/live.spec.ts-snapshots/inputs-down-desktop-linux.png`
- `web/e2e/live.spec.ts-snapshots/no-lights-desktop-linux.png`
- `web/e2e/live.spec.ts-snapshots/nothing-running-desktop-linux.png`
- `web/e2e/live.spec.ts-snapshots/preview-only-desktop-linux.png`
- `web/e2e/live.spec.ts-snapshots/preview-only-phone-linux.png`
- `web/e2e/live.spec.ts-snapshots/problems-desktop-linux.png`
- `web/e2e/live.spec.ts-snapshots/problems-phone-linux.png`
- `web/e2e/live.spec.ts-snapshots/transition-desktop-linux.png`
- `web/e2e/live.spec.ts-snapshots/waiting-desktop-linux.png`
- `web/e2e/live.spec.ts-snapshots/waiting-phone-linux.png`
- `web/e2e/live.spec.ts-snapshots/zone-phone-linux.png`
- `web/e2e/shell.spec.ts-snapshots/live-desktop-linux.png`
- `web/e2e/shell.spec.ts-snapshots/live-phone-linux.png`

Then run the whole suite twice, and the screenshot specs three times over, so a baseline that passed by luck shows itself:

```bash
for run in 1 2; do
  for i in $(seq 1 60); do [ "$(ss -ltn | grep -cE ':(4174|4175) ')" = 0 ] && break; sleep 10; done
  (cd web && npm run e2e 2>&1 | tail -3)
done
(cd web && npx playwright test e2e/live.spec.ts e2e/compose.spec.ts e2e/shell.spec.ts --repeat-each 3 --reporter line 2>&1 | tail -3)
```

Expected: `160 passed` and `106 skipped` each time, then `468 passed` and `306 skipped`. A screenshot that fails one run in several is still racing the picture. Check that its test waits for `fxPictured()` before it shoots, fix the test, and re-record that one.

- [ ] **Step 7: The frame rate**

```bash
for i in $(seq 1 60); do [ "$(ss -ltn | grep -cE ':(4174|4175) ')" = 0 ] && break; sleep 10; done; ss -ltn | grep -cE ':(4174|4175) '
(cd web && npm run e2e:perf 2>&1 | grep -E '^\{|passed|failed')
```

Expected: `4 passed`. Each project runs the firmware scenario ("with every LED streaming") and the hero ("with the effects in space drawn"). Every `fps` is within §14's, as the test asserts. On the machine this plan was written on:
- desktop: firmware 57.6 fps, busy 0.07; hero 57.4 fps, busy 0.06;
- phone: 30.2 fps both, busy 0.21 and 0.16.

Write each project's numbers down for the PR.

- [ ] **Step 8: The gate**

```bash
(cd web && npm test 2>&1 | grep -E 'Test Files|Tests ' && npm run lint && npx tsc -b && echo "tsc ok" && npm run build 2>&1 | tail -1)
```

Expected: `Test Files  107 passed (107)`, `Tests  1123 passed (1123)`, lint clean, "tsc ok", and `…/web/dist: no mocks, 285.8 KB of gzipped JS` on `57455a7`, within §14's budget.

- [ ] **Step 9: Commit**

```bash
git add web/e2e web/src/api/mocks
git commit -m "test(web): the effects in space in the browser, and baselines with them"
```

---

### Task 9: Revise CLAUDE.md

CLAUDE.md gains the effects in space's modules and the gotchas this branch found. No design values go in: CLAUDE.md forbids restating them there.

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: the names Tasks 1 to 8 gave their modules.
- Produces: nothing that code reads.

- [ ] **Step 1: Invoke `claude-md-management:revise-claude-md`**

Use it to review what this branch taught. The edits below are the minimum. Keep any other edit it proposes that also follows the no-design-values rule and the public-repo rule (Global Constraints).

- [ ] **Step 2: The data layer and the mocks**

All of these are in the `web/` block of `## Architecture`.

In `CLAUDE.md`, replace:

```markdown
`live-client.ts` (the one socket: backoff, silence watchdog, resync, frame protocol handshake)
```

with:

```markdown
`live-client.ts` (the one socket: backoff, silence watchdog, resync, frame protocol handshake; `subscribeFx()`, the `fx` channel on or off, asked for again at every link-up while on, its pictures stored only while on and cleared on a drop)
```

In `CLAUDE.md`, replace:

```markdown
`frames.ts` (`FrameStore`: reused typed arrays React never watches; `onNextFrame()` wakes whoever waits for the next frame),
```

with:

```markdown
`frames.ts` (`FrameStore`: reused typed arrays React never watches; `onNextFrame()` wakes whoever waits for the next frame), `fx.ts` (`FxStore`: the `fx` channel's latest picture, by zone, for each stream, which React never watches either; its `version` moves with every picture, `onNextChange()` wakes whoever waits for the next, and the preview's are held while the frame store holds the preview's frames),
```

In `CLAUDE.md`, replace:

```markdown
`live.ts` (the app's singletons, the preview session among them; `startDataLayer()`, and `resetDataLayer()` for tests)
```

with:

```markdown
`live.ts` (the app's singletons, the preview session and the fx store among them; `wantFx()`, the stages that want the `fx` channel counted, which `useFxStream()` in `use-fx.ts` calls; `startDataLayer()`, and `resetDataLayer()` for tests)
```

In `CLAUDE.md`, replace:

```markdown
- `src/api/mocks/` — `MockServer` plays a §12.5 scenario (REST, channels, animated frames) from byte copies of `home.json` and `looks.json`;
```

with:

```markdown
- `src/api/mocks/` — `MockServer` plays a §12.5 scenario (REST, channels, animated frames, and the `fx` channel from `mock-fx.ts`'s `zoneFx()`, a simple moving picture of each look that draws in space, no design value) from byte copies of `home.json` and `looks.json`;
```

- [ ] **Step 3: The stage**

In `CLAUDE.md`, replace:

```markdown
`StageView` asks it once (mode, variant, reduced motion, the Labels switch) and hands down what each part does (interactive, `roomClick`, `framesComposeZone`, overlays, legend, `outlinePx`, labels, the sun's label, greyed, `previewTag`, `cadenceMs`)
```

with:

```markdown
`StageView` asks it once (mode, variant, reduced motion, the Labels and Effects in space switches) and hands down what each part does (interactive, `roomClick`, `framesComposeZone`, overlays, legend, `outlinePx`, labels, `effects`, the sun's label, greyed, `previewTag`, `cadenceMs`)
```

In `CLAUDE.md`, replace:

```markdown
`FrameWriter` writes the frame store's arrays into the instances in place, and says whether anything changed; `cadence.ts`'s `useCadence` is the stage's one draw tick (the canvas draws on it, and the light tooltip follows it through `onStageDraw()`); `stage-canvas.tsx` mounts React Three Fiber's `createRoot` on its own canvas; `scene/` is three.js under it (`HomeScene`, `LightMeshes`);
```

with:

```markdown
`FrameWriter` writes the frame store's arrays into the instances in place, and says whether anything changed; `FxWriter` (`fx-writer.ts`) writes the fx store's picture of the zones the stage picks (`FxPick`: the composer's preview, and the live zones hidden under it or outside focus) into arrays it keeps, which grow and never shrink; `cadence.ts`'s `useCadence` is the stage's one draw tick (the canvas draws on it, and the light tooltip follows it through `onStageDraw()`); `stage-canvas.tsx` mounts React Three Fiber's `createRoot` on its own canvas; `scene/` is three.js under it (`HomeScene`, `LightMeshes`, and the effects in space: `FxMeshes` and `FxMaterials` in `fx-meshes.ts`, their shaders in `fx-shaders.ts`, `FxLayer`; `StageScene` owns the cadence and asks each layer through its `DrawList`, `draw-list.ts`);
```

- [ ] **Step 4: e2e**

In `CLAUDE.md`, replace:

```markdown
`openStage()` and the stage's canvas locator;
```

with:

```markdown
`openStage()` and the stage's canvas locator; `fxPictured()`, which waits for the mock's first `fx` picture;
```

- [ ] **Step 5: Gotchas**

In `CLAUDE.md`, replace:

```markdown
- Web app: the light layer draws in `useCadence`'s tick: `FrameWriter.write()`, and only if that changed something, `LightMeshes.update()` and `advance(now)`, which renders in that animation frame; `invalidate()` would wait for the next one and halve the rate. After an animation frame with nothing new the cadence sleeps, asking for no animation frames, until `FrameStore.onNextFrame()` wakes it
```

with:

```markdown
- Web app: the stage draws in `StageScene`'s one `useCadence` tick: its `DrawList` asks the light layer (`FrameWriter.write()`, then `LightMeshes.update()`) and the fx layer (`FxWriter.write()`, then `FxMeshes.update()`) for what's new, and only if either changed something it calls `advance(now)`, which renders in that animation frame; `invalidate()` would wait for the next one and halve the rate. After an animation frame with nothing new the cadence sleeps, asking for no animation frames, until `FrameStore.onNextFrame()` or `FxStore.onNextChange()` wakes it. A layer never runs a cadence of its own: two would render the canvas twice a tick
- Web app: three's `ShaderMaterial` declares `attribute vec3 normal` itself, so an instanced attribute of that name doesn't compile: the effects in space's plane material calls its normal `planeNormal`. jsdom has no WebGL, so a shader is checked only in the browser (e2e/stage.spec.ts's Effects in space test)
- Web app: a stage screenshot on the mock waits for `fxPictured()` (e2e/helpers.ts): the browser's mock marks `<html data-mock-fx>` after its first `fx` send, and under `?still` it sends one picture and holds it, so a screenshot taken before it lands lacks the effects and a baseline recorded either way fails the other way some of the time
```

- [ ] **Step 6: Check that no design values or private names slipped in**

```bash
git diff CLAUDE.md | grep -nE '^\+.*(#[0-9a-fA-F]{6}|[0-9.]+ ?(px|fps|ms|°|%)|[0-9]+ × [0-9]+)'
git diff CLAUDE.md | grep -E '^\+' | grep -nE '([0-9]{1,3}\.){3}[0-9]{1,3}|([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}'
```

Expected: no output from either.

- [ ] **Step 7: Check that every file CLAUDE.md now names exists**

```bash
for f in api/fx.ts api/use-fx.ts api/mocks/mock-fx.ts stage/fx-writer.ts stage/scene/fx-meshes.ts stage/scene/fx-shaders.ts \
  stage/scene/fx-layer.tsx stage/scene/draw-list.ts; do test -f "web/src/$f" || echo "MISSING: $f"; done
test -f web/e2e/helpers.ts && grep -q 'export async function fxPictured' web/e2e/helpers.ts || echo "MISSING: fxPictured"; echo "names checked"
```

Expected: "names checked" alone.

- [ ] **Step 8: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add the web app's effects in space to CLAUDE.md"
```

---

### Task 10: Rebase over master, and open the PR

Engine M8 is planned beside this plan, and either may merge first. M8 changes no file under `web/` that this plan changes, but both change `CLAUDE.md`, and master may move elsewhere under `web/` before F10 lands. This task brings the branch onto the latest master, runs every gate, and opens the PR. It never merges.

**Files:**
- Modify, only where the rebase asks: `CLAUDE.md`, and any `web/` file master changed beside this branch.
- Re-record, where master asks: `web/e2e/*-snapshots/*.png`, after a comparison by eye.

**Interfaces:**
- Consumes: every task's commits; master as it is now.
- Produces: the pull request.

- [ ] **Step 1: Rebase onto master**

```bash
git fetch origin
git log --oneline 3ac0dac..origin/master
git rebase origin/master
```

The branch hasn't been pushed, so rebasing is safe. Read the log, and write down whether engine M8 had merged, for the PR. Where a commit conflicts:
- **`CLAUDE.md`** (Task 9): keep both sides. Where both changed one line, keep each side's addition once, in the line's order.
- **A baseline under `web/e2e/*-snapshots/`** (Task 8): keep F10's with `git checkout --theirs <file>` ("theirs" is the commit being replayed). Step 2 compares it again.
- **`web/src/api/ws-messages.ts`, `live-client.ts`, `live.ts` or the mocks**: keep both sides, each name once in an import list, in the list's order.
- **Anything else**: stop and tell the owner.

After each resolution, run `git add` on the resolved files, then `git rebase --continue`.

- [ ] **Step 2: The whole web gate, from a clean install**

```bash
uv sync --extra web
(cd web && npm ci && npm run api:check && npm test 2>&1 | grep -E 'Test Files|Tests ' && npm run lint && npx tsc -b && echo "tsc ok" && npm run build 2>&1 | tail -1)
for i in $(seq 1 60); do [ "$(ss -ltn | grep -cE ':(4174|4175) ')" = 0 ] && break; sleep 10; done; ss -ltn | grep -cE ':(4174|4175) '
(cd web && npm run e2e 2>&1 | tail -3)
for i in $(seq 1 60); do [ "$(ss -ltn | grep -cE ':(4174|4175) ')" = 0 ] && break; sleep 10; done; ss -ltn | grep -cE ':(4174|4175) '
(cd web && npm run e2e:perf 2>&1 | grep -E '^\{|passed|failed')
```

Expected:
- `api:check` passes: F10 changes no API.
- Vitest passes: Task 8's count (1123 tests in 107 files on `57455a7`), plus whatever master added since.
  - `src/stage/design-numbers.node.test.ts` is among them. If it fails, a new handoff landed on master: stop and tell the owner, because `RENDER.particle` and the screenshots have to be read and compared again.
- Lint is clean, and `tsc -b` passes.
- `npm run build` ends with `…/web/dist: no mocks, <n> KB of gzipped JS`, within §14's budget (285.8 KB on `57455a7`). Write `<n>` down for the PR.
- Each port check prints `0`.
- e2e passes with Task 8's counts (160 passed and 106 skipped on `57455a7`), plus any master added.
  - If a screenshot fails because master changed what the mock serves or how the stage draws, compare it with its render by eye, as Task 8 did. Then re-record it (`npm run e2e -- --update-snapshots`, after the port check), run e2e again, and commit: `git add web/e2e && git commit -m "test(web): re-record the screenshots over master"`.
  - If it fails because of this branch's code, go back to the task that owns it.
- `e2e:perf` prints `4 passed`. Write down each scenario's `fps`, `p95GapMs` and `busy` for the PR.

- [ ] **Step 3: Scope and privacy checks**

```bash
git diff --stat origin/master...HEAD -- frontend/ docs/ src/ tests/ pyproject.toml uv.lock
for f in home.json looks.json; do cmp docs/design/web-app/$f web/src/api/mocks/$f || echo "DIFFERS: $f"; done
cmp docs/design/web-app/tokens.css web/src/styles/tokens.css && cmp docs/design/web-app/icons.ts web/src/design/icons.ts && echo "copies identical"
git status --short
```

Expected:
- No diff under `frontend/`, `docs/`, `src/`, `tests/`, or in the Python project files.
- No `DIFFERS`, then `copies identical`.
- A clean tree.

The repo is public. Check the branch's added lines, and its commit messages, for LAN addresses, MAC addresses, light names, light model names, room names, deck model names, network interface names and AI model names. The names come from the mock's `home.json` and `looks.json`, so this plan never spells one out. For the same reason, the AI model check looks for a model id's shape rather than for any name:

```bash
git diff origin/master...HEAD -- . ':!web/package-lock.json' | grep -E '^\+' | grep -nE '(192\.168|10\.[0-9]+\.[0-9]+\.[0-9]+|172\.(1[6-9]|2[0-9]|3[01])\.[0-9]+\.[0-9]+)|([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}'
git diff origin/master...HEAD -- . ':!web/src/api/mocks/home.json' | grep -E '^\+' | grep -nF -f <(node -e "for (const m of new Set(require('./web/src/api/mocks/home.json').lights.map((l) => l.model))) console.log(m)")
git diff origin/master...HEAD -- . ':!web/package-lock.json' | grep -E '^\+' | grep -niE '\b(XDJ|CDJ|DJM|DDJ)-?[0-9A-Z]|\b(enp[0-9]+s[0-9]+|eth[0-9]+|wlan[0-9]+|wlp[0-9]+s[0-9]+)\b|\b[0-9]+(\.[0-9]+)?b\b|instruct|gguf|\bawq\b|gptq|\bfp8\b|claude-[a-z]+-[0-9]'
git log --format=%B origin/master..HEAD | grep -nE '([0-9]{1,3}\.){3}[0-9]{1,3}|([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}'
node -e "
const home = require('./web/src/api/mocks/home.json'), looks = require('./web/src/api/mocks/looks.json')
const all = [...(home.rooms ?? []), ...(home.subZones ?? []), ...(home.lights ?? []), ...(looks.looks ?? looks)]
for (const name of new Set(all.map((each) => each.name))) console.log(name)
" > /tmp/f10-names.txt
git diff origin/master...HEAD -- . ':!web/src/api/mocks/*.json' ':!web/e2e/*-snapshots/*' ':!web/package-lock.json' | grep -E '^\+' | grep -nwF -f /tmp/f10-names.txt
git log --format=%B origin/master..HEAD | grep -nwF -f /tmp/f10-names.txt
```

Expected: no output from any of them. The tests name zones by their ids, which are home.json's; a match there is the fixture's id, not a typed name. Look at any other match by eye:
- Take out a real address, MAC, name, model or interface name.
- Ignore a false alarm, such as a short model name inside another word.

- [ ] **Step 4: Push and open the PR**

Fill in:
- the test count and file count, the build's KB figure and the frame-rate numbers, from Step 2;
- what Task 8's comparison by eye found;
- whether engine M8 had merged, from Step 1.

```bash
git push -u origin feature/web-f10-effects-in-space
gh pr create --base master --title "F10: the stage draws effects in space (first slice)" --body-file - <<'EOF'
## Summary

The first slice of milestone F10 (the handoff's M10) of the web app rebuild, per docs/superpowers/plans/2026-10-14-f10-effects-in-space.md: the stage draws §12.4's `fx` stream, so the owner can see how each particle look meets the lamps and tune the eleven M5 looks (#48–#58).

- **The data layer:** the `fx` message read item by item (a malformed item dropped, an unknown key ignored); `FxStore`, the latest picture per zone and stream; `subscribe_fx` while the stage draws the effects, sent again at every link-up, with the picture forgotten on off and on a drop.
- **The stage:** particles drawn as Main.html's fireflies (`RENDER.particle`, read from the render by `npm run design:numbers`); `sphere` and `circle` rings; planes clipped to the home's outline and its floor and ceiling, a `ray`'s half only. All additive and faint, on the stage's one draw tick (`DrawList`), with arrays that grow and never shrink.
- **The switch:** "Effects in space" between `3D | Plan` and Labels on desktop, on by default and remembered per route. The phone always draws them. Frozen and reduced motion draw none.
- **Compose and focus:** the composer's zone draws its preview's effects, with the live ones under it hidden; focus draws its zone's.
- **The mocks** send `fx` for every look that draws in space, at most 30 a second and only when changed.
- **e2e:** the switch in the browser; every stage screenshot waits for the mock's first picture and was re-recorded after a comparison by eye; `e2e:perf` measures the hero with its effects.
- CLAUDE.md: the modules and the gotchas.
- Engine M8: <merged before this, so the real engine sends `fx` | not merged yet; until it does, the real engine sends nothing and the switch draws nothing there>.

Deferred, as planned: sun shafts (M6's sun), the doorbell's gold ring and the overlays (M6, M7), and the rest of F10's reduced-motion, performance and accessibility pass.

## For the owner

The plan's decisions fill gaps in the spec. The ones to check:
- 2: the switch is shown now, though §7.4 says it's hidden until the `fx` stream exists; until M8 merges, it draws nothing on the real engine.
- 3 and 4: the phone always draws the effects, with no switch; frozen and reduced motion draw none.
- 5: compose draws the previewed look's effects on its zone and hides the live ones under it.
- 10: a particle is Main.html's firefly: its glow's radius is its `size` in metres, round a core held to the render's sizes; not clipped to the rooms.
- 11 and 12: rings and planes at the glass pane's alpha; planes clipped to the outline, and their `width` not drawn yet (§12.4 says it's how thick the plane is drawn).
- Acceptance (the plan's Task 11): once this and M8 have both merged and you say go for the deploy, preview each of the eleven particle looks in the composer. Previewing changes no light.

## Differences from the renders

- Live-PutLookOn draws no effects; the composer now draws the previewed look's (decision 5).
- The fireflies' places and colours are the mock's moving picture, not the render's.
- <what Task 8's comparison found, by screenshot>

## Test plan

- [x] `cd web && npm test`: <N> tests in <F> files: the message's checks, the store, the subscription's counts and link-ups, the mock's pictures and channel, the particle's numbers from the render, the writer, the meshes and the one draw tick, the switch, and the stage's pick in compose and focus
- [x] `cd web && npm run e2e`: the switch takes the effects off and puts them back, remembered; every screenshot with its effects, compared by eye, run twice and three times over
- [x] `cd web && npm run e2e:perf`: desktop firmware <fps> fps, hero with effects <fps> fps (busy <busy>); phone firmware <fps>, hero <fps> (busy <busy>)
- [x] `cd web && npm run build`: no mocks, <n> KB of gzipped JS, three.js's chunk aside
- [x] `npm run api:check`: no API change
- [x] No LAN address, MAC, light name, light model, room name or AI model name in the diff

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
```

Expected: `gh` prints the PR's URL. Don't merge it. Then stop: Task 11 waits for the owner.

---

### Task 11: The owner's acceptance (owner-gated)

The owner sees each particle look on the stage, as the slice was brought forward for. Previewing a look in the composer changes no light: the preview's runtime never gets a route. The deploy, though, restarts the app the lights are on, so each step below waits for the owner's "go". Don't start it on a clock; ask.

**Precondition:** engine M8's PR and this one have both merged to master. Check: `git -C /home/anirudhlath/code/private/dj-ledfx fetch origin && git -C /home/anirudhlath/code/private/dj-ledfx log --oneline origin/master | head -20` shows both merges.

- [ ] **Step 1: Ask for the deploy, then deploy**

Ask the owner: "Both M8 and F10 have merged. May I deploy master to dj-ledfx-app-1 (`docker compose up -d --build` in the main checkout)? It restarts the app, which the lights are on, for about a minute." Wait for "go".

```bash
cd /home/anirudhlath/code/private/dj-ledfx && git status --short && git pull --ff-only origin master
docker compose up -d --build
docker compose ps
curl -s http://127.0.0.1:8080/api/running | head -c 300; echo
ss -ulne 'sport = :4002'
```

Expected: a clean checkout fast-forwarded, the container healthy, `/api/running` answering, and `ss` showing `uid:10001` on UDP 4002. If 4002 shows another uid, Home Assistant took it while the app was down (CLAUDE.md, Gotchas): tell the owner before anything else.

- [ ] **Step 2: The owner previews each particle look**

The owner opens `/next/live` on their own device, puts the "Effects in space" switch on if they turned it off, and for each of M5's eleven particle looks opens Put a look on, chooses a zone, and chooses the look. The stage draws the preview's particles over the zone's lamps. Nothing changes on the lights until Start, and the acceptance needs no Start.

The looks, by their ids in `looks.json`: `fireflies`, `embers`, `rain`, `snow`, `spotlights`, `bursts`, `fountain`, `flock`, `vortex`, `comets`, `ball`. Read the names from `GET /api/looks`; don't retype them.

For each look, write down the owner's verdict as they give it: whether the particles sit where the lamps light, and what they want tuned. Post it to that look's issue (#48–#58) in the owner's words, only if they ask. Never post a screenshot of the real stage: it shows the home's room and light names, and the repo is public.

- [ ] **Step 3: Rings and planes (optional, the owner's call)**

If the owner wants to, they do the same with Shockwave, Speaker waves, Ripples and Scanner. Speaker waves runs on the beat until M7.

- [ ] **Step 4: Close**

Ask the owner whether anything is left running that they started. Never press Off or Stop all for them. Report the verdicts in one list, look by look.

---

## Hand-off

F10's first slice draws the `fx` stream's first kinds and the switch. The rest belongs to later slices and milestones. Each item names the F10 piece it builds on.

**F10, the rest of the M10 pass**
- **Reduced motion** (§5.4). This slice draws no effects under reduced motion (ruling 4). The pass decides whether a still picture, at the reduced cadence, is wanted. `stageBehaviour().effects` is the one line.
- **Performance.** `e2e:perf` measures the hero with its effects. The pass adds a crowd near §12.4's limits (the engine caps a look at 500 particles), and `compose` with the preview's effects.
- **Accessibility.** The switch is Base UI's `Switch` with its label, and axe on `/live` covers it. The pass checks the stage's accessible alternative says nothing about the effects, as the renders' don't.
- **Plane `width`** (ruling 12). The writer keeps it in the `width` attribute. Drawing it needs a slab, or a width-aware alpha edge on.

**Engine M6 (the sun) and M7 (the doorbell)**
- **Sun shafts:** a new optional `shafts` key on `ZoneFx` (§12.4's "Extending it"). Add its reader in `readFx()` beside the others, a batch in `FxWriter`, and a mesh in `FxMeshes`. Nothing else changes.
- **The doorbell's gold ring**, "clipped to the apartment outline" (§7.4): `FxMaterials` already masks the plane to the outline. A clipped ring would take the same mask.

**F7 (the home map)**
- **Map mode draws no effects** (ruling 4). Add `map` to `stageBehaviour()`'s `effects` rule when F7 adds the mode.

**F8 (the look editor)**
- **The editor's preview** draws its effects as the composer's does: `FxPick.preview` names the zone, and `hidden` the live zones under it.

**Engine M8**
- If M8 merged after this PR, the real engine starts sending `fx` with no change here. If its payload differs from §12.4's in any key, the spec settles it: fix whichever side differs, with the owner.

**Every new handoff**
- Run `cd web && npm run design:numbers`. If Main.html's fireflies changed, `RENDER.particle` follows, or the extractor names the firefly off the rule. Compare every stage screenshot with its new render by eye before re-recording it.

## Coverage

| The slice, and the sections it touches | Task |
|---|---|
| §12.4's `fx` payload read item by item; the extension rule; the store (rulings 8, 9) | 1 |
| `subscribe_fx` while drawn, again at link-up; the picture forgotten on off and on a drop (ruling 7) | 2 |
| §12.5's mocks send `fx` for every look that draws in space, ≤ 30 a second, only when changed (ruling 17) | 3 |
| A particle's look from Main.html's fireflies, through `npm run design:numbers` (ruling 10) | 4 |
| No allocation that grows with the pictures (§7.5; ruling 15) | 5, 6 |
| Particles, `sphere` and `circle` rings, planes with a `ray`, clipped and faint (§7.4; rulings 10–14) | 6 |
| One draw tick, waking for a picture as for a frame (§7.5; ruling 16) | 6 |
| §8.1's switch, default on, remembered; the phone; frozen; reduced motion (§7.4, §5.4, §7.6; rulings 2–4) | 7 |
| Compose's preview and focus's zone (§7.6; rulings 5, 6) | 7 |
| The shaders in Chromium; every screenshot with its effects, compared by eye; §14's frame rate with them | 8 |
| Review Focus 1 to 5 | 2, 5, 6, 7 |
| CLAUDE.md revised | 9 |
| Rebase over master and engine M8, every gate, the PR | 10 |
| The owner previews each of the eleven particle looks on the real engine (ruling 19) | 11 |
| Sun shafts, the doorbell's ring, map mode, plane `width`, the rest of the M10 pass | Hand-off |
