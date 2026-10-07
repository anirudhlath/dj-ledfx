# F4 Web App Put a Look On Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put a look on works, on both sizes. From Live, `L`, **Put a look on**, a room clicked on the stage, a card's **Change look** or Zone detail's **Change** opens the composer at `/live/put?zone=&look=`. It has Where (`ZonePicker`), What (search, categories and `LookTile`s on desktop, look rows on the phone) and How (the transition, the consequence line, **Cancel** and **Start**). Choosing a look previews it on the stage at once, in `compose` mode, while the lights keep what they run until Start. Done when a look starts in three clicks from Live, and the mock shows the lights unchanged until Start.

**Architecture:**
- One backend change. `POST /api/preview` answers `lights` beside `previewId`: what each of the zone's lights would do if the look started now (`PreviewLight {id, mode, effect}`). The preview's runtime already knows this. The consequence line needs it to say which lights would run their own effect and which a streamed copy, and nothing else serves it (F4 ruling 1). `npm run api:types` regenerates the types, and the mock answers the same way (ruling 2).
- `src/api/preview.ts`'s `PreviewSession` is the composer's one preview. It asks for one preview at a time, so the last choice wins. It watches the preview stream while a preview is on, and ends the preview with `DELETE` when the composer goes. When the link comes back, it asks for the preview again. `usePreview(zoneId, lookId)` ties it to the composer's life.
- `src/compose/` holds the composer:
  - `model.ts` and `consequence.ts` are pure: the zone chosen, the zones' notes, the looks shown, the inputs a look would wait for, the transitions, and the consequence's words.
  - `use-composer*.ts` keep its state in the URL and handle the keys.
  - `ZonePicker`, `LookTile`, `LookRow`, `ComposerPanel` (desktop, in the Running panel's place) and `ComposerSheet` (phone) draw it.
  - `src/looks/look-thumb.tsx` is `LookThumb`, a plain tile until F5 draws the motifs.
- The stage gets `compose` mode (§7.6):
  - the rooms outside the chosen zone are dimmed, and the zone is outlined;
  - the zone's lights draw the preview stream while a preview is on;
  - a room click chooses its zone;
  - the PREVIEW ON SCREEN card shows on desktop, and a tag on the phone.
  - `stageBehaviour()` says what each part does, as it does for the other modes.
- `/live/put` is a child of Live's route with no element, as `/live/zones/:zoneId` is, so the stage stays mounted. On the phone it's a focused task (`PageMeta.focusedTask`), with no header and no tab bar.

**Tech Stack:**
- Unchanged from F3: Vite 8, React 19, TypeScript 5.9 (strict, `erasableSyntaxOnly`, `verbatimModuleSyntax`), react-router 7, zustand 5, TanStack Query 5, Base UI 1.8, Tailwind v4, MSW, Vitest, Playwright with axe. Task 1 changes FastAPI and Pydantic code, with pytest.
- No new dependencies. The transition select is F0's `Select` (Base UI's).

**Spec:**
- `docs/superpowers/specs/2026-09-23-web-app-rebuild-design.md`:
  - §13.1, row M4: "Put a look on: composer, `ZonePicker`, `LookTile`, preview stream in `compose` mode, consequence line, transitions, Start / Cancel". It's done when "Start a look in ≤ 3 clicks from Live; lights unchanged until Start (mock asserts)".
  - Sections read for this plan: §2, §4.3, §4.4, §6.3 (`ZonePicker`), §6.4, §7.2, §7.6, §8.2, §8.10, §9, §10, §11.1, §11.3, §12, §14.
- `docs/superpowers/specs/2026-09-23-home-effects-engine-design.md` §10: "F4 Put a look on | M1 zones; M2 preview runtimes and frame protocol v2".
- The renders, in the main checkout: `/home/anirudhlath/code/private/dj-ledfx/docs/design/web-app/reference/`. F4 has two, `Live-PutLookOn` (desktop) and `Phone-PutLookOn` (phone), each `.png` with its `.html` beside it.
- F3's hand-off: `docs/superpowers/plans/2026-10-03-f3-live.md`, "Hand-off", "F4 (Put a look on)".

**What exists** (master at `d6f959e`):
- Engine M2 serves previews:
  - `POST /api/preview {zoneId, lookId | look}` → `{previewId}`, which replaces any previous preview; `PUT` and `DELETE /api/preview/{previewId}`.
  - Frame protocol v2's `preview` stream.
  - A preview nobody watches ends after 10 s.
- The web app's side of it:
  - `src/api/rest.ts` has `api.startPreview`, `api.updatePreview` and `api.stopPreview`.
  - `FrameStore` keeps the `preview` stream apart, and `clearPreview()` drops it.
  - The live client's frame streams are "`live` alone until F4 opens a preview, then `preview` too while it's open".
- Engine M4: a start takes a `transition` (`StartRequest`), and a running zone's transition has `durationS`.
- F3 already links to `/live/put`, from the Running panel's and the phone's **Put a look on**, a card's **Change look**, Zone detail's **Change** and **Put a look on**, Nothing running, and a room clicked on the stage (`composerFor` in `stage/stage.tsx`). The route draws F0's placeholder.
- `SPEC.compose {dimmed, outlinePx}` is generated (F3 Task 1). `ZoneOutline` draws the hovered zone's outline, from `zonePolygons()`.

**Execution:** in a new worktree, `~/code/.worktrees/dj-ledfx/web-f4`, on branch `feature/web-f4-put-a-look-on`, from `origin/master` (Before Task 1), by the method the owner picks. After Task 12 opens the PR, the run's own final review of the whole branch runs: fix every finding it raises and push the fixes to the PR. Then stop.

**How to read the code.** A new file is given whole after "Create". A change to an existing file is a unified diff, in a `diff` block, against the file as master at `d6f959e` and the earlier tasks leave it; apply the blocks in the order given. Save a block to a file and run `git apply` on it (`git apply /tmp/f4-step.diff`), or make the same edit by hand. If master has moved past `d6f959e` and a block no longer applies, make the edit by hand: its hunks say where. Every block was applied, and every count below measured, on a copy of `d6f959e`; a newer master may add tests. Two kinds of file are never written by hand: `web/src/api/generated/*` (`npm run api:types` writes them, in Task 1) and `web/src/design/live-numbers.ts` (`npm run design:numbers`, in Task 2). Task 10's screenshots are recorded by Playwright.

---

## Global Constraints

Every task's requirements include this section. Quotes are the spec's or CLAUDE.md's own words, with their sections.

**Source of truth**
- CLAUDE.md, "Web App Design":
  - "The Claude Design handoff is the only source of design truth. Don't work from memory, a summary or an earlier conversation."
  - "Behaviour, structure, data contract and copy: the web app spec. Look and layout: the reference renders."
  - "Use `tokens.css`, `icons.ts`, `looks.json` and `home.json` as they are … Never retype a token, colour, size, icon path or look description, and never restate design values in docs or in this file."
- How code reaches a design value. Pick the first of these that has it:
  - a token utility (`text-display-sm`, `rounded-card`, `h-(--touch-min)`, `touch-target`);
  - the Tailwind spacing class F0–F3 used for a render's size;
  - a generated number:
    - `SPEC`, `RENDER` and `TOKENS` from `src/stage/design-numbers.ts`, in the stage's chunk only;
    - `LIVE_SPEC` and `LIVE_RENDER` from `src/design/live-numbers.ts`, everywhere else. Task 2 adds the composer's.
  - only where none of those has it, an arbitrary Tailwind value (`w-[…]`, `text-[…]`) holding the render's own measurement. The code's comment says which render it comes from.
  - This plan names numbers by those keys and never states them. `npm run design:numbers` writes both files. Never edit them by hand.
- CLAUDE.md, Gotchas: "where tokens.css has a token, use its utility … never an arbitrary value equal to it".
- CLAUDE.md: "Before each web app task, re-read the spec sections and look at the renders that the task names."
  - Each task's Step 1 names them.
  - View each PNG once per task and write down what you see.
  - Where a picture can't settle something (a font run, a colour, what a state leaves out), read the HTML beside it.
- The byte copies (`tokens.css`, `icons.ts`, `looks.json`, `home.json`) change only by `cp`, and F4 changes none.
- §10 Copy:
  - "Names from the backend verbatim". A look's, a zone's and a light's names come from the server (the mock's fixtures in tests), never typed.
  - The words are look, zone, light, Off, Stop all, Put a look on, Preview only, Needs attention. Text is in sentence case, except the caps labels the renders draw (PREVIEWING, RUNNING HERE, PREVIEW ON SCREEN).
  - Copy is the spec's: §8.2, §8.10, §10 and §11.3. Where the spec gives none, it's the render's. Copy this plan writes itself is listed in "Decisions already made" (ruling 14 holds most of it).
  - Apostrophes are straight (`'`), as the spec writes them. A quoted search takes the renders' curly quotes (“…”).

**The data contract** (§12, CLAUDE.md)
- §12: "Components never call `fetch` or touch the socket directly."
  - Start goes through `src/api/actions.ts` (`startLook`).
  - The preview goes through `src/api/preview.ts`'s `PreviewSession`. It alone calls `api.startPreview` and `api.stopPreview`, and asks the live client for the preview stream.
- §7.5: "No React state per frame". The preview's frames reach the stage through the frame store, as the live ones do; `FrameWriter` reads each light from the stream its entry names.
- CLAUDE.md: "the chrome and the pages read the live store a slice at a time (`useLive(selector)`)". A slice the inputs heartbeat replaces every second with an equal copy goes through `useLiveBy(selector, same)`.
- What the engine serves:
  - M1: zones and take-over. M2: previews, frame protocol v2's `preview` stream, a preview ended after 10 s unwatched, and the PC as one light with parts. M4: a start's `transition`.
  - The engine refuses a whole-home look at preview and at start until M6: `validate_look` says "Home looks (whole-home scope) arrive in M6" (400). The mock allows them (ruling 3).
  - It refuses a zone with no lights the same way: "<zone> has no lights" (400). The mock does too, from Task 1.
  - Engine M5 (particles) is planned beside this plan. Until it merges, the engine serves no particle look, so the composer lists only what `GET /api/looks` serves.
  - F4 adds one field to one answer (Task 1), with its tests and the regenerated types, in one commit (CLAUDE.md: "a backend API change … needs `cd web && npm run api:types` in the same commit").

**Quality** (§13.1, §14)
- Done when: "Start a look in ≤ 3 clicks from Live; lights unchanged until Start (mock asserts)". Task 8's "starts a look in three clicks from Live, and leaves the lights alone until Start" pins both: Put a look on, a tile and Start, with the mock's lights unchanged until the Start.
- §14:
  - Unit: "take-over consequence text" (Task 4).
  - Components: "composer flow" (Tasks 8 and 9).
  - Accessibility: axe on every route (`/live/put` is already in `e2e/shell.spec.ts`'s routes) and on every new popup (Task 10); "full keyboard path through Live → composer → Start" (Tasks 8 and 10); "contrast from 5.1 holds" (ruling 19).
  - Visual: each state on both sizes, compared with its render by eye before its baseline is recorded (Task 10).
  - Performance: "first load < 400 KB gzipped JS excluding three.js". `npm run build` checks the budget.
- A popup that portals out of `<main>` joins `OVERLAYS` in `e2e/shell.spec.ts`. A control drawn smaller than `--touch-min` gets `touch-target` (CLAUDE.md, Gotchas).

**Public repo and live system**
- The repo is public. None of these may appear in the plan, the code, the tests, CLAUDE.md, the commit messages or the PR: LAN addresses, MACs, SSIDs, light names, light model names, the home's location or AI model names.
- Room names and look names come only from the design files, never retyped. Tests read them from the fixtures; e2e paths carry ids.
- "The deployed `dj-ledfx-app-1` is never touched". F4 runs on the mocks, the dev server and the test suites: no docker, no lights, no UFW and no master.

**Workflow** (CLAUDE.md)
- The executor works in `/home/anirudhlath/code/.worktrees/dj-ledfx/web-f4`, on branch `feature/web-f4-put-a-look-on`, made in "Before Task 1". It works nowhere else.
- Run commands from the worktree root, and web commands in a subshell: `(cd web && …)`.
- During a task, run only the task's own test files. Run the gate once, before the task's commit, as its last step says.
- e2e uses :4174 and :4175 with `strictPort`, so only one worktree can run it at a time. Before every `npm run e2e`, wait until neither port is taken, for ten minutes at most:

  ```bash
  for i in $(seq 1 60); do [ "$(ss -ltn | grep -cE ':(4174|4175) ')" = 0 ] && break; sleep 10; done; ss -ltn | grep -cE ':(4174|4175) '
  ```

  It must print `0`. If it doesn't, another worktree is still running e2e: run the loop again.
- Python: `uv` only (`uv run …`, `uv sync --extra web`). Python changes only in Task 1.
- Lines run to about 140 characters. There's no formatter. `erasableSyntaxOnly` rules out enums and parameter properties. `verbatimModuleSyntax` needs `import type` for types.
- ESLint has no type-aware rules. It enforces two sets that bite here:
  - react-refresh: a `.tsx` file exports only components, so a hook or helper that component files share goes in a `.ts` file (`use-composer.ts`, `model.ts`);
  - the React Compiler's rules: no ref read during render, no `Date.now()` in render, and no setState called straight from an effect.
- `cx()` joins class names and merges none. To override a primitive's own class, use Tailwind's important suffix (`h-9!`).
- Vitest's fake timers hang `userEvent`, so a test on fake timers drives the page with `fireEvent` (Task 8 explains it, and Task 11 adds it to CLAUDE.md).
- Context7 needs authorizing and was unavailable while this plan was written. F4 uses no outside API that F0–F3 don't already use. Where Base UI's behaviour mattered (a Select's Esc, its focus guards), the plan's tests and e2e measured it (Tasks 8 and 10).

## Decisions already made

These fill gaps in the spec. The owner sees them in the plan's report, and should look at rulings 1, 3, 4, 5, 6, 7, 11, 16, 18 and 19 in particular. Reviewers: don't reverse one without asking. Code comments cite them as "F4 ruling N".

1. **The consequence line's lights come from the preview's answer.** [owner]
   - §8.2's example consequence names the lights that would run the look's built-in effect. What a light does in a look (its own effect, a streamed copy, or the look's frames) depends on the light and the look, and only the engine knows it: its runtime's `mode_of()` and `effect_name()`. The preview's runtime already has the answer.
   - So `POST /api/preview` answers `lights: PreviewLight[]` beside `previewId`. Each one is `{id, mode, effect}` for a light of the zone. `mode` is `LightMode` (`own-effect`, `streamed-copy` or `streaming`), and `effect` is the built-in effect's name (null while streaming).
   - The PC answers as one light, as its most active part does: an own effect over a streamed copy over streaming.
   - It isn't in the web spec's contract, and the contract model's docstring says so.
   - The take-overs ("Takes over the … from …", §11.3) are worked out in the client from `running`. §11.3 says "A light is in at most one running zone", and the newest start wins.
2. **The mock tells the same** (`lightPlan()` in `mocks/fixtures.ts`).
   - In the firmware look, each light runs its first own effect, or gets a streamed copy of `COPIED_EFFECT` when it has none. The `firmware` scenario has run them so since F3, and now asks `lightPlan()` too.
   - In any other look, a light runs the built-in effect the look's description names, when it has that effect. Otherwise it streams.
   - The mock refuses a preview or a start on a zone with no lights, with the engine's words.
3. **The engine refuses a whole-home look until M6.** [owner]
   - `validate_look` answers 400, "Home looks (whole-home scope) arrive in M6", at preview and at start.
   - The composer says the refusal where the consequence goes (ruling 14's "Couldn't preview <look>. …"), and keeps **Start** enabled. Start announces its own failure, so the composer shows each refusal the server makes, and starts working on the day M6 lands.
   - The mock allows both, because the hero runs a home look over everything (State-Sheet's overlay).
4. **Each zone's note** (§6.3 ZonePicker: "Each chip shows what's running there in small text"). [owner]
   - It's the zone's own look, else the newest look on any of its lights, else "idle".
   - A room never says a sub-zone's look, as the stage's labels have it.
   - A zone with no lights says "no lights".
   - Both sizes use this rule. Live-PutLookOn draws notes only on the zones that run their own look. Phone-PutLookOn's "idle" and "no lights" are where the words come from.
5. **The zones come in the server's order** (`GET /api/zones`), on both sizes. [owner]
   - The renders order them otherwise, and the phone's puts the chosen zone first.
   - On the phone the chosen zone is scrolled into view: to the row's start as the composer opens, then as little as it takes as the choice changes.
6. **"Pick lights…" is drawn, and does nothing.** [owner] It's dashed with its `plus` icon, `aria-disabled`, and inert. Picking lights for a custom group has no render and no milestone yet.
7. **`LookThumb` is a plain tile until F5.** [owner]
   - §6.4 asks for `(lookId, size, live?: boolean)`. F4's `LookThumb({lookId, size})` draws the scene's tile, shaped as `LIVE_RENDER.lookThumb`'s width and height and filled with its `background`, with no motif, keyed by the look's `thumbnail` (`data-thumb`), and `aria-hidden`.
   - The tile's size is `tile`, as wide as the `LookTile` holding it; the phone's `row` is `LIVE_SPEC.phoneComposer.thumb`.
   - F5 adds each look's motif and `live`, with no caller changing.
   - Nothing running's Start again keeps its own plain tile (F3 decision 27) until F5 swaps in `LookThumb` with its motif.
8. **The inputs a look would wait for** are judged only where the server sends them (§8.2: "A look whose input is missing stays selectable").
   - Music is missing while it's disconnected, idle or has no track. A stale one isn't: it holds its last value.
   - Home Assistant is missing while it's disconnected.
   - The tempo never is: the clock always runs. The sun isn't served before M6, so it never is either.
   - With `inputs` not loaded, nothing is missing.
   - A tile says the first missing input's words in signal: "Waits for music" or "Needs Home Assistant" (§8.2).
   - The consequence line says the waiting card's sentence (F3 decision 13, `waitingText()`).
9. **The URL holds the zone and the look** (§4.3: "the composer's zone and look … live in the URL so reload and back work").
   - Every choice replaces the URL's entry (`replace`), so Back leaves the composer whole.
   - The zone is `?zone=` (the room clicked, or the card's zone). Otherwise it's the last zone started on in this browser (`localStorage`, written at Start), otherwise the whole home. A zone that's gone is passed over.
   - A home look locks the zone to the whole home (§8.2: "Home looks (whole-home scope) lock the zone to Whole home").
   - The search, the category and the transition live in the component.
10. **The categories and the search.**
    - The composer opens on the chosen look's category, else the category of the look running on the zone, else Ambient.
    - A search spans every category and presses no chip.
    - A chip clears the search.
11. **The transitions** (§8.2: "Cut, Fade, Wipe, Spread, Dissolve + duration; default the look's own"). [owner]
    - The select offers Cut, then Fade, Wipe, Spread and Dissolve, each at 1, 3 and 5 s (`TRANSITION_SECONDS`), labelled as the cards label a transition (`transitionLabel()`).
    - The default is the look's own, or Cut for a look with none. A look's own length that isn't on the list is offered after its kind's others.
    - The chosen transition is always sent with Start (`StartRequest.transition`).
    - Live-PutLookOn shows a dissolve chosen. The screenshots show each look's own default.
12. **The keyboard** (§8.2: "Keyboard: `L` opens the composer from Live; arrows move through tiles; Enter starts; Esc cancels").
    - `L` opens the composer, unless it's typed into a field or comes with Ctrl, Alt or Meta.
    - The composer gives the chosen look's tile the focus as it opens, else the first tile's. The tiles are one tab stop.
    - The arrows move through the tiles and choose as they move, so the preview follows. Left and Right move by one tile, Up and Down by a row of the grid; on the phone, Up and Down move by one row.
    - Enter starts the chosen look.
    - Esc closes the composer, unless something inside it took the Esc first: an open list closes, and a search clears.
13. **Start, Cancel and Close.**
    - Start sends `startLook(zone, look, transition)`, which writes the answer into the live store at once (the zone as the newest, and the lights it took off the others), as `startAgain` does.
    - Then it remembers the zone (ruling 9), announces "Started <look> on <zone>.", and goes back to `/live` (`replace`), which ends the preview.
    - A failure announces "Couldn't start <look>. <the server's detail>", and the composer stays.
    - Start is disabled while no look is chosen, on a zone with no lights, and while a start is on its way.
    - Cancel (desktop) and Close (both sizes) go back to `/live` (`replace`). The lights stay as they were.
14. **The consequence line's words** (§8.2's "explanation of consequences"; §11.3: "The UI must show the consequence before Start"). Look names are in serif italic, as the renders draw them.
    - "Takes over the <zone> from <look>." with every look it takes lights from, newest first, and the zone's own look when it's another one ("<a>, <b> and <c>").
    - "Starts <look> again on the <zone>." when the zone runs it already.
    - "Nothing runs on the <zone> now." when nothing runs there.
    - "<look> stops." or "<a> and <b> stop." for each zone left with no lights (§11.3: "A zone left with no lights stops").
    - "<Lights> will run <effect>." for the lights that would run their own effect, then "<Lights> will get a streamed copy of <effect>." The lights are "the <name>". Numbered lights of one name fold into "the <name>s" when all of them are there. More than three names become "<n> lights".
    - The waiting sentence, for a look that would wait (ruling 8).
    - The whole home is "the whole home".
    - With no look chosen: "Choose a look to see it on the stage first." On a zone with no lights: "The <zone> has no lights." Both hold Start.
    - A refused preview: "Couldn't preview <look>. <the server's detail>" (ruling 3).
    - The phone's one line (Phone-PutLookOn) is the waiting sentence, else "Takes over from <look>", else "Starts <look> again", else "Nothing runs here now".
15. **The stage in `compose`** (§7.6: "Rooms outside the chosen zone dimmed to …; chosen zone outlined in … `text`; the chosen zone renders the **preview stream** instead of live; a "PREVIEW ON SCREEN" tag says the lights are still running the old look").
    - The rooms outside the zone are dimmed by `SPEC.compose.dimmed`, and the zone is outlined at `SPEC.compose.outlinePx` in `text`, through `ZoneOutline`'s polygons (F2's hand-off).
    - While the preview is on for the zone, its lights draw the preview stream, whatever they'd run. Every other light stays live.
    - The room labels name the previewed look on its zone, as the newest there. The chosen zone's labels are all `text` and the others' all `text-3`, as Live-PutLookOn draws them.
    - The card says "<look> on <zone>. The lights are still running <look>." (Live-PutLookOn's words, every look the zone's lights run, its own first), or "The lights are as they were." where nothing runs on them. The phone's tag says §8.10's "PREVIEW ON SCREEN · LIGHTS UNCHANGED", in sentence case under `uppercase`.
    - A room click chooses its zone and keeps the look (§6.3: "Clicking a room on the stage selects the same zone").
    - The stage's interactive layer stays Live's: in the composer there are no tools, sun readout or view controls, no hover tooltip, no zone tags and no room links.
    - Desktop keeps Live's stored view (3D or Plan, and the pose), and draws the legend (Live-PutLookOn draws it), the labels as the Labels switch says, and the sun's label. The card sits beside the zone, left of it where it fits, else right, else over it, and only while the preview is on.
    - The phone frames the zone as `focus` does (§7.2: "Focus framing (zone detail, editor preview, composer on phone)"), keeping the other lights, with no vignette and no labels, and puts the tag at the stage's top left (Phone-PutLookOn).
16. **The phone's layout.** [owner]
    - `/live/put` is a child of Live's route with no element, so the stage stays mounted from Live to the composer.
    - The stage keeps Phone-Live's box (`LIVE_SPEC.phoneStage`), where Phone-PutLookOn draws it shorter, so it never resizes on the way in. The sheet overlaps the stage's foot, as the render draws it.
    - It's a focused task (`PageMeta.focusedTask`): no header and no tab bar, as §8.10 says of Phone-Map ("No tab bar (a focused task)") and Phone-PutLookOn draws. The sheet's title is the page's `h1`.
    - The footer pads below as the render does. On a phone with a home indicator, the OS's inset adds below that.
17. **Icons** (`icons.ts`): `plus` (Pick lights…), `eye` (the PREVIEWING tag and the preview's card and tag), `x` (Close), `search`, `layers` (the consequence line), `play` (Start), and `check` (the phone's chosen row).
18. **The looks come in the server's order** (`GET /api/looks`), within a category and in a search, where Live-PutLookOn's grid orders them otherwise. [owner]
19. **Text on a `control` fill is `text-2`.** [owner] The renders draw the zone chips' notes and the phone's chosen row's line in `text-3` on `control`, which falls short of §14's "contrast from 5.1 holds". F4 draws them in `text-2`. axe on `/live/put` pins it.
20. **axe leaves out Base UI's focus guards in one overlay test.** (This is test-side only.)
    - axe's aria-hidden-focus rule excuses the guards only while it takes the page for a modal one. It decides that by finding a fixed layer under each of five points it samples.
    - The transition list's backdrop leaves a hole over its trigger, and the phone's trigger sits on one of the points.
    - So that `OVERLAYS` entry excludes `[data-base-ui-focus-guard]`, and says why.

## Review Focus

These are the five failure modes the spec implies that are most likely to bite someone putting a look on, most likely first. Each has a test in the task that owns the code.

1. **Choices outrun the server.** Arrows held down, or tiles clicked fast.
   - Expected:
     - One preview request at a time. A choice made while one is on its way is asked for when it's answered, and only the last choice is.
     - The stage shows the last choice, never an answer that came late.
     - The preview that ends is the server's current one.
   - Pinned in: Task 3: "asks for one preview at a time, and the last choice wins", and "drops an answer to a request made before a reset".
2. **The server refuses the preview.** The causes: a whole-home look before M6, a zone with no lights, another 400, a 500, or no answer at all.
   - Expected:
     - The consequence line says why: "Couldn't preview <look>. <the server's detail>".
     - The preview before it ends, and its frames go, so the stage never shows a preview that isn't the choice.
     - Nothing is asked again for that choice.
     - Start stays, and says its own failure if the start is refused too.
   - Pinned in:
     - Task 3: "says why the server refused, ends the preview before, and doesn't ask again";
     - Task 4: "says why the server refused the preview, and leaves Start to say it again";
     - Task 8: "says why the preview was refused, and leaves Start to try".
3. **Leaving without Cancel.** Back, the rail, the tab bar, or a click on a card's link.
   - Expected: the preview ends with `DELETE`, the preview stream is unwatched, its frames go, and the lights stay as they were.
   - Pinned in:
     - Task 3: "previews while its component is mounted, and ends the preview after";
     - Task 8: "ends the preview when Back leaves".
4. **The link drops during a preview.**
   - Expected:
     - The stage freezes, as Live's does.
     - When the link is back, the preview is asked for again: the engine ended the unwatched one after 10 s. The preview stream is watched again.
   - Pinned in: Task 3: "asks for the preview again when the link comes back".
5. **Esc inside the composer.**
   - Expected:
     - Esc in the transition list closes the list, and only the list.
     - Esc in the search clears it.
     - The next Esc closes the composer.
   - Pinned in: Task 8: "closes only the transition list on an Esc in it", and "opens on L, chooses on the arrows, starts on Enter and closes on Esc".

## File Structure

```
src/dj_ledfx/
  zones/preview.py               Modify: PreviewLight, preview_lights(), PreviewManager.lights()
  web/contract.py                Modify: PreviewLight; PreviewStarted.lights; preview_started(), the PC as one light
  web/router_preview.py          Modify: POST /preview answers the lights
tests/
  zones/test_preview.py          Modify
  web/test_preview_api.py        Modify
web/
  scripts/
    design-extract.ts            Modify: LIVE_SPEC.lookTile and phoneComposer; LIVE_RENDER.lookThumb and selectedZoneNote
  src/
    design/
      live-numbers.ts            Regenerate (npm run design:numbers)
      overlays.tsx               Modify: Grabber, which Sheet and the composer's sheet share
    api/
      generated/*                Regenerate (npm run api:types)
      contract.ts                Modify: PreviewLight
      actions.ts                 Modify: startLook(); storeStarted(), which startAgain shares
      preview.ts                 Create: PreviewSession, PreviewState, PREVIEW_IDLE
      use-preview.ts             Create: usePreview(), usePreviewState()
      live.ts                    Modify: previewSession, resumed on a resync and reset with the data layer
      mocks/fixtures.ts          Modify: COPIED_EFFECT, lightPlan()
      mocks/mock-server.ts       Modify: the preview's lights; a zone with no lights refused
      mocks/scenarios.ts         Modify: the firmware scenario's lights through lightPlan()
    lib/
      storage.ts                 Create: browserStorage() (moved from stage/view-memory.ts)
    zones/
      zone-view.ts               Modify: waitingText() and transitionLabel() exported
    stage/
      behaviour.ts               Modify: `compose`; roomClick, framesComposeZone, legend, previewTag
      frame-writer.ts            Modify: each entry's stream
      labels.ts                  Modify: the previewed look; looksOn()
      zone-shape.ts              Modify: zoneRooms(), boxOf(), besideZone()
      view-memory.ts             Modify: browserStorage() from lib/storage.ts
      overlays/stage-svg.tsx     Modify: compose's dims and outline; the chosen room's label
      overlays/zone-outline.tsx  Modify: ZoneDims
      overlays/preview-tag.tsx   Create: PreviewCard (desktop), PreviewTag (phone)
      stage-view.tsx             Modify: StageCompose, and compose mode
      stage.tsx                  Modify: passes compose through; a room's composer path keeps the look
    looks/
      look-thumb.tsx             Create: LookThumb, a plain tile until F5
    compose/
      model.ts                   Create: the composer's pure model
      consequence.ts             Create: the consequence line's words
      last-zone.ts               Create: the last zone used
      look-tile.tsx              Create: LookTile (§6.4)
      look-row.tsx               Create: LookRow (Phone-PutLookOn)
      zone-picker.tsx            Create: ZonePicker (§6.3)
      consequence-text.tsx       Create: ConsequenceText, the line in its fonts
      use-composer.ts            Create: useComposeChoice(), useStageCompose(), useRunning(), useComposer()
      use-composer-view.ts       Create: useComposerView(), what the panel and the sheet share
      use-composer-keys.ts       Create: useComposerKeys(), L and Esc
      composer-panel.tsx         Create: ComposerWhere and ComposerPanel (desktop)
      composer-sheet.tsx         Create: ComposerSheet (phone)
    live/
      nothing-running.tsx        Modify: its comment says F5 swaps LookThumb in
    pages/
      live.tsx                   Modify: the composer in the panel's place; the phone's sheet
    app/
      routes.tsx                 Modify: /live/put a child of Live, with its PageMeta
      page-meta.ts               Modify: focusedTask
    shell/
      app-shell.tsx              Modify: a focused task hides the phone's header and tab bar
    test/
      live.ts                    Modify: restOn(), and pushFrame()'s stream
  e2e/
    helpers.ts                   Modify: open() waits for the composer's Looks group too
    shell.spec.ts                Modify: the notched phone's race; the transition list joins OVERLAYS
    compose.spec.ts              Create: every state on both sizes, the keyboard, the sizes
    compose.spec.ts-snapshots/   Create: the baselines (Playwright records them)
CLAUDE.md                        Modify (Task 11)
```

Tests sit beside the code they test. A `*.node.test.ts` file runs in Node and is type-checked by `tsconfig.node.json`.

## Before Task 1

- [ ] **Step 1: Make the worktree**

```bash
git -C /home/anirudhlath/code/private/dj-ledfx fetch origin
git -C /home/anirudhlath/code/private/dj-ledfx worktree add -b feature/web-f4-put-a-look-on /home/anirudhlath/code/.worktrees/dj-ledfx/web-f4 origin/master
W=/home/anirudhlath/code/.worktrees/dj-ledfx/web-f4; cd "$W"
test -f web/src/live/running-panel.tsx && grep -q 'milestone="F4"' web/src/app/routes.tsx && echo "F3 is here, F4 isn't"
git log --oneline -3
```

Expected: "F3 is here, F4 isn't". The log's newest commit is master's (`d6f959e` when this plan was written, or newer).

- [ ] **Step 2: Install, and check the pins**

```bash
uv sync --extra web
(cd web && npm ci)
(cd docs/design/web-app && sha256sum -c --ignore-missing HANDOFF.sha256 | grep -v ': OK$'; echo "pins checked")
(cd /home/anirudhlath/code/private/dj-ledfx/docs/design/web-app && sha256sum -c HANDOFF.sha256 2>/dev/null \
  | grep -E 'reference/(Live|Phone)-PutLookOn\.(html|png): ' | grep -v ': OK$'; echo "renders checked")
```

Expected: "pins checked" and "renders checked", with no line between them. A render that fails its pin stops the plan: tell the owner.

- [ ] **Step 3: Record the baselines**

```bash
(cd web && npm test 2>&1 | tail -4 && npm run lint && npx tsc -b && echo "tsc ok" && npm run api:check && npm run build 2>&1 | tail -1)
uv run pytest -q -p no:randomly 2>&1 | tail -1
uv run ruff check . && uv run ruff format --check . 2>&1 | tail -1
uv run mypy src/ 2>&1 | tail -1
```

Expected: everything passes. On `d6f959e`:
- Vitest: 716 tests in 91 files;
- the build: `…/web/dist: no mocks, 272.4 KB of gzipped JS`;
- pytest: `2029 passed, 1 skipped, 42 deselected`, with FastAPI's warnings;
- ruff: `All checks passed!` and `339 files already formatted`;
- mypy: `Found 16 errors in 4 files (checked 153 source files)`. That's the baseline: F4 adds none.

Write down this master's own numbers. The counts below are those of `d6f959e`, and a newer master adds its own to each.

- [ ] **Step 4: Record the Playwright baseline**

```bash
for i in $(seq 1 60); do [ "$(ss -ltn | grep -cE ':(4174|4175) ')" = 0 ] && break; sleep 10; done; ss -ltn | grep -cE ':(4174|4175) '
(cd web && npx playwright install chromium && npm run e2e 2>&1 | tail -3)
```

Expected: the first command prints `0` (Global Constraints, Workflow). Then all pass: 90 passed and 48 skipped on `d6f959e`. Write the counts down.

`a notched phone keeps its chrome inside the safe area` can fail with `["nav left"]`. That happens when the stage's chunk loads before the test measures: the stage's room links are a hidden `nav` one pixel outside the screen. It's a race in master's test, and the composer makes it likely, so Task 8 fixes it. If it fails that way before Task 8, run e2e again.

---

### Task 1: The preview says what each light would do

The consequence line has to say which of the zone's lights would run their own effect and which a streamed copy, before anything reaches a light (§8.2, §11.2). Only the engine knows that, and the preview's runtime has already worked it out. So `POST /api/preview` answers it, the generated types follow, and the mock answers the same way (F4 rulings 1 and 2). It's the only backend change in F4.

**Files:**
- Modify: `src/dj_ledfx/zones/preview.py`, `src/dj_ledfx/web/contract.py`, `src/dj_ledfx/web/router_preview.py`
- Test: `tests/zones/test_preview.py`, `tests/web/test_preview_api.py`
- Regenerate: `web/src/api/generated/openapi.json`, `web/src/api/generated/schema.d.ts`
- Modify: `web/src/api/contract.ts`, `web/src/api/mocks/fixtures.ts`, `web/src/api/mocks/mock-server.ts`, `web/src/api/mocks/scenarios.ts`
- Test: `web/src/api/mocks/mock-server.test.ts`

**Interfaces:**
- Consumes:
  - `ZoneRuntime.lights`, `mode_of(device_id)` and `effect_name(device_id)` (`zones/runtime.py`);
  - `LightIndex.light_of(device_id)`, through `web/state.py`'s `light_index(app)`;
  - in the mock: `Light.builtInEffects`, `Look.category` and `Look.description`.
- Produces:
  - `zones.preview`: `PreviewLight(device_id, mode, effect)`, frozen; `preview_lights(runtime) -> tuple[PreviewLight, ...]`; `PreviewManager.lights(preview_id)`, which raises `PreviewNotFoundError` for a preview replaced or ended.
  - `web.contract`: `PreviewLight {id, mode: LightMode, effect: str | None}`; `PreviewStarted.lights: list[PreviewLight]`; `preview_started(preview_id, lights, index) -> PreviewStarted`, the PC as one light.
  - `web/src/api/contract.ts`: `type PreviewLight`. `PreviewStarted` gains `lights` from the generated types.
  - `web/src/api/mocks/fixtures.ts`: `COPIED_EFFECT`, and `lightPlan(look, light): Omit<PreviewLight, 'id'>`.

- [ ] **Step 1: Read the spec and the engine**

Read §8.2 (How, and "Data"), §9.1 (own effects and streamed copies), §11.2, §11.3 and §12.3's preview rows. Then read `src/dj_ledfx/zones/preview.py`, the `mode_of()` and `effect_name()` docstrings in `src/dj_ledfx/zones/runtime.py`, and `PreviewStarted` in `src/dj_ledfx/web/contract.py`. Look at `Live-PutLookOn.png`'s consequence line once.

- [ ] **Step 2: Write the failing tests**

In `tests/zones/test_preview.py`:

```diff
--- a/tests/zones/test_preview.py
+++ b/tests/zones/test_preview.py
@@ -6,11 +6,12 @@ from typing import Any
 
 import pytest
 from conftest import FakeLight
-from zone_home import FakeHome, Home, HomeFactory, zone_record
+from runtime_fakes import LAMP, TILE
+from zone_home import BREATHE_AND_GLOW, GLOW, FakeHome, Home, HomeFactory, zone_record
 
 from dj_ledfx.looks.model import LookError
 from dj_ledfx.zones.model import ZoneError, ZoneNotFoundError
-from dj_ledfx.zones.preview import PreviewManager, PreviewNotFoundError
+from dj_ledfx.zones.preview import PreviewLight, PreviewManager, PreviewNotFoundError
 
 
 class Watch:
@@ -157,3 +158,30 @@ async def test_a_preview_follows_the_map_a_backup_brings(make_home: HomeFactory)
     await home.manager.replace_state(restore)
 
     assert previews.runtimes() == [] and home.host.hosted == []
+
+
+# F4 ruling 1: the composer's consequence line names the lights that would run a firmware
+# effect, and the ones that would stream a copy of it, before anything reaches a light.
+async def test_a_preview_says_what_each_light_would_do(make_home: HomeFactory) -> None:
+    tile, lamp = FakeLight("tile", caps=TILE), FakeLight("lamp", caps=LAMP)
+    home = await make_home([tile, lamp], [zone_record("z", "tile", "lamp")])
+    tile.calls.clear()
+    lamp.calls.clear()
+    previews = _previews(home, Watch())
+
+    glow = previews.start("z", GLOW)
+
+    assert previews.lights(glow) == (
+        PreviewLight("tile", "own-effect", "Glow"),
+        PreviewLight("lamp", "streamed-copy", "Glow"),  # no field layer: it streams a copy
+    )
+    with_field = previews.start("z", BREATHE_AND_GLOW)
+    assert previews.lights(with_field) == (
+        PreviewLight("tile", "own-effect", "Glow"),
+        PreviewLight("lamp", "streaming", None),  # it plays the field layer
+    )
+    waiting = previews.start("z", replace(GLOW, needs=("music",)))
+    assert [light.mode for light in previews.lights(waiting)] == ["streaming"] * 2  # dark
+    with pytest.raises(PreviewNotFoundError):
+        previews.lights(glow)  # replaced
+    assert tile.calls == [] and lamp.calls == []
```

In `tests/web/test_preview_api.py`:

```diff
--- a/tests/web/test_preview_api.py
+++ b/tests/web/test_preview_api.py
@@ -1,13 +1,15 @@
 from __future__ import annotations
 
 from collections.abc import AsyncIterator
+from dataclasses import replace
 from pathlib import Path
 from typing import Any
 
 import pytest_asyncio
 from api_home import Api, api_home
-from conftest import FakeLight
+from conftest import OPENRGB, SERVER, FakeLight
 from map_home import IN_THE_EAST_ROOM, tiny_home
+from runtime_fakes import TILE
 from zone_home import zone_record
 
 IN_THE_WEST_ROOM = {"kind": "point", "position": [1.0, 1.0, 1.0]}
@@ -72,6 +74,26 @@ async def test_a_new_preview_replaces_the_last(api: Api) -> None:
     assert stale.status_code == 404
 
 
+# F4 ruling 1: the PC answers as one light, as its most active part does.
+async def test_a_preview_says_what_each_light_would_do(tmp_path: Path) -> None:
+    keyboard = FakeLight(f"{SERVER}:0", name="Keyboard", caps=replace(OPENRGB, matrix=True))
+    ram = FakeLight(f"{SERVER}:1", name="RAM", led_count=2, caps=OPENRGB)
+    lights = [FakeLight("tile", caps=TILE), keyboard, ram, FakeLight("lamp")]
+    desk = [zone_record("desk", "tile", keyboard.stable_id, ram.stable_id, "lamp")]
+    async with api_home(tmp_path, lights, desk) as api:
+        glow = {"id": "glow", "name": "Glow", "type": "firmware", "kind": "glow_firmware"}
+        draft = {**await _draft(api, "Glow"), "layers": [glow]}
+
+        started = await api.client.post("/api/preview", json={"zoneId": "desk", "look": draft})
+
+    assert started.status_code == 201
+    assert started.json()["lights"] == [
+        {"id": "tile", "mode": "own-effect", "effect": "Glow"},
+        {"id": SERVER, "mode": "own-effect", "effect": "Glow"},  # the keyboard runs it
+        {"id": "lamp", "mode": "streamed-copy", "effect": "Glow"},
+    ]
+
+
 async def test_a_bad_preview_request_says_why(api: Api) -> None:
     both = {"zoneId": "desk", "lookId": "classic-strobe", "look": await _draft(api, "x")}
     home_look = {**await _draft(api, "x"), "scope": "whole-home"}
```

- [ ] **Step 3: Run them to see them fail**

Run: `uv run pytest tests/zones/test_preview.py -q -p no:randomly`
Expected: FAIL while collecting: `ImportError: cannot import name 'PreviewLight' from 'dj_ledfx.zones.preview'`.

Run: `uv run pytest tests/web/test_preview_api.py -q -p no:randomly`
Expected: FAIL: `1 failed, 6 passed`, with `KeyError: 'lights'`.

- [ ] **Step 4: Answer what each light would do**

In `src/dj_ledfx/zones/preview.py`:

```diff
--- a/src/dj_ledfx/zones/preview.py
+++ b/src/dj_ledfx/zones/preview.py
@@ -6,6 +6,11 @@ preview stream only, has no route, so it never sends to a light, and is never sy
 it never captures one. It follows its zone's lights as the map changes and ends with its
 zone. A browser tab that closes mid-preview sends no DELETE, so a preview nobody has
 watched for PREVIEW_IDLE_S ends by itself (Review Focus 1).
+
+The composer's consequence line (web spec §8.2) reads from a preview what each of its
+lights would do if the look started now (preview_lights): the runtime plans each light's
+firmware effect as a started look's would, since both are built from the same look and
+lights.
 """
 
 from __future__ import annotations
@@ -25,7 +30,7 @@ from dj_ledfx.timing import paced
 if TYPE_CHECKING:
     from dj_ledfx.looks.model import Look
     from dj_ledfx.zones.manager import ZoneManager
-    from dj_ledfx.zones.runtime import ZoneRuntime
+    from dj_ledfx.zones.runtime import LightMode, ZoneRuntime
 
 PREVIEW_IDLE_S = 10.0
 
@@ -34,6 +39,27 @@ class PreviewNotFoundError(KeyError):
     """No preview has that id: it ended, or a newer one replaced it."""
 
 
+@dataclass(frozen=True)
+class PreviewLight:
+    """What one of a preview's lights would do if its look started: stream the look, run a
+    firmware effect itself, or stream a copy of one (effect: that effect's name)."""
+
+    device_id: str
+    mode: LightMode
+    effect: str | None
+
+
+def preview_lights(runtime: ZoneRuntime) -> tuple[PreviewLight, ...]:
+    """The runtime's lights in its order. A look that waits for an input runs no firmware
+    effect: it waits dark (ZoneRuntime._render_look), so every light reads as streaming."""
+    return tuple(
+        PreviewLight(
+            light.device_id, runtime.mode_of(light.device_id), runtime.effect_name(light.device_id)
+        )
+        for light in runtime.lights
+    )
+
+
 @dataclass
 class _Preview:
     id: str
@@ -70,6 +96,10 @@ class PreviewManager:
         self._preview = _Preview(preview_id, runtime, self._clock())
         return preview_id
 
+    def lights(self, preview_id: str) -> tuple[PreviewLight, ...]:
+        """What each of the preview's lights would do if its look started now."""
+        return preview_lights(self._require(preview_id).runtime)
+
     def update(self, preview_id: str, look: Look) -> None:
         """The editor changed the look: take it in place where the layers allow."""
         preview = self._require(preview_id)
```

In `src/dj_ledfx/web/contract.py`:

```diff
--- a/src/dj_ledfx/web/contract.py
+++ b/src/dj_ledfx/web/contract.py
@@ -52,7 +52,7 @@ from dj_ledfx.tempo.model import (
     TempoSource,
 )
 from dj_ledfx.types import RGB, DeviceStats
-from dj_ledfx.zones import attention
+from dj_ledfx.zones import attention, preview
 from dj_ledfx.zones.attention import AttentionAction, AttentionKind, Severity, SubjectType
 from dj_ledfx.zones.lights import LightState, LightStatus
 from dj_ledfx.zones.model import (
@@ -62,7 +62,7 @@ from dj_ledfx.zones.model import (
     ZoneKind,
     ZoneRecord,
 )
-from dj_ledfx.zones.runtime import ZoneState
+from dj_ledfx.zones.runtime import LightMode, ZoneState
 
 if TYPE_CHECKING:
     from dj_ledfx.devices.govee.output import LampOutputReport
@@ -413,14 +413,47 @@ class PreviewRequest(ContractModel):
     look: Look | None = None  # an unsaved draft
 
 
+class PreviewLight(ContractModel):
+    """What one of the preview's lights would do if its look started now (web spec §8.2's
+    consequence line). Not in the web spec's contract: F4 adds it (its ruling 1)."""
+
+    id: str
+    mode: LightMode
+    effect: str | None  # the firmware effect it would run, or stream a copy of
+
+
 class PreviewStarted(ContractModel):
     preview_id: str
+    lights: list[PreviewLight]  # the zone's lights, the PC as one
 
 
 class PreviewUpdate(ContractModel):
     look: Look  # the editor's look as it is now, saved or not
 
 
+# The PC answers as its most active part: one that runs the effect itself over one that
+# streams a copy, and either over one that streams the look.
+_ACTIVITY: dict[LightMode, int] = {"own-effect": 2, "streamed-copy": 1, "streaming": 0}
+
+
+def preview_started(
+    preview_id: str, lights: Iterable[preview.PreviewLight], index: LightIndex
+) -> PreviewStarted:
+    chosen: dict[str, preview.PreviewLight] = {}
+    for light in lights:
+        light_id = index.light_of(light.device_id)
+        known = chosen.get(light_id)
+        if known is None or _ACTIVITY[light.mode] > _ACTIVITY[known.mode]:
+            chosen[light_id] = light
+    return PreviewStarted(
+        preview_id=preview_id,
+        lights=[
+            PreviewLight(id=light_id, mode=light.mode, effect=light.effect)
+            for light_id, light in chosen.items()
+        ],
+    )
+
+
 # --- the home map (web spec §12.2) ------------------------------------------------------
 
 Vec2 = tuple[float, float]
```

The route's docstring is its OpenAPI description (CLAUDE.md, Gotchas), so Step 6 picks it up:

In `src/dj_ledfx/web/router_preview.py`:

```diff
--- a/src/dj_ledfx/web/router_preview.py
+++ b/src/dj_ledfx/web/router_preview.py
@@ -10,18 +10,21 @@ from fastapi import APIRouter, Request, Response
 from dj_ledfx.web import contract as api
 from dj_ledfx.web.errors import answers
 from dj_ledfx.web.router_zones import requested_look
-from dj_ledfx.web.state import get_previews
+from dj_ledfx.web.state import get_previews, light_index
 
 router = APIRouter()
 
 
 @router.post("/preview", status_code=201)
 async def start_preview(request: Request, body: api.PreviewRequest) -> api.PreviewStarted:
-    """Replaces any previous preview. A request that fails leaves it as it was."""
+    """Replaces any previous preview. A request that fails leaves it as it was. The answer
+    says what each of the zone's lights would do if the look started now."""
     with answers():
         look = requested_look(request, body.look_id, body.look)
-        preview_id = get_previews(request).start(body.zone_id, look)
-    return api.PreviewStarted(preview_id=preview_id)
+        previews = get_previews(request)
+        preview_id = previews.start(body.zone_id, look)
+        lights = previews.lights(preview_id)
+    return api.preview_started(preview_id, lights, light_index(request.app))
 
 
 @router.put("/preview/{preview_id}", status_code=204)
```

- [ ] **Step 5: Run them to see them pass**

Run: `uv run pytest tests/zones/test_preview.py tests/web/test_preview_api.py -q -p no:randomly`
Expected: PASS (`14 passed`).

- [ ] **Step 6: Regenerate the API types, and alias the new one**

```bash
(cd web && npm run api:types && npm run api:check && git status --short src/api/generated)
```

Expected: `api types match`, and `git status` lists `openapi.json` and `schema.d.ts`. Never edit them by hand.

In `web/src/api/contract.ts`:

```diff
--- a/web/src/api/contract.ts
+++ b/web/src/api/contract.ts
@@ -73,6 +73,8 @@ export type PlacementIn = Schemas['PlacementIn']
 export type Placement = Schemas['Placement']
 export type PreviewRequest = Schemas['PreviewRequest']
 export type PreviewStarted = Schemas['PreviewStarted']
+/** What one of a preview's lights would do if its look started now: F4's consequence line reads it (F4 ruling 1). */
+export type PreviewLight = Schemas['PreviewLight']
 /** PUT /preview/{id}: the editor's look as it is now, saved or not. */
 export type PreviewUpdate = Schemas['PreviewUpdate']
 /** The binary frame's stream byte (§12.4): 0x01 live, 0x02 preview. */
```

- [ ] **Step 7: Write the mock's failing tests**

In `web/src/api/mocks/mock-server.test.ts`:

```diff
--- a/web/src/api/mocks/mock-server.test.ts
+++ b/web/src/api/mocks/mock-server.test.ts
@@ -1,14 +1,14 @@
 import { beforeEach, describe, expect, it, vi } from 'vitest'
 import { HERO_NOW, startMockServer } from '@/test/live'
 import { BeatClock } from '../beat'
-import type { Deck, Home, Inputs, Light, Look, Placement, RecentLook, Zone } from '../contract'
+import type { Deck, Home, Inputs, Light, Look, Placement, PreviewStarted, RecentLook, Zone } from '../contract'
 import { FrameStore, decodeFrame } from '../frames'
 import { LiveClient } from '../live-client'
 import { createLiveStore } from '../live-store'
 import type { ClientCommand, RunningMessage } from '../ws-messages'
 import { inMemorySockets } from './in-memory-socket'
 import { RECENT_LIMIT, beatMessage, snapshotMessages, statsMessage, type MockServer } from './mock-server'
-import { HOME_TOTALS } from './fixtures'
+import { COPIED_EFFECT, HOME_TOTALS } from './fixtures'
 import { SCENARIOS, buildScenario } from './scenarios'
 
 /** Moves the wall clock on: the mock's times come from Date.now(). */
@@ -298,7 +298,7 @@ describe('the REST API', () => {
     socket.send({ action: 'subscribe_frames', fps: 60, protocol: 2, streams: ['live', 'preview'] })
     const lights = JSON.stringify(server.state.lights)
     const reply = server.handle('POST', '/api/preview', { zoneId: 'living', lookId: 'embers' })
-    expect(reply).toEqual({ status: 201, body: { previewId: expect.any(String) } })
+    expect(reply).toEqual({ status: 201, body: { previewId: expect.any(String), lights: expect.any(Array) } })
     vi.advanceTimersByTime(500)
     const frames = decoded(socket.binary(), 2)
     expect(frames.preview.size).toBe(server.state.zones.find((zone) => zone.id === 'living')?.lights.length)
@@ -310,6 +310,43 @@ describe('the REST API', () => {
     expect(decoded(socket.binary(), 2).preview.size).toBe(0)
   })
 
+  // F4 ruling 2: the consequence line's lights. Mock looks have no layers, so a look's description names its effect.
+  it('answers what each light would do: a built-in effect the look names, else its frames', () => {
+    const server = startMockServer()
+    const living = server.state.zones.find((zone) => zone.id === 'living')!
+    const embers = server.state.looks.find((look) => look.id === 'embers')!
+    const { lights } = server.handle('POST', '/api/preview', { zoneId: 'living', lookId: 'embers' }).body as PreviewStarted
+    expect(lights.map((light) => light.id)).toEqual(living.lights)
+    const own = lights.filter((light) => light.mode === 'own-effect')
+    expect(own.length).toBeGreaterThan(0)
+    for (const { id, effect } of own) {
+      expect(embers.description).toContain(effect)
+      expect(server.state.lights.find((light) => light.id === id)?.builtInEffects).toContain(effect)
+    }
+    expect(lights.filter((light) => light.mode !== 'own-effect').every((light) => light.mode === 'streaming' && light.effect === null)).toBe(true)
+  })
+
+  it("answers the firmware look as State-Firmware runs it: each light's first effect, or a streamed copy", () => {
+    const server = startMockServer()
+    const { lights } = server.handle('POST', '/api/preview', { zoneId: 'home', lookId: 'firmware' }).body as PreviewStarted
+    for (const { id, mode, effect } of lights) {
+      const offers = server.state.lights.find((light) => light.id === id)!.builtInEffects
+      expect({ mode, effect }).toEqual(offers.length > 0 ? { mode: 'own-effect', effect: offers[0] } : { mode: 'streamed-copy', effect: COPIED_EFFECT })
+    }
+    expect(new Set(lights.map((light) => light.mode))).toEqual(new Set(['own-effect', 'streamed-copy']))
+  })
+
+  // Engine M2's ZoneError: "<zone> has no lights".
+  it('neither previews nor starts a look on a zone with no lights', () => {
+    const server = startMockServer()
+    const empty = server.state.zones.find((zone) => zone.lights.length === 0)!
+    const running = JSON.stringify(server.state.running)
+    const refused = { status: 400, body: { detail: `${empty.name} has no lights` } }
+    expect(server.handle('POST', '/api/preview', { zoneId: empty.id, lookId: 'embers' })).toEqual(refused)
+    expect(server.handle('POST', `/api/zones/${empty.id}/start`, { lookId: 'embers' })).toEqual(refused)
+    expect(JSON.stringify(server.state.running)).toBe(running)
+  })
+
   it('puts preview only on through the config, and pushes transport', () => {
     const server = startMockServer()
     const socket = connect(server)
```

Run: `(cd web && npx vitest run src/api/mocks/mock-server.test.ts)`
Expected: FAIL: `4 failed | 43 passed (47)`. The preview's answer has no `lights`, and the mock starts a look on a zone with no lights (201).

- [ ] **Step 8: The mock answers the same way**

`lightPlan()` is the mock's one rule for what a light does in a look. The `firmware` scenario now asks it too, so State-Firmware and the composer can't disagree:

In `web/src/api/mocks/fixtures.ts`:

```diff
--- a/web/src/api/mocks/fixtures.ts
+++ b/web/src/api/mocks/fixtures.ts
@@ -2,7 +2,7 @@
 // byte copies of home.json and looks.json, so no name, position or description is typed here
 // (CLAUDE.md, "Web App Design"), except the owner's name for one room (decision 8). What the files don't say, the mock makes up in the API's shape:
 // addresses from the documentation range (RFC 5737), no MACs, and M1's latency heuristics.
-import type { Home, Id, InputKind, Light, LightShape, Location, Look, Room, RunningZone, Vec3, Zone } from '../contract'
+import type { Home, Id, InputKind, Light, LightShape, Location, Look, PreviewLight, Room, RunningZone, Vec3, Zone } from '../contract'
 import homeJson from './home.json'
 import looksJson from './looks.json'
 
@@ -125,6 +125,23 @@ function builtInEffects(protocol: Protocol, capabilities: Capability[]): string[
   return ['LIFX waveform']
 }
 
+/** The effect a light that can run none of the firmware look's streams a copy of (State-Firmware: "Streamed copy of Flame"). */
+export const COPIED_EFFECT = 'LIFX Flame'
+
+/**
+ * What a light does in a look, as the mock tells it (F4 ruling 2): in a firmware look, its first
+ * built-in effect, else a streamed copy of COPIED_EFFECT; in any other look, a built-in effect of its own
+ * that the look's description names, else the look's frames. Mock looks have no layers to plan from.
+ */
+export function lightPlan(look: Pick<Look, 'category' | 'description'>, light: Pick<Light, 'builtInEffects'>): Omit<PreviewLight, 'id'> {
+  if (look.category === 'firmware') {
+    const own = light.builtInEffects[0]
+    return own === undefined ? { mode: 'streamed-copy', effect: COPIED_EFFECT } : { mode: 'own-effect', effect: own }
+  }
+  const named = light.builtInEffects.find((effect) => look.description.includes(effect))
+  return named === undefined ? { mode: 'streaming', effect: null } : { mode: 'own-effect', effect: named }
+}
+
 /** CLAUDE.md's device-type heuristics: LIFX 50 ms, Govee 100 ms, USB 5 ms. Only LIFX can be probed. */
 const LATENCY_MS: Record<Protocol, number> = { LIFX: 50, Govee: 100, OpenRGB: 5 }
 
```

In `web/src/api/mocks/mock-server.ts`:

```diff
--- a/web/src/api/mocks/mock-server.ts
+++ b/web/src/api/mocks/mock-server.ts
@@ -7,13 +7,13 @@ import {
   STREAMED,
   type AnchorIn, type ApiPath, type CreateGroup, type FrameStream, type HomeSettings, type Id, type Inputs, type InternalTempo,
   type Light, type LightShape, type LightUpdate, type Look, type PendingPath, type Placement, type PlacementIn,
-  type PreviewRequest, type PreviewUpdate, type RecentLook, type RunningZone, type StartRequest, type SubZoneIn, type TakeOver,
+  type PreviewLight, type PreviewRequest, type PreviewUpdate, type RecentLook, type RunningZone, type StartRequest, type SubZoneIn, type TakeOver,
   type TempoLock, type TempoSource, type Transition, type UpdateGroup, type Zone,
 } from '../contract'
 import { encodeFrame, type FrameVersion } from '../frames'
 import { PATH_PARAM } from '../rest'
 import type { BeatV1, BeatV2, ServerMessage, StatsMessage } from '../ws-messages'
-import { coversOf, partId, runningZone } from './fixtures'
+import { coversOf, lightPlan, partId, runningZone } from './fixtures'
 import { motifFor, paint, type MotifSpec } from './frame-generator'
 import { asEngineM1, buildScenario, type ScenarioBeat, type ScenarioName, type ScenarioState } from './scenarios'
 
@@ -860,10 +860,15 @@ export class MockServer {
     ]
     if (problems.length > 0) return { status: 422, body: { detail: problems } }
     return this.withZone(zoneId, (zone) =>
-      this.withLookFor(body, (look) => this.takeOver(zone, look, body.transition ?? look.transition)),
+      this.withLookFor(body, (look) => this.lit(zone) ?? this.takeOver(zone, look, body.transition ?? look.transition)),
     )
   }
 
+  /** Engine M2 neither starts nor previews a look on a zone with no lights (ZoneError, 400); null when it has some. */
+  private lit(zone: Zone): MockReply | null {
+    return zone.lights.length === 0 ? badRequest(`${zone.name} has no lights`) : null
+  }
+
   private takeOver(zone: Zone, look: Look, transition: Transition | undefined): MockReply {
     const taking = new Set(zone.lights)
     const takeOvers: TakeOver[] = []
@@ -1112,10 +1117,15 @@ export class MockServer {
     return ok(guessed)
   }
 
-  /** One preview at a time (§12.3): its frames go on the preview stream, and the lights are left alone. */
+  /**
+   * One preview at a time (§12.3): its frames go on the preview stream, and the lights are left alone. It
+   * answers what each light would do if the look started, as the engine does since F4 (its ruling 1).
+   */
   private startPreview(body: PreviewRequest): MockReply {
     return this.withZone(body.zoneId, (zone) =>
       this.withLookFor(body, (look) => {
+        const refused = this.lit(zone)
+        if (refused !== null) return refused
         const lights = new Map(this.state.lights.map((light) => [light.id, light]))
         const spec = motifFor(look)
         const id = this.newId('preview')
@@ -1124,7 +1134,11 @@ export class MockServer {
           lights: zone.lights.map((lightId) => this.painted(lightId, lights.get(lightId)?.leds ?? 0, spec, 1, false)),
           watchedAt: this.clock(),
         }
-        return created({ previewId: id })
+        const plans = zone.lights.map((lightId): PreviewLight => {
+          const light = lights.get(lightId)
+          return { id: lightId, ...(light === undefined ? { mode: 'streaming', effect: null } : lightPlan(look, light)) }
+        })
+        return created({ previewId: id, lights: plans })
       }),
     )
   }
```

In `web/src/api/mocks/scenarios.ts`:

```diff
--- a/web/src/api/mocks/scenarios.ts
+++ b/web/src/api/mocks/scenarios.ts
@@ -7,7 +7,7 @@ import type {
   SunPathPoint, TempoSource, Zone,
 } from '../contract'
 import {
-  HOME_ZONE, homeFixture, lightFixtures, lookFixtures, lookName, partId, roomName, runningZone, zoneFixtures,
+  HOME_ZONE, homeFixture, lightFixtures, lightPlan, lookFixtures, lookName, partId, roomName, runningZone, zoneFixtures,
 } from './fixtures'
 
 export const SCENARIOS = [
@@ -409,10 +409,11 @@ const BUILD: Record<ScenarioName, (state: ScenarioState, now: Date) => void> = {
   },
   firmware(state, now) {
     run(state, HOME_ZONE, 'firmware', after(now, -10 * MINUTE), 0.9)
+    const firmware = state.looks.find((look) => look.id === 'firmware')!
     for (const light of state.lights) {
       // State-Firmware: "Streamed copy of Flame". The engine names the effect a copy streams in ownEffect.
-      if (light.builtInEffects.length === 0) setLight(state, light.id, { status: 'streamed-copy', ownEffect: 'LIFX Flame' })
-      else setLight(state, light.id, { status: 'own-effect', ownEffect: light.builtInEffects[0] })
+      const { mode, effect } = lightPlan(firmware, light)
+      setLight(state, light.id, { status: mode, ownEffect: effect })
     }
   },
   'inputs-down'(state, now) {
```

Run: `(cd web && npx vitest run src/api/mocks/mock-server.test.ts)`
Expected: PASS (47 tests).

- [ ] **Step 9: Run the gate**

```bash
uv run pytest -q -p no:randomly 2>&1 | tail -1
uv run ruff check . && uv run ruff format --check . 2>&1 | tail -1
uv run mypy src/ 2>&1 | tail -1
(cd web && npm run api:check && npm test 2>&1 | tail -4 && npm run lint && npx tsc -b && echo "tsc ok")
```

Expected:
- pytest: `2031 passed, 1 skipped, 42 deselected`: the two new tests, and four more of FastAPI's warnings (the API test builds the app);
- ruff: `All checks passed!` and `339 files already formatted`;
- mypy: the baseline's 16 errors in 4 files, and no new one;
- `api types match`, then Vitest: 719 tests in 91 files; lint is clean, and "tsc ok".

- [ ] **Step 10: Commit**

```bash
git add src/dj_ledfx tests web/src/api
git commit -m "feat(preview): say what each of a preview's lights would do if its look started"
```

---

### Task 2: The composer's design numbers

The composer's sizes and two of its colours aren't tokens, and F0–F3 have no class for them. They come from the spec's sentences and the two renders, through the extractor, into `src/design/live-numbers.ts`. Later tasks name them by key and never state them.

**Files:**
- Modify: `web/scripts/design-extract.ts`
- Regenerate: `web/src/design/live-numbers.ts`
- Test: `web/src/stage/design-numbers.node.test.ts`

**Interfaces:**
- Consumes: `design-extract.ts`'s `Entry`, `n`, `same`, `colour` and `ReadText`, as they are.
- Produces:
  - `LIVE_SPEC.lookTile {px, namePx}` (§6.4 LookTile) and `LIVE_SPEC.phoneComposer {zonePx, thumb {width, height}}` (§8.10, Put a look on).
  - `LIVE_RENDER.lookThumb {width, height, background}`: a thumb's viewBox and its scene's colour, as both renders draw it.
  - `LIVE_RENDER.selectedZoneNote {chip, button}`: the colour of the note under the chosen zone's name, on the desktop's chip and the phone's button. tokens.css has no colour for it.

- [ ] **Step 1: Read the spec and the renders**

Read §6.4 (`LookThumb` and `LookTile`) and §8.10's Put a look on row. Then read the render markup:
- In `Live-PutLookOn.html`, a `LookTile`'s `<svg class="tb " …>` and the zone chip with `aria-pressed="true"`.
- In `Phone-PutLookOn.html`, the zone button with `aria-pressed="true"` and a look row's thumb.
- Look at `Live-PutLookOn.png` and `Phone-PutLookOn.png` once each.

- [ ] **Step 2: Write the failing test**

In `web/src/stage/design-numbers.node.test.ts`:

```diff
--- a/web/src/stage/design-numbers.node.test.ts
+++ b/web/src/stage/design-numbers.node.test.ts
@@ -44,9 +44,15 @@ describe('the design numbers', () => {
     expect(LIVE_RENDER.rowSwatchPx).toBeLessThan(LIVE_SPEC.swatch.px)
   })
 
+  // §6.4: LookThumb is "a small 16:10 scene", and the composer's tile holds one (F4 ruling 7).
+  it("draw a look's thumb at 16:10", () => {
+    expect(LIVE_RENDER.lookThumb.width / LIVE_RENDER.lookThumb.height).toBe(16 / 10)
+  })
+
   it('name the sentence that moved', () => {
     expect(() => extractSpec('')).toThrow(/§7\.1 Floors/)
     expect(() => extractLive('')).toThrow(/§4\.4/)
+    expect(() => extractLive(handoff.spec.replace('**`LookTile`** (composer', '**`LookTile`** (library'))).toThrow(/§6\.4 LookTile/)
   })
 
   it('come only from pinned files', () => {
```

- [ ] **Step 3: Run it to see it fail**

Run: `(cd web && npx vitest run src/stage/design-numbers.node.test.ts)`
Expected: FAIL: `2 failed | 7 passed (9)`. `LIVE_RENDER.lookThumb` doesn't exist, and the extractor doesn't read §6.4's LookTile.

- [ ] **Step 4: Teach the extractor the composer's numbers**

In `web/scripts/design-extract.ts`:

```diff
--- a/web/scripts/design-extract.ts
+++ b/web/scripts/design-extract.ts
@@ -189,6 +189,16 @@ const LIVE_ENTRIES: Record<string, Entry> = {
     pattern: /`AttentionPopover` \(desktop, (\d+) px, anchored under the button\)/,
     take: (m) => n(m[1]),
   },
+  lookTile: {
+    where: '§6.4 LookTile',
+    pattern: /\*\*`LookTile`\*\* \(composer, (\d+) px\): thumb, serif (\d+) name/,
+    take: (m) => ({ px: n(m[1]), namePx: n(m[2]) }),
+  },
+  phoneComposer: {
+    where: '§8.10 Put a look on',
+    pattern: /sheet: Where \((\d+) px zone buttons, horizontal scroll\), What \(category chips, look rows with (\d+) × (\d+) thumbs\)/,
+    take: (m) => ({ zonePx: n(m[1]), thumb: { width: n(m[2]), height: n(m[3]) } }),
+  },
 }
 
 /** Each entry's number, from the spec's text. Each sentence must say it once. */
@@ -249,7 +259,13 @@ const luminance = (hex: string) => [1, 3, 5].reduce((sum, at) => sum + parseInt(
 /** The renders RENDER reads. */
 const RENDERS = ['reference/Main.html', 'reference/State-Firmware.html']
 /** The renders LIVE_RENDER reads. */
-const LIVE_RENDERS = ['reference/Main.html', 'reference/State-Sheet.html', 'reference/State-Problems.html']
+const LIVE_RENDERS = [
+  'reference/Main.html',
+  'reference/State-Sheet.html',
+  'reference/State-Problems.html',
+  'reference/Live-PutLookOn.html',
+  'reference/Phone-PutLookOn.html',
+]
 
 /** Fails unless each named file of docs/design/web-app is the one HANDOFF.sha256 (`pins`) pins. */
 export function checkPins(pins: string, names: readonly string[], readBytes: (name: string) => Uint8Array): void {
@@ -436,13 +452,17 @@ export function extractRender(read: ReadText): Record<string, unknown> {
  * `@keyframes pip`, is turned from a cycle's percentages into beats: the four pips share one animation,
  * each a beat behind the last, so a cycle is as many beats as the delays' step goes into it. An overlay's
  * gold is State-Sheet.html's: tokens.css has no colour for it. A ZoneRow's small swatches are State-Problems.html's
- * size: §6.3 gives them none (F3 decision 34).
+ * size: §6.3 gives them none (F3 decision 34). The composer's (Live-PutLookOn.html, Phone-PutLookOn.html): a
+ * LookThumb's scene, its viewBox and background, the same in every render that draws one; and the note under the
+ * selected zone's name, which tokens.css has no colour for, on a chip (desktop) and a zone button (phone).
  */
 export function extractLiveRender(read: ReadText): Record<string, unknown> {
   const tokens = read('tokens.css')
   const main = read('reference/Main.html')
   const sheet = read('reference/State-Sheet.html')
   const problems = read('reference/State-Problems.html')
+  const put = read('reference/Live-PutLookOn.html')
+  const phonePut = read('reference/Phone-PutLookOn.html')
   const curve = same(main, {
     where: 'Main.html @keyframes pip',
     pattern:
@@ -467,6 +487,21 @@ export function extractLiveRender(read: ReadText): Record<string, unknown> {
     pattern:
       /font-size: 20px; white-space: nowrap">[^<]*<\/span><span style="font-size: 12px; color: #[0-9a-f]{6}; white-space: nowrap">[^<]*<\/span><\/div><div style="display: flex; align-items: center; flex-wrap: wrap; gap: \d+px"><span title="[^"]*" style="display: inline-block; width: (\d+)px; height: \1px; border-radius: 50%/,
   })
+  const thumb = same(put + phonePut, {
+    where: "Live-PutLookOn.html's and Phone-PutLookOn.html's thumbs",
+    pattern:
+      /<svg class="tb " viewBox="0 0 (\d+) (\d+)" preserveAspectRatio="xMidYMid slice" aria-hidden="true" style="display: block; background: (#[0-9a-f]{6}); ">/,
+  })
+  const chipNote = same(put, {
+    where: "Live-PutLookOn.html, the selected zone chip's note",
+    pattern:
+      /<button type="button" aria-pressed="true" style="display: inline-flex;[^"]*">[^<]*<span style="font-size: [\d.]+px; color: (#[0-9a-f]{6}); font-weight: 500; font-style: normal">/,
+  })
+  const buttonNote = same(phonePut, {
+    where: "Phone-PutLookOn.html, the selected zone button's note",
+    pattern:
+      /<button type="button" aria-pressed="true" style="display: flex; flex-direction: column;[^"]*"><span style="[^"]*">[^<]*<\/span><span style="font-size: [\d.]+px; color: (#[0-9a-f]{6}); white-space: nowrap">/,
+  })
   return {
     pip: {
       rest: colour(tokens, curve[1]),
@@ -480,6 +515,8 @@ export function extractLiveRender(read: ReadText): Record<string, unknown> {
     },
     overlay: { background: card[1], border: card[2], ink: card[3], track: card[4], fill: card[5] },
     rowSwatchPx: n(row[1]),
+    lookThumb: { width: n(thumb[1]), height: n(thumb[2]), background: colour(tokens, thumb[3]) },
+    selectedZoneNote: { chip: colour(tokens, chipNote[1]), button: colour(tokens, buttonNote[1]) },
   }
 }
 
```

- [ ] **Step 5: Generate the numbers**

```bash
(cd web && npm run design:numbers && git status --short src/design src/stage)
```

Expected: `git status` lists `src/design/live-numbers.ts` alone. It gains `LIVE_SPEC.lookTile` and `phoneComposer`, and `LIVE_RENDER.lookThumb` and `selectedZoneNote`. Never edit it by hand.

- [ ] **Step 6: Run it to see it pass**

Run: `(cd web && npx vitest run src/stage/design-numbers.node.test.ts)`
Expected: PASS (9 tests).

- [ ] **Step 7: Run the gate**

```bash
(cd web && npm test 2>&1 | tail -4 && npm run lint && npx tsc -b && echo "tsc ok")
```

Expected: 720 tests in 91 files; lint is clean, and "tsc ok".

- [ ] **Step 8: Commit**

```bash
git add web/scripts/design-extract.ts web/src/design/live-numbers.ts web/src/stage/design-numbers.node.test.ts
git commit -m "feat(web): the composer's numbers, from the spec and its two renders"
```

---

### Task 3: The preview session, and starting a look

The composer's two calls to the server. `PreviewSession` holds the one preview: one request at a time, the last choice wins, the preview stream watched only while a preview is open, a refusal said and not asked again, and the preview asked for again when the link comes back. `startLook()` starts the look with its transition and writes the answer into the live store, so Live shows it before the push comes (F4 rulings 1 and 13; Review Focus 1, 2 and 4).

**Files:**
- Create: `web/src/api/preview.ts`, `web/src/api/use-preview.ts`
- Modify: `web/src/api/actions.ts`, `web/src/api/live.ts`, `web/src/test/live.ts`
- Test: `web/src/api/preview.test.ts`, `web/src/api/use-preview.test.tsx`, `web/src/api/actions.test.ts`

**Interfaces:**
- Consumes:
  - `api.startPreview`, `api.stopPreview` and `api.start` (`rest.ts`), and `PreviewStarted.lights` (Task 1);
  - `FrameStore.clearPreview()`; `LiveClient.subscribeFrames(streams)`;
  - the live client's `onResync`.
- Produces:
  - `src/api/preview.ts`:
    - `type PreviewStatus = 'idle' | 'starting' | 'on' | 'failed'`;
    - `interface PreviewState {status, zoneId, lookId, lights, error, showing}`. `showing` is the zone whose lights the stage draws from the preview stream: its preview is on, or the next look on it is on its way;
    - `PREVIEW_IDLE`;
    - `class PreviewSession`: `subscribe`, `snapshot`, `show(zoneId, lookId)`, `stop()`, `resume()` and `reset()`.
  - `src/api/live.ts`: `previewSession`, the app's one. `resume()` runs at every resync, and `resetDataLayer()` resets it.
  - `src/api/use-preview.ts`: `usePreviewState()` and `usePreview(zoneId, lookId)`, which previews while its component is mounted.
  - `src/api/actions.ts`: `startLook(zoneId, lookId, transition)`.
  - `src/test/live.ts`: `restOn(server)` answers the app's `fetch` from a `MockServer`, as MSW does in the browser. `pushFrame(…, { stream })` pushes a preview frame.

- [ ] **Step 1: Read the spec**

Read §8.2 ("Selecting a tile starts **preview on screen** for that zone immediately", and "Data"), §12.3's preview rows, §12.4's `subscribe_frames` and frame v2, and §2's "Preview before commit". Then read `web/src/api/frames.ts` (`clearPreview()`) and the frame streams in `web/src/api/live-client.ts`.

- [ ] **Step 2: Write the failing tests**

The test helpers come first, because the tests below use them:

In `web/src/test/live.ts`:

```diff
--- a/web/src/test/live.ts
+++ b/web/src/test/live.ts
@@ -1,5 +1,5 @@
-import { onTestFinished } from 'vitest'
-import type { AttentionItem, Id } from '@/api/contract'
+import { onTestFinished, vi } from 'vitest'
+import type { AttentionItem, FrameStream, Id } from '@/api/contract'
 import { decodeFrame, encodeFrame, type FrameStore } from '@/api/frames'
 import { clientNow, normaliseBeat } from '@/api/beat'
 import { beatClock, frames, startDataLayer } from '@/api/live'
@@ -40,9 +40,26 @@ export function startMockDataLayer(options: MockServerOptions = {}): MockServer
   return server
 }
 
-/** A light's live frame, `rgb` three bytes an LED, decoded as the socket would: into the app's frame store unless given another. */
-export function pushFrame(id: Id, seq: number, rgb: ArrayLike<number>, { store = frames, at = 0 }: { store?: FrameStore; at?: number } = {}): void {
-  decodeFrame(encodeFrame(2, id, seq, Uint8Array.from(rgb)), 2, store, at)
+/** REST on a mock server: the app's fetch answered by `server`, as MSW's handlers answer it in the browser. */
+export function restOn(server: MockServer): void {
+  vi.stubGlobal('fetch', async (input: URL | string, init: RequestInit = {}) => {
+    const body = typeof init.body === 'string' ? (JSON.parse(init.body) as unknown) : undefined
+    const reply = server.handle(init.method ?? 'GET', new URL(input).pathname, body)
+    return reply.body === undefined ? new Response(null, { status: reply.status }) : Response.json(reply.body, { status: reply.status })
+  })
+}
+
+/**
+ * A light's frame, `rgb` three bytes an LED, decoded as the socket would: live, into the app's frame
+ * store, unless told otherwise.
+ */
+export function pushFrame(
+  id: Id,
+  seq: number,
+  rgb: ArrayLike<number>,
+  { store = frames, at = 0, stream = 'live' }: { store?: FrameStore; at?: number; stream?: FrameStream } = {},
+): void {
+  decodeFrame(encodeFrame(2, id, seq, Uint8Array.from(rgb), stream), 2, store, at)
 }
 
 const KIND = { light: 'light-offline', zone: 'zone-crashed', input: 'input-disconnected' } as const
```

Create `web/src/api/preview.test.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fakeSockets } from '@/test/fake-socket'
import { HERO_NOW, pushFrame, restOn, startMockDataLayer } from '@/test/live'
import { startLook } from './actions'
import type { PreviewStarted } from './contract'
import { FrameStore } from './frames'
import { frames, previewSession, startDataLayer } from './live'
import type { LiveClient } from './live-client'
import { PreviewSession } from './preview'
import { api, ApiError } from './rest'

const CUT = { kind: 'cut', durationS: 0 } as const

/** A request held open until the test answers it. */
function held<T>() {
  let resolve: (value: T) => void = () => {}
  let reject: (error: unknown) => void = () => {}
  const promise = new Promise<T>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

const started = (previewId: string): PreviewStarted => ({ previewId, lights: [] })

/** A session over its own frame store and a client that records what it subscribes to. */
function session() {
  const store = new FrameStore()
  const subscribeFrames = vi.fn()
  const preview = new PreviewSession({ frames: store, client: () => ({ subscribeFrames }) as unknown as LiveClient })
  return { preview, store, subscribeFrames }
}

describe('the preview', () => {
  beforeEach(() => {
    vi.spyOn(api, 'stopPreview').mockResolvedValue(undefined)
  })

  // §13.1 F4's exit check: "lights unchanged until Start (mock asserts)".
  it('draws the look on the preview stream and leaves the lights alone until Start', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(HERO_NOW)
    vi.mocked(api.stopPreview).mockRestore()
    const server = startMockDataLayer()
    restOn(server)
    await vi.advanceTimersByTimeAsync(1100)
    const running = structuredClone(server.state.running)
    const lights = structuredClone(server.state.lights)
    const living = server.state.zones.find((zone) => zone.id === 'living')!

    previewSession.show('living', 'embers')
    await vi.advanceTimersByTimeAsync(500)
    expect(previewSession.snapshot()).toMatchObject({ status: 'on', zoneId: 'living', lookId: 'embers', showing: 'living' })
    expect(previewSession.snapshot().lights!.map((light) => light.id)).toEqual(living.lights)
    for (const id of living.lights) expect(frames.get(id, 'preview')).toBeDefined()
    expect(server.state.running).toEqual(running)
    expect(server.state.lights).toEqual(lights)

    await startLook('living', 'embers', CUT)
    expect(server.state.running.find((zone) => zone.zoneId === 'living')?.lookId).toBe('embers')
  })

  it('asks for one preview at a time, and the last choice wins', async () => {
    const { preview } = session()
    const first = held<PreviewStarted>()
    const ask = vi.spyOn(api, 'startPreview').mockReturnValueOnce(first.promise).mockResolvedValueOnce(started('p2'))
    preview.show('living', 'embers')
    preview.show('living', 'aurora')
    preview.show('kitchen', 'lava')
    expect(ask).toHaveBeenCalledTimes(1)
    expect(preview.snapshot()).toMatchObject({ status: 'starting', zoneId: 'kitchen', lookId: 'lava' })

    first.resolve(started('p1'))
    await vi.waitFor(() => expect(preview.snapshot().status).toBe('on'))
    expect(ask).toHaveBeenCalledTimes(2)
    expect(ask).toHaveBeenLastCalledWith({ zoneId: 'kitchen', lookId: 'lava' })
    expect(preview.snapshot()).toMatchObject({ zoneId: 'kitchen', lookId: 'lava', showing: 'kitchen' })
  })

  it('watches the preview stream only while a preview is open', async () => {
    const { preview, subscribeFrames } = session()
    vi.spyOn(api, 'startPreview').mockResolvedValue(started('p1'))
    preview.show('living', 'embers')
    expect(subscribeFrames).toHaveBeenLastCalledWith(['live', 'preview'])
    await vi.waitFor(() => expect(preview.snapshot().status).toBe('on'))
    preview.show('living', 'aurora')
    await vi.waitFor(() => expect(preview.snapshot()).toMatchObject({ status: 'on', lookId: 'aurora' }))
    expect(subscribeFrames).toHaveBeenCalledTimes(1)
    preview.stop()
    expect(subscribeFrames).toHaveBeenLastCalledWith(['live'])
    expect(api.stopPreview).toHaveBeenCalledWith('p1')
  })

  it("ends the server's preview when stopped, even one still on its way", async () => {
    const { preview } = session()
    const first = held<PreviewStarted>()
    vi.spyOn(api, 'startPreview').mockReturnValueOnce(first.promise)
    preview.show('living', 'embers')
    preview.stop()
    expect(preview.snapshot().status).toBe('idle')
    first.resolve(started('p1'))
    await vi.waitFor(() => expect(api.stopPreview).toHaveBeenCalledWith('p1'))
    expect(preview.snapshot().status).toBe('idle')
  })

  it('previews the same look again after a stop', async () => {
    const { preview } = session()
    const ask = vi.spyOn(api, 'startPreview').mockResolvedValue(started('p1'))
    preview.show('living', 'embers')
    await vi.waitFor(() => expect(preview.snapshot().status).toBe('on'))
    preview.stop()
    preview.show('living', 'embers')
    await vi.waitFor(() => expect(preview.snapshot().status).toBe('on'))
    expect(ask).toHaveBeenCalledTimes(2)
  })

  // F4 ruling 3: the engine refuses a whole-home look until M6.
  it("says why the server refused, ends the preview before, and doesn't ask again", async () => {
    const { preview, store } = session()
    const refused = new ApiError(400, 'Home looks (whole-home scope) arrive in M6', '/api/preview')
    const ask = vi.spyOn(api, 'startPreview').mockResolvedValueOnce(started('p1')).mockRejectedValueOnce(refused)
    preview.show('home', 'embers')
    await vi.waitFor(() => expect(preview.snapshot().status).toBe('on'))
    pushFrame('a-light', 1, [1, 2, 3], { store, stream: 'preview' })

    preview.show('home', 'wisp')
    await vi.waitFor(() => expect(preview.snapshot().status).toBe('failed'))
    expect(preview.snapshot()).toMatchObject({ zoneId: 'home', lookId: 'wisp', error: refused, showing: null, lights: null })
    expect(api.stopPreview).toHaveBeenCalledWith('p1')
    expect(store.preview.size).toBe(0)

    preview.show('home', 'wisp')
    expect(ask).toHaveBeenCalledTimes(2)
  })

  it("keeps drawing a zone's preview while the next look on it starts, and drops it for another zone", async () => {
    const { preview, store } = session()
    const second = held<PreviewStarted>()
    vi.spyOn(api, 'startPreview').mockResolvedValueOnce(started('p1')).mockReturnValueOnce(second.promise)
    preview.show('living', 'embers')
    await vi.waitFor(() => expect(preview.snapshot().status).toBe('on'))
    pushFrame('a-light', 1, [1, 2, 3], { store, stream: 'preview' })

    preview.show('living', 'aurora')
    expect(preview.snapshot()).toMatchObject({ status: 'starting', showing: 'living' })
    expect(store.preview.size).toBe(1)

    preview.show('kitchen', 'aurora')
    expect(preview.snapshot()).toMatchObject({ status: 'starting', showing: null })
    expect(store.preview.size).toBe(0)
    second.resolve(started('p2'))
  })

  // Review focus 4: the engine ends a preview nobody watched for 10 s, and a restarted server holds none.
  it('asks for the preview again when the link comes back', async () => {
    vi.useFakeTimers()
    const { sockets, open } = fakeSockets()
    const latest = () => sockets[sockets.length - 1]
    const welcome = () => {
      latest().open()
      latest().say({ channel: 'transport', state: 'playing' })
      latest().say({ channel: 'ack', id: latest().idOf('subscribe_frames'), action: 'subscribe_frames', protocol: 2, fps: 60 })
    }
    startDataLayer({ openSocket: open, url: 'ws://test/ws' })
    welcome()
    const ask = vi.spyOn(api, 'startPreview').mockResolvedValueOnce(started('p1')).mockResolvedValueOnce(started('p2'))
    previewSession.show('living', 'embers')
    await vi.waitFor(() => expect(previewSession.snapshot().status).toBe('on'))

    latest().drop()
    await vi.advanceTimersByTimeAsync(1000)
    welcome()
    await vi.waitFor(() => expect(ask).toHaveBeenCalledTimes(2))
    expect(ask).toHaveBeenLastCalledWith({ zoneId: 'living', lookId: 'embers' })
    expect(previewSession.snapshot()).toMatchObject({ status: 'on', zoneId: 'living', showing: 'living' })
    // The new socket watches the preview stream too.
    expect(latest().sent.findLast((command) => command.action === 'subscribe_frames')).toMatchObject({ streams: ['live', 'preview'] })

    // With no preview wanted, a reconnect asks for none.
    previewSession.stop()
    latest().drop()
    await vi.advanceTimersByTimeAsync(1000)
    welcome()
    await Promise.resolve()
    expect(ask).toHaveBeenCalledTimes(2)
  })

  it('drops an answer to a request made before a reset', async () => {
    const { preview } = session()
    const first = held<PreviewStarted>()
    vi.spyOn(api, 'startPreview').mockReturnValueOnce(first.promise)
    preview.show('living', 'embers')
    preview.reset()
    first.resolve(started('p1'))
    await Promise.resolve()
    await Promise.resolve()
    expect(preview.snapshot().status).toBe('idle')
  })
})
```

Create `web/src/api/use-preview.test.tsx`:

```tsx
import { renderHook } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { previewSession } from './live'
import { usePreview } from './use-preview'

describe('usePreview', () => {
  it('previews while its component is mounted, and ends the preview after', () => {
    const show = vi.spyOn(previewSession, 'show').mockImplementation(() => {})
    const stop = vi.spyOn(previewSession, 'stop').mockImplementation(() => {})
    const props: { zone: string | null; look: string | null } = { zone: 'living', look: 'embers' }
    const { rerender, unmount } = renderHook(({ zone, look }) => usePreview(zone, look), { initialProps: props })
    expect(show).toHaveBeenLastCalledWith('living', 'embers')
    rerender({ zone: 'living', look: null })
    expect(stop).toHaveBeenCalledTimes(1)
    unmount()
    expect(stop).toHaveBeenCalledTimes(2)
  })
})
```

In `web/src/api/actions.test.ts`:

```diff
--- a/web/src/api/actions.test.ts
+++ b/web/src/api/actions.test.ts
@@ -1,6 +1,6 @@
 import { describe, expect, it, vi } from 'vitest'
 import { seedLive } from '@/test/live'
-import { failureText, setBrightness, setTempoLock, startAgain, tapTempo } from './actions'
+import { failureText, setBrightness, setTempoLock, startAgain, startLook, tapTempo } from './actions'
 import { liveStore } from './live-store'
 import { queries, queryClient } from './queries'
 import { api, ApiError } from './rest'
@@ -35,6 +35,37 @@ describe('actions', () => {
     expect(api.tap).toHaveBeenCalledWith(Date.now() / 1000)
   })
 
+  // F4 ruling 13: Live shows the started look before the push comes.
+  it('puts a started look in the store as the newest, without the lights it took', async () => {
+    seedLive()
+    const home = zone('home')
+    const taken = home.lights.slice(0, 2)
+    vi.spyOn(api, 'start').mockResolvedValue({
+      ...zone('living'),
+      lookId: 'embers',
+      takeOvers: [{ zoneId: 'home', zoneName: 'home', lookName: home.lookName, lights: taken, stopped: false }],
+    })
+    await startLook('living', 'embers', { kind: 'dissolve', durationS: 3 })
+    expect(api.start).toHaveBeenCalledWith('living', { lookId: 'embers', transition: { kind: 'dissolve', durationS: 3 } })
+    const zones = liveStore.getState().running!.zones
+    expect(zones.map((candidate) => candidate.zoneId)).toEqual(['home', 'office', 'living'])
+    expect(zone('living').lookId).toBe('embers')
+    expect(zone('home').lights).toEqual(home.lights.filter((id) => !taken.includes(id)))
+  })
+
+  it('stops a zone in the store when a start takes all its lights', async () => {
+    seedLive()
+    const office = zone('office')
+    vi.spyOn(api, 'start').mockResolvedValue({
+      ...office,
+      zoneId: 'bedroom',
+      lookId: 'embers',
+      takeOvers: [{ zoneId: 'office', zoneName: 'office', lookName: office.lookName, lights: office.lights, stopped: true }],
+    })
+    await startLook('bedroom', 'embers', { kind: 'cut', durationS: 0 })
+    expect(liveStore.getState().running!.zones.map((candidate) => candidate.zoneId)).toEqual(['home', 'living', 'bedroom'])
+  })
+
   it('reads "Start again" afresh after starting a look from it', async () => {
     vi.spyOn(api, 'start').mockResolvedValue({ zoneId: 'living', lookId: 'fireflies' } as never)
     const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
```

- [ ] **Step 3: Run them to see them fail**

Run: `(cd web && npx vitest run src/api/preview.test.ts src/api/use-preview.test.tsx src/api/actions.test.ts)`
Expected: FAIL. `./preview` and `./use-preview` don't resolve, and `actions.test.ts` reports `2 failed | 5 passed (7)`: `startLook is not a function`.

- [ ] **Step 4: Start a look, with its transition**

`storeStarted()` writes what the server answered: the zone as the newest, and the lights it took gone from the zones it took them from.

In `web/src/api/actions.ts`:

```diff
--- a/web/src/api/actions.ts
+++ b/web/src/api/actions.ts
@@ -2,7 +2,7 @@
 // with the new state, the action puts it in the live store at once, so a control shows it without
 // waiting for the push (F3 decision 8). A failure rejects; components say it with failureText()
 // through useAnnounce() (Review Focus 1). Components call these, never `api` or the socket (§12).
-import type { Id, RecentLook, RunningZone, TempoInput, TempoLock } from './contract'
+import type { Id, RecentLook, RunningZone, StartResponse, TempoInput, TempoLock, Transition } from './contract'
 import { liveClient } from './live'
 import { liveStore } from './live-store'
 import { queries, queryClient } from './queries'
@@ -15,6 +15,22 @@ function storeZone(zone: RunningZone): void {
   )
 }
 
+/**
+ * A start's answer in the store (F4 ruling 13): the zone, replaced or added as the newest, and the
+ * lights it took gone from the zones it took them from; a zone left with none stops, as on the server.
+ */
+function storeStarted({ takeOvers, ...zone }: StartResponse): void {
+  const taken = new Set((takeOvers ?? []).flatMap((takeOver) => takeOver.lights))
+  liveStore.setState(({ running }) => {
+    if (running === null) return {}
+    const others = running.zones
+      .filter((other) => other.zoneId !== zone.zoneId)
+      .map((other) => (other.lights.some((id) => taken.has(id)) ? { ...other, lights: other.lights.filter((id) => !taken.has(id)) } : other))
+      .filter((other) => other.lights.length > 0)
+    return { running: { ...running, zones: [...others, zone] } }
+  })
+}
+
 /** The tempo the server answered with, in the inputs the store holds. */
 function storeTempo(tempo: TempoInput): void {
   liveStore.setState(({ inputs }) => (inputs === null ? {} : { inputs: { ...inputs, tempo } }))
@@ -40,6 +56,11 @@ export async function stopAll(): Promise<void> {
   await api.stopAll()
 }
 
+/** §8.2 Start: the look on the zone, with the transition chosen. Live shows it before the push comes. */
+export async function startLook(zoneId: Id, lookId: Id, transition: Transition): Promise<void> {
+  storeStarted(await api.start(zoneId, { lookId, transition }))
+}
+
 /** §9.4 "Start again": one tap plays a recent look on its zone, and the list is read afresh. */
 export async function startAgain(recent: Pick<RecentLook, 'zoneId' | 'lookId'>): Promise<void> {
   await api.start(recent.zoneId, { lookId: recent.lookId })
```

- [ ] **Step 5: Write the preview session**

Create `web/src/api/preview.ts`:

```ts
// The composer's preview (spec §8.2, §12.3): the look on the stage only, while the lights stay as they
// are. The server holds one preview at a time and a new one replaces it, so the session asks for one
// at a time: a choice made while a request is on its way is asked for when that one is answered, and
// the server's last preview is always the last one chosen. The preview stream is watched while one is
// open (engine M2 ends a preview nobody watches, its Spec Ruling 9), and asked for again when the link
// comes back. Components read it through usePreview() (use-preview.ts).
import type { Id, PreviewLight } from './contract'
import type { FrameStore } from './frames'
import type { LiveClient } from './live-client'
import { api } from './rest'

export type PreviewStatus = 'idle' | 'starting' | 'on' | 'failed'

export interface PreviewState {
  readonly status: PreviewStatus
  /** The zone and the look chosen: null while idle. */
  readonly zoneId: Id | null
  readonly lookId: Id | null
  /** What each of the zone's lights would do if the look started (F4 ruling 1): the server's answer, while on. */
  readonly lights: readonly PreviewLight[] | null
  /** Why the server refused it, while failed. */
  readonly error: unknown
  /**
   * The zone whose lights the stage draws from the preview stream: its preview is on, or the next look
   * on it is on its way (the last one's frames flow until the server replaces it). Null otherwise.
   */
  readonly showing: Id | null
}

export const PREVIEW_IDLE: PreviewState = { status: 'idle', zoneId: null, lookId: null, lights: null, error: null, showing: null }

interface Choice {
  zoneId: Id
  lookId: Id
}

const same = (a: Choice | null, b: Choice | null) => a !== null && b !== null && a.zoneId === b.zoneId && a.lookId === b.lookId

export class PreviewSession {
  private state: PreviewState = PREVIEW_IDLE
  private readonly listeners = new Set<() => void>()
  private readonly frames: FrameStore
  private readonly client: () => LiveClient | null
  /** What the composer wants previewed now; null for nothing. */
  private wanted: Choice | null = null
  /** The last choice sent, answered or on its way; null after a stop. */
  private asked: Choice | null = null
  private asking = false
  /** The preview the server holds for this page. */
  private previewId: Id | null = null
  private watching = false
  /** Moves on at reset(): an answer to a request from before it is dropped. */
  private generation = 0

  constructor(options: { frames: FrameStore; client: () => LiveClient | null }) {
    this.frames = options.frames
    this.client = options.client
  }

  /** For useSyncExternalStore. */
  readonly subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener)
    return () => void this.listeners.delete(listener)
  }

  readonly snapshot = (): PreviewState => this.state

  /** Previews `lookId` on `zoneId`, replacing whatever this session previewed before. */
  show(zoneId: Id, lookId: Id): void {
    const choice = { zoneId, lookId }
    if (same(this.wanted, choice)) return
    this.wanted = choice
    if (this.state.showing !== null && this.state.showing !== zoneId) this.frames.clearPreview()
    this.watch(true)
    this.set({ ...PREVIEW_IDLE, status: 'starting', zoneId, lookId, showing: this.state.showing === zoneId ? zoneId : null })
    if (!this.asking) void this.ask()
  }

  /** No preview: the server's ends (one still on its way ends when it's answered), and the stage draws the live stream. */
  stop(): void {
    if (this.wanted === null && this.state.status === 'idle') return
    this.wanted = null
    if (!this.asking) this.drop()
    this.set(PREVIEW_IDLE)
  }

  /**
   * After a reconnect (the live client's resync): the server may have ended the preview while nobody
   * watched it, or restarted, so the one wanted is asked for again. The answer replaces whatever the
   * server still holds, as every new preview does.
   */
  resume(): void {
    if (this.wanted === null) return
    this.asked = null
    if (!this.asking) void this.ask()
  }

  /** Back to a page just opened, with no request: for resetDataLayer(). */
  reset(): void {
    this.generation += 1
    this.wanted = null
    this.asked = null
    this.asking = false
    this.previewId = null
    this.watching = false
    this.set(PREVIEW_IDLE)
  }

  private async ask(): Promise<void> {
    const generation = this.generation
    this.asking = true
    while (this.wanted !== null && !same(this.wanted, this.asked)) {
      const choice = this.wanted
      this.asked = choice
      try {
        const started = await api.startPreview(choice)
        if (generation !== this.generation) return
        this.previewId = started.previewId
        if (same(this.wanted, choice)) this.set({ ...PREVIEW_IDLE, status: 'on', ...choice, lights: started.lights, showing: choice.zoneId })
      } catch (error) {
        if (generation !== this.generation) return
        // The server may still hold the last preview: it ends too, so the stage never shows a look not chosen.
        if (same(this.wanted, choice)) {
          this.drop()
          this.asked = choice // asked once: a refusal isn't asked again until another choice comes between
          this.set({ ...PREVIEW_IDLE, status: 'failed', ...choice, error })
        }
      }
    }
    this.asking = false
    if (this.wanted === null) this.drop()
  }

  /** Ends the server's preview, if it holds one, and stops watching the preview stream. */
  private drop(): void {
    const id = this.previewId
    this.previewId = null
    this.asked = null
    // A preview already gone (it ended unwatched, or the server restarted) has nothing left to end.
    if (id !== null) void api.stopPreview(id).catch(() => undefined)
    this.frames.clearPreview()
    this.watch(false)
  }

  private watch(on: boolean): void {
    if (this.watching === on) return
    this.watching = on
    this.client()?.subscribeFrames(on ? ['live', 'preview'] : ['live'])
  }

  private set(state: PreviewState): void {
    this.state = state
    for (const listener of this.listeners) listener()
  }
}
```

- [ ] **Step 6: One session for the app, and its hook**

In `web/src/api/live.ts`:

```diff
--- a/web/src/api/live.ts
+++ b/web/src/api/live.ts
@@ -1,16 +1,20 @@
 // The app's one data layer: a frame store, a beat clock, and the live client that fills them and
-// the live store. main.tsx starts it once; F3's "Try now" and TAP (actions.ts) and F6/F8's signal
-// subscriptions reach the client through liveClient().
+// the live store. main.tsx starts it once; F3's "Try now" and TAP (actions.ts), F4's preview and F6/F8's
+// signal subscriptions reach the client through liveClient().
 import { BeatClock } from './beat'
 import { FrameStore } from './frames'
 import { LiveClient, liveSocketUrl, type OpenSocket } from './live-client'
 import { liveStore, resetLiveStore } from './live-store'
+import { PreviewSession } from './preview'
 import { queryClient, refetchOnNews, resync } from './queries'
 
 export const frames = new FrameStore()
 export const beatClock = new BeatClock()
 
 let client: LiveClient | null = null
+
+/** The composer's preview (F4): one at a time, on the stage only. */
+export const previewSession = new PreviewSession({ frames, client: () => client })
 let stopRefetching: (() => void) | null = null
 
 /**
@@ -27,7 +31,10 @@ export function startDataLayer(options: { openSocket?: OpenSocket; url?: string
     frames,
     beatClock,
     openSocket: options.openSocket,
-    onResync: () => void resync(queryClient),
+    onResync: () => {
+      void resync(queryClient)
+      previewSession.resume()
+    },
   })
   client.start()
   return client
@@ -37,10 +44,11 @@ export function liveClient(): LiveClient | null {
   return client
 }
 
-/** Back to a page just opened: no client, and the live store, frames, beat clock and REST cache empty. */
+/** Back to a page just opened: no client or preview, and the live store, frames, beat clock and REST cache empty. */
 export function resetDataLayer(): void {
   client?.stop()
   client = null
+  previewSession.reset()
   stopRefetching?.()
   stopRefetching = null
   resetLiveStore()
```

Create `web/src/api/use-preview.ts`:

```ts
// The composer's preview as React sees it: usePreview() asks for one while its component is mounted,
// and usePreviewState() reads it (the stage draws the chosen zone from the preview stream).
import { useEffect, useSyncExternalStore } from 'react'
import type { Id } from './contract'
import { previewSession } from './live'
import type { PreviewState } from './preview'

/** The preview's state, which every component reading it shares. */
export function usePreviewState(): PreviewState {
  return useSyncExternalStore(previewSession.subscribe, previewSession.snapshot)
}

/**
 * Previews `lookId` on `zoneId` while both are given, and nothing otherwise; the preview ends when the
 * component unmounts (Cancel, Close, Start, or leaving the page).
 */
export function usePreview(zoneId: Id | null, lookId: Id | null): PreviewState {
  useEffect(() => {
    if (zoneId === null || lookId === null) previewSession.stop()
    else previewSession.show(zoneId, lookId)
  }, [zoneId, lookId])
  useEffect(() => () => previewSession.stop(), [])
  return usePreviewState()
}
```

- [ ] **Step 7: Run them to see them pass**

Run: `(cd web && npx vitest run src/api/preview.test.ts src/api/use-preview.test.tsx src/api/actions.test.ts)`
Expected: PASS (17 tests).

- [ ] **Step 8: Run the gate**

```bash
(cd web && npm test 2>&1 | tail -4 && npm run lint && npx tsc -b && echo "tsc ok")
```

Expected: 732 tests in 93 files; lint is clean, and "tsc ok".

- [ ] **Step 9: Commit**

```bash
git add web/src/api web/src/test/live.ts
git commit -m "feat(web): the composer's preview session, and starting a look with its transition"
```

---

### Task 4: The composer's model and the consequence line

Everything the composer decides goes in pure functions, tested from the mock's scenarios: the zone it puts the look on, what runs on each zone, the inputs a look would wait for, the looks a category or a search shows, the transitions on offer, and the consequence line's words (F4 rulings 3, 4, 8 to 11, and 14). §14 asks for "take-over consequence text" unit tests, and `consequence.test.ts` holds them.

**Files:**
- Create: `web/src/compose/model.ts`, `web/src/compose/consequence.ts`, `web/src/compose/last-zone.ts`, `web/src/lib/storage.ts`
- Modify: `web/src/stage/view-memory.ts` (`browserStorage()` moves out), `web/src/zones/zone-view.ts` (`waitingText()` and `transitionLabel()` exported)
- Test: `web/src/compose/model.test.ts`, `web/src/compose/consequence.test.ts`, `web/src/compose/last-zone.test.ts`

**Interfaces:**
- Consumes:
  - `newestFirst()` (`stage/show.ts`), `chipsFor()` and `INPUTS` (`zones/zone-view.ts`), `effectWord()` (`lights/firmware.ts`), `formatList()` (`lib/format.ts`);
  - `PreviewLight` (Task 1).
- Produces:
  - `src/lib/storage.ts`: `browserStorage(): Storage | null`, moved from `stage/view-memory.ts`.
  - `src/zones/zone-view.ts`: `waitingText(kind)` and `transitionLabel(kind, durationS)`, which the card's note and transition already said and the composer now shares.
  - `src/compose/last-zone.ts`: `lastZone(storage?)` and `rememberZone(id, storage?)`.
  - `src/compose/model.ts`:
    - `type Category` and `CATEGORIES` (§8.2's chips);
    - `locksToHome(look)`, `chosenZone(zones, asked, remembered, look)`, `runningOn(zone, running, zones)` and `zoneNote(zone, here)`;
    - `type MissingInput`, `MISSING_SIGNAL` and `missingInputs(look, inputs)`;
    - `looksShown(looks, category, query)` and `openingCategory(look, here)`;
    - `TRANSITION_SECONDS`, `interface TransitionChoice {key, label, transition}`, `lookTransition(look)`, `transitionChoices(look)` and `transitionKey(transition)`.
  - `src/compose/consequence.ts`:
    - `interface ConsequencePart {text, look?}`, `interface Consequence {parts, short, blocked}` and `interface ConsequenceSources`;
    - `zonePhrase(zone)`, `lightsPhrase(ids, lights)` and `consequence(sources)`.

- [ ] **Step 1: Read the spec and the renders**

Read §6.3 (`ZonePicker`), §8.2, §9.3 (how an input reads when it's missing or stale), §10, §11.3 and §14's unit tests. Look once at `Live-PutLookOn.png`'s zone chips and consequence line, and at `Phone-PutLookOn.png`'s zone buttons and the line above Start.

- [ ] **Step 2: Write the failing tests**

Create `web/src/compose/model.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import type { Look } from '@/api/contract'
import { lookName } from '@/api/mocks/fixtures'
import { buildScenario, type ScenarioName } from '@/api/mocks/scenarios'
import { HERO_NOW } from '@/test/live'
import {
  CATEGORIES,
  chosenZone,
  looksShown,
  lookTransition,
  missingInputs,
  openingCategory,
  runningOn,
  transitionChoices,
  transitionKey,
  zoneNote,
} from './model'

const hero = buildScenario('hero', HERO_NOW)
const zone = (id: string) => hero.zones.find((candidate) => candidate.id === id)!
const look = (id: string) => hero.looks.find((candidate) => candidate.id === id)!

describe('the zone the composer puts a look on', () => {
  it("is the URL's, else the last one used, else the whole home", () => {
    expect(chosenZone(hero.zones, 'kitchen', 'living', look('embers'))?.id).toBe('kitchen')
    expect(chosenZone(hero.zones, null, 'living', look('embers'))?.id).toBe('living')
    expect(chosenZone(hero.zones, null, null, undefined)?.kind).toBe('home')
  })

  it('passes over a zone that has gone', () => {
    expect(chosenZone(hero.zones, 'group-9', 'group-8', undefined)?.kind).toBe('home')
  })

  // §8.2: "Home looks (whole-home scope) lock the zone to Whole home."
  it('is the whole home for a home look, whatever was asked', () => {
    expect(chosenZone(hero.zones, 'living', 'kitchen', look('homesunset'))?.kind).toBe('home')
  })
})

describe('what runs on a zone', () => {
  const note = (id: string) => zoneNote(zone(id), runningOn(zone(id), hero.running, hero.zones))

  it('is its own look, else the newest on its lights', () => {
    expect(note('living')).toBe(lookName('fireflies'))
    expect(note('office')).toBe(lookName('comets'))
    expect(note('kitchen')).toBe(lookName('homesunset'))
  })

  // Sub-zone 'office' is in room 'bedroom' and runs the newest look; the room's other lights run the home's.
  it("never says a room runs a sub-zone's look", () => {
    expect(note('bedroom')).toBe(lookName('homesunset'))
  })

  it('is idle where nothing runs, and says when a zone has no lights', () => {
    const quiet = buildScenario('nothing-running', HERO_NOW)
    const kitchen = quiet.zones.find((candidate) => candidate.id === 'kitchen')!
    expect(zoneNote(kitchen, runningOn(kitchen, quiet.running, quiet.zones))).toBe('idle')
    expect(note('counter')).toBe('no lights')
  })
})

describe('the inputs a look would wait for', () => {
  const missing = (scenario: ScenarioName, id: string) => {
    const state = buildScenario(scenario, HERO_NOW)
    return missingInputs(look(id), state.inputs)
  }

  it('are none while the music plays and Home Assistant answers', () => {
    expect(missing('hero', 'spectrum')).toEqual([])
    expect(missing('hero', 'goodnight')).toEqual([])
  })

  it('are the music while nothing plays, and Home Assistant while it has no link', () => {
    expect(missing('dj-playing', 'spectrum')).toEqual(['music'])
    expect(missing('inputs-down', 'goodnight')).toEqual(['home-assistant'])
  })

  // §9.3: a stale input's looks hold its last value.
  it("aren't the music while it's only stale", () => {
    expect(missing('inputs-down', 'spectrum')).toEqual([])
  })

  it('are never the tempo, and none an input the server doesn\'t serve yet', () => {
    expect(missing('inputs-down', 'bursts')).toEqual([])
    expect(missingInputs(look('spectrum'), { ...hero.inputs, music: undefined })).toEqual([])
    expect(missingInputs(look('spectrum'), null)).toEqual([])
  })
})

describe('the looks the composer shows', () => {
  const ids = (looks: Look[]) => looks.map((each) => each.id)

  it("are a category's, in the server's order", () => {
    expect(ids(looksShown(hero.looks, 'tempo', ''))).toEqual(ids(hero.looks.filter((each) => each.category === 'tempo')))
    const starred = hero.looks.map((each) => ({ ...each, starred: each.id === 'lava' || each.id === 'comets' }))
    expect(ids(looksShown(starred, 'starred', ''))).toEqual(['lava', 'comets'])
  })

  it("are a search's over every category, whatever the case", () => {
    expect(ids(looksShown(hero.looks, 'tempo', ` ${lookName('homesunset').toUpperCase()} `))).toEqual(['homesunset'])
    expect(looksShown(hero.looks, 'ambient', 'zzzz')).toEqual([])
  })

  it("open on the chosen look's category, else the running look's, else Ambient", () => {
    expect(openingCategory(look('comets'), look('fireflies'))).toBe('tempo')
    expect(openingCategory(undefined, look('homesunset'))).toBe('home')
    expect(openingCategory(undefined, undefined)).toBe('ambient')
  })

  it('come in §8.2\'s categories', () => {
    expect(CATEGORIES.map((category) => category.label)).toEqual(['Starred', 'Ambient', 'Tempo', 'Audio', 'Home', 'Firmware'])
  })
})

describe('the transitions', () => {
  it('are a cut and each kind at 1, 3 and 5 s, said as the cards say them', () => {
    const choices = transitionChoices(look('embers'))
    expect(choices).toHaveLength(13)
    expect(choices[0]).toMatchObject({ key: 'cut:0', label: 'Cut' })
    expect(choices.find((choice) => choice.key === 'dissolve:3')?.label).toBe('Dissolve · 3 s')
  })

  // §8.2: "default the look's own".
  it("default to the look's own, offered after its kind's others where it's another length", () => {
    const own = { ...look('embers'), transition: { kind: 'wipe' as const, durationS: 2.5 } }
    expect(transitionKey(lookTransition(own))).toBe('wipe:2.5')
    const keys = transitionChoices(own).map((choice) => choice.key)
    expect(keys.slice(keys.indexOf('wipe:5'), keys.indexOf('wipe:5') + 2)).toEqual(['wipe:5', 'wipe:2.5'])
    expect(transitionKey(lookTransition(look('embers')))).toBe('cut:0')
  })
})
```

Create `web/src/compose/consequence.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import type { Id, PreviewLight } from '@/api/contract'
import { COPIED_EFFECT, lightPlan, lookName } from '@/api/mocks/fixtures'
import { buildScenario, type ScenarioState } from '@/api/mocks/scenarios'
import { effectWord } from '@/lights/firmware'
import { HERO_NOW } from '@/test/live'
import { waitingText } from '@/zones/zone-view'
import { consequence, lightsPhrase, type ConsequencePart, type ConsequenceSources } from './consequence'

const text = (parts: readonly ConsequencePart[]) => parts.map((part) => part.text).join('')
const looksIn = (parts: readonly ConsequencePart[]) => parts.filter((part) => part.look === true).map((part) => part.text)
const capital = (words: string) => words.charAt(0).toUpperCase() + words.slice(1)

const hero = buildScenario('hero', HERO_NOW)
const zoneName = (state: ScenarioState, id: Id) => state.zones.find((zone) => zone.id === id)!.name

/** The composer's sources for a look on a zone, with the preview's answer as the mock gives it. */
function sources(state: ScenarioState, zoneId: Id, lookId: Id | null, overrides: Partial<ConsequenceSources> = {}): ConsequenceSources {
  const zone = state.zones.find((candidate) => candidate.id === zoneId)!
  const look = lookId === null ? undefined : state.looks.find((candidate) => candidate.id === lookId)!
  const lights = new Map(state.lights.map((light) => [light.id, light]))
  const plan = look === undefined ? null : zone.lights.map((id): PreviewLight => ({ id, ...lightPlan(look, lights.get(id)!) }))
  return { zone, look, running: state.running, lights, plan, missing: [], refused: null, ...overrides }
}

describe('the consequence line', () => {
  // Live-PutLookOn: "Takes over the <room> from <look>." then the lights that run their own effect.
  it('says what the look takes over, and what the lights that run their own effect will run', () => {
    const given = sources(hero, 'living', 'embers')
    const said = consequence(given)
    expect(text(said.parts)).toMatch(new RegExp(`^Takes over the ${zoneName(hero, 'living')} from ${lookName('fireflies')}\\. `))
    expect(looksIn(said.parts)).toEqual([lookName('fireflies')])
    const own = given.plan!.filter((light) => light.mode === 'own-effect')
    expect(own.length).toBeGreaterThan(0)
    expect(text(said.parts)).toContain(`${capital(lightsPhrase(own.map((light) => light.id), given.lights))} will run ${own[0].effect}.`)
    expect(said.blocked).toBe(false)
  })

  // Phone-PutLookOn: "Takes over from <look>", with no firmware sentence.
  it('says it in one short line on the phone', () => {
    const said = consequence(sources(hero, 'living', 'embers'))
    expect(text(said.short)).toBe(`Takes over from ${lookName('fireflies')}`)
    expect(looksIn(said.short)).toEqual([lookName('fireflies')])
  })

  // §11.3: "A zone left with no lights stops."
  it('names every look it takes lights from, newest first, and the zones that stop', () => {
    expect(text(consequence(sources(hero, 'bedroom', 'embers')).parts)).toMatch(
      new RegExp(`^Takes over the ${zoneName(hero, 'bedroom')} from ${lookName('comets')} and ${lookName('homesunset')}\\. ${lookName('comets')} stops\\.`),
    )
    expect(text(consequence(sources(hero, 'home', 'aurora')).parts)).toMatch(
      new RegExp(
        `^Takes over the whole home from ${lookName('homesunset')}, ${lookName('comets')} and ${lookName('fireflies')}\\. ` +
          `${lookName('comets')} and ${lookName('fireflies')} stop\\.`,
      ),
    )
  })

  it('says a look running there already starts again', () => {
    const said = consequence(sources(hero, 'living', 'fireflies'))
    expect(text(said.parts)).toMatch(new RegExp(`^Starts ${lookName('fireflies')} again on the ${zoneName(hero, 'living')}\\.`))
    expect(text(said.short)).toBe(`Starts ${lookName('fireflies')} again`)
  })

  it('says nothing runs there now', () => {
    const quiet = buildScenario('nothing-running', HERO_NOW)
    const said = consequence(sources(quiet, 'kitchen', 'embers'))
    expect(text(said.parts)).toMatch(new RegExp(`^Nothing runs on the ${zoneName(quiet, 'kitchen')} now\\.`))
    expect(text(said.short)).toBe('Nothing runs here now')
  })

  it('asks for a look first, and blocks Start until one is chosen', () => {
    const said = consequence(sources(hero, 'living', null))
    expect(text(said.parts)).toBe('Choose a look to see it on the stage first.')
    expect(said.blocked).toBe(true)
  })

  it('says a zone with no lights has none, and blocks Start', () => {
    const said = consequence(sources(hero, 'counter', 'embers'))
    expect(text(said.parts)).toBe(`The ${zoneName(hero, 'counter')} has no lights.`)
    expect(said.blocked).toBe(true)
  })

  // F4 ruling 3: the engine refuses a whole-home look until M6, and says so.
  it("says why the server refused the preview, and leaves Start to say it again", () => {
    const refused = "Couldn't preview the look. Home looks (whole-home scope) arrive in M6"
    const said = consequence(sources(hero, 'home', 'wisp', { refused }))
    expect(text(said.parts)).toBe(refused)
    expect(text(said.short)).toBe(refused)
    expect(said.blocked).toBe(false)
  })

  // §8.2: "the consequence line says what will happen".
  it('says what a look waiting for an input does', () => {
    const quiet = buildScenario('dj-playing', HERO_NOW)
    const said = consequence(sources(quiet, 'living', 'spectrum', { missing: ['music'] }))
    expect(text(said.parts).endsWith(` ${waitingText('music')}`)).toBe(true)
    expect(text(said.short)).toBe(waitingText('music'))
  })

  it('says which lights get a streamed copy, after those that run their own effect', () => {
    const said = text(consequence(sources(hero, 'home', 'firmware')).parts)
    expect(said).toMatch(new RegExp(`will get a streamed copy of ${effectWord(COPIED_EFFECT)}\\.$`))
    expect(said.indexOf(' will run ')).toBeLessThan(said.indexOf(' will get a streamed copy '))
  })
})

describe('lights by name', () => {
  const named = (...names: string[]) => new Map(names.map((name, index) => [`l${index}`, { id: `l${index}`, name }]))
  const lights = named('Alpha 1', 'Alpha 2', 'Beta', 'Box 1', 'Box 2', 'Gamma 1', 'Gamma 2')

  it('fold numbered lights into their plural when all of them are there', () => {
    expect(lightsPhrase(['l0', 'l1', 'l2'], lights)).toBe('the Alphas and the Beta')
    expect(lightsPhrase(['l3', 'l4'], lights)).toBe('the Boxes')
    expect(lightsPhrase(['l0', 'l2'], lights)).toBe('the Alpha 1 and the Beta')
  })

  it('say how many when there are more than three names', () => {
    expect(lightsPhrase(['l0', 'l2', 'l3', 'l5'], lights)).toBe('4 lights')
  })
})
```

Create `web/src/compose/last-zone.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { lastZone, rememberZone } from './last-zone'

describe('the last zone used', () => {
  it('is remembered in this browser', () => {
    rememberZone('kitchen', localStorage)
    expect(lastZone(localStorage)).toBe('kitchen')
    localStorage.clear()
    expect(lastZone(localStorage)).toBeNull()
  })

  it('is quietly forgotten where storage refuses', () => {
    const refusing = {
      getItem: () => {
        throw new Error('blocked')
      },
      setItem: () => {
        throw new Error('full')
      },
    } as unknown as Storage
    expect(() => rememberZone('kitchen', refusing)).not.toThrow()
    expect(lastZone(refusing)).toBeNull()
    expect(lastZone(null)).toBeNull()
  })
})
```

- [ ] **Step 3: Run them to see them fail**

Run: `(cd web && npx vitest run src/compose)`
Expected: FAIL. `./model`, `./consequence` and `./last-zone` don't resolve, and Vitest reports `3 failed (3)` files with no tests.

- [ ] **Step 4: Move `browserStorage()` where the composer can reach it**

The stage's view memory and the composer's last zone share it, and `src/lib/` keeps it out of the stage's chunk:

Create `web/src/lib/storage.ts`:

```ts
// The browser's localStorage, for per-viewer conveniences: the stage's view (§7.2) and the composer's
// last zone (§8.2). A storage that is missing, full or blocked only costs what it would remember.

/** localStorage, or null where reaching it throws (a sandboxed frame, blocked site data). */
export function browserStorage(): Storage | null {
  try {
    return window.localStorage
  } catch {
    return null
  }
}
```

In `web/src/stage/view-memory.ts`:

```diff
--- a/web/src/stage/view-memory.ts
+++ b/web/src/stage/view-memory.ts
@@ -2,6 +2,7 @@
 // storage that is missing, full, blocked or holding junk only costs the remembered view: every read
 // and write is guarded, and every field is checked on the way in.
 import { useCallback, useState } from 'react'
+import { browserStorage } from '@/lib/storage'
 import { FIT_VIEW, type View } from './camera'
 import { SPEC } from './design-numbers'
 
@@ -18,15 +19,6 @@ export const ZOOM_STEPS = [1, 1.25, 1.5, 2] as const
 
 const KEY = 'dj-ledfx:stage-view:'
 
-/** localStorage, or null where reaching it throws (a sandboxed frame, blocked site data). */
-export function browserStorage(): Storage | null {
-  try {
-    return window.localStorage
-  } catch {
-    return null
-  }
-}
-
 const isRotation = (value: unknown): value is number =>
   typeof value === 'number' && Number.isInteger(value / SPEC.rotate.stepDeg) && Math.abs(value) <= SPEC.rotate.maxDeg
 const isZoom = (value: unknown): value is number => typeof value === 'number' && (ZOOM_STEPS as readonly number[]).includes(value)
```

- [ ] **Step 5: Remember the last zone used**

Create `web/src/compose/last-zone.ts`:

```ts
// §8.2: the composer's zone is "preselected from the room clicked or the last zone used". The last zone
// is a per-viewer convenience in localStorage: a storage that's missing, full or blocked forgets it.
import type { Id } from '@/api/contract'
import { browserStorage } from '@/lib/storage'

const KEY = 'dj-ledfx:compose-zone'

/** The zone a look was last started on from this browser, if it remembers one. */
export function lastZone(storage: Storage | null = browserStorage()): Id | null {
  try {
    return storage?.getItem(KEY) ?? null
  } catch {
    return null
  }
}

/** Remembers the zone a look was started on. */
export function rememberZone(id: Id, storage: Storage | null = browserStorage()): void {
  try {
    storage?.setItem(KEY, id)
  } catch {
    // Full, or blocked: the zone just isn't remembered.
  }
}
```

- [ ] **Step 6: Share the waiting sentence and the transition's label**

The consequence line says a waiting look's sentence as the card's note does (F4 ruling 8), and the transition select labels a transition as the card does (ruling 11):

In `web/src/zones/zone-view.ts`:

```diff
--- a/web/src/zones/zone-view.ts
+++ b/web/src/zones/zone-view.ts
@@ -134,6 +134,17 @@ export const TRANSITION: Record<RunningZoneTransition['kind'], { label: string;
 /** §6.3: "Nothing playing on Music Assistant. The look waits dark and starts with the music." */
 const WAITING_FOR_MUSIC = 'Nothing playing on Music Assistant. The look waits dark and starts with the music.'
 
+/** What a look waiting for an input does: a waiting zone's note, and the composer's consequence line (§8.2). */
+export function waitingText(kind: InputKind): string {
+  return kind === 'music' ? WAITING_FOR_MUSIC : `Waiting for ${INPUTS[kind].label}. The look waits dark and starts when it's there.`
+}
+
+/** A transition as the card, the stage's tag and the composer's select say it: "Dissolve · 3 s", or "Cut" with no duration. */
+export function transitionLabel(kind: RunningZoneTransition['kind'], durationS: number | null): string {
+  const { label } = TRANSITION[kind]
+  return durationS === null ? label : `${label} · ${Math.round(durationS * 10) / 10} s`
+}
+
 const clamp01 = (value: number) => Math.min(Math.max(value, 0), 1)
 const lightCount = (count: number) => (count === 1 ? '1 light' : `${count} lights`)
 const timeOf = (at: string) => formatTime(new Date(at))
@@ -209,9 +220,7 @@ function stateNote(running: RunningZone, world: ZoneWorld, name: string, now: Da
       const waitingFor = running.waitingFor ?? []
       const first = INPUT_ORDER.find((kind) => waitingFor.includes(kind))
       if (first === undefined) return null
-      const text =
-        first === 'music' ? WAITING_FOR_MUSIC : `Waiting for ${INPUTS[first].label}. The look waits dark and starts when it's there.`
-      return { tone: 'quiet', parts: [{ text }] }
+      return { tone: 'quiet', parts: [{ text: waitingText(first) }] }
     }
     default:
       return null
@@ -264,11 +273,9 @@ function firmwareNote(lights: readonly SwatchLight[]): ZoneNote | null {
 /** A served transition as the card and the stage's tag say it; null without one. */
 export function transitionView(transition: RunningZoneTransition | null | undefined): TransitionView | null {
   if (transition == null) return null
-  const { label } = TRANSITION[transition.kind]
   // A duration that isn't above zero (or isn't a number) says nothing.
   const durationS = transition.durationS != null && transition.durationS > 0 ? transition.durationS : null
-  const said = durationS === null ? label : `${label} · ${Math.round(durationS * 10) / 10} s`
-  return { from: transition.from, label: said, progress: clamp01(transition.progress), durationS }
+  return { from: transition.from, label: transitionLabel(transition.kind, durationS), progress: clamp01(transition.progress), durationS }
 }
 
 /** A running zone's lights that REST knows, each with its state, in the zone's order. */
```

- [ ] **Step 7: Write the model**

Create `web/src/compose/model.ts`:

```ts
// The composer's model (§8.2, §8.10 Put a look on): the zone it puts the look on, what runs on each zone
// now, the inputs a look would wait for, the looks a category or a search shows, and the transitions to
// choose from. Pure: the composer gathers its data (REST, the live store), and tests build it from a
// scenario. The words are the spec's and the renders' (Live-PutLookOn, Phone-PutLookOn).
import type { Id, InputKind, Inputs, Look, RunningZone, Transition, Zone } from '@/api/contract'
import { newestFirst } from '@/stage/show'
import { transitionLabel } from '@/zones/zone-view'

/** §8.2's category chips: Starred, then the looks' own categories. */
export type Category = 'starred' | Look['category']

/** "Starred, Ambient, Tempo, Audio, Home, Firmware" (§8.2), in its order. */
export const CATEGORIES: readonly { id: Category; label: string }[] = [
  { id: 'starred', label: 'Starred' },
  { id: 'ambient', label: 'Ambient' },
  { id: 'tempo', label: 'Tempo' },
  { id: 'audio', label: 'Audio' },
  { id: 'home', label: 'Home' },
  { id: 'firmware', label: 'Firmware' },
]

/** §8.2: "Home looks (whole-home scope) lock the zone to Whole home." */
export const locksToHome = (look: Look | undefined): boolean => look?.scope === 'whole-home'

/**
 * The zone the composer puts the look on (F4 ruling 9): the whole home for a home look; else the zone the
 * URL names (the room clicked), else the last one used, else the whole home. A zone that's gone is unnamed.
 */
export function chosenZone(zones: readonly Zone[], asked: Id | null, remembered: Id | null, look: Look | undefined): Zone | undefined {
  const home = zones.find((zone) => zone.kind === 'home')
  if (locksToHome(look)) return home
  const named = (id: Id | null) => (id === null ? undefined : zones.find((zone) => zone.id === id))
  return named(asked) ?? named(remembered) ?? home ?? zones[0]
}

/**
 * What runs on a zone now (§6.3 ZonePicker: "what's running there"): its own look, else the newest look on
 * any of its lights. A room isn't said to run a sub-zone's look, as the stage's labels have it.
 */
export function runningOn(zone: Zone, running: readonly RunningZone[], zones: readonly Zone[]): RunningZone | null {
  const own = running.find((candidate) => candidate.zoneId === zone.id)
  if (own !== undefined) return own
  const subZones = new Set(zones.filter((each) => each.kind === 'sub-zone').map((each) => each.id))
  const lights = new Set(zone.lights)
  return (
    newestFirst(running).find(
      (candidate) => !(zone.kind === 'room' && subZones.has(candidate.zoneId)) && candidate.lights.some((id) => lights.has(id)),
    ) ?? null
  )
}

/** A zone's small text in the ZonePicker (F4 ruling 4; Phone-PutLookOn's "idle" and "no lights"). */
export function zoneNote(zone: Zone, here: RunningZone | null): string {
  if (zone.lights.length === 0) return 'no lights'
  return here?.lookName ?? 'idle'
}

/** The inputs F4 can tell are missing (F4 ruling 8): the tempo clock always runs, and the sun isn't served yet. */
export type MissingInput = Extract<InputKind, 'music' | 'home-assistant'>

/** §8.2: a tile's signal words for the first input its look would wait for. */
export const MISSING_SIGNAL: Record<MissingInput, string> = {
  music: 'Waits for music',
  'home-assistant': 'Needs Home Assistant',
}

/**
 * The inputs a look needs that aren't there (F4 ruling 8), in §6.3's chip order: music with nothing playing
 * or no link (a stale one holds its last value, §9.3), and Home Assistant with no link. Only what the server
 * serves is judged: an input it doesn't send yet is never missing.
 */
export function missingInputs(look: Look, inputs: Pick<Inputs, 'music' | 'homeAssistant'> | null): MissingInput[] {
  const needs = new Set(look.needs ?? [])
  const missing: MissingInput[] = []
  const music = inputs?.music
  if (needs.has('music') && music !== undefined && (music.state === 'disconnected' || music.state === 'idle' || music.track === null)) {
    missing.push('music')
  }
  const homeAssistant = inputs?.homeAssistant
  if (needs.has('home-assistant') && homeAssistant !== undefined && homeAssistant.state === 'disconnected') missing.push('home-assistant')
  return missing
}

/** The tiles a category shows, or a search's over every look (F4 ruling 10), in the server's order. */
export function looksShown(looks: readonly Look[], category: Category, query: string): Look[] {
  const words = query.trim().toLowerCase()
  if (words !== '') return looks.filter((look) => look.name.toLowerCase().includes(words))
  return looks.filter((look) => (category === 'starred' ? look.starred : look.category === category))
}

/** The category the composer opens on (F4 ruling 10): the chosen look's, else the look running there, else Ambient. */
export function openingCategory(look: Look | undefined, here: Look | undefined): Category {
  return look?.category ?? here?.category ?? 'ambient'
}

/** The lengths every kind but a cut is offered at (F4 ruling 11). */
export const TRANSITION_SECONDS = [1, 3, 5] as const

const KINDS = ['fade', 'wipe', 'spread', 'dissolve'] as const
const CUT: Transition = { kind: 'cut', durationS: 0 }

export interface TransitionChoice {
  /** The select's value. */
  key: string
  /** "Dissolve · 3 s", or "Cut". */
  label: string
  transition: Transition
}

/** A look's own transition (§8.2's default): a cut when it has none. */
export const lookTransition = (look: Look | undefined): Transition => look?.transition ?? CUT

function choiceOf({ kind, durationS }: Transition): TransitionChoice {
  const length = kind === 'cut' || durationS <= 0 ? null : durationS
  return { key: `${kind}:${length ?? 0}`, label: transitionLabel(kind, length), transition: { kind, durationS: length ?? 0 } }
}

/**
 * §8.2: "Cut, Fade, Wipe, Spread, Dissolve + duration; default the look's own". A look's own transition,
 * when it's none of these, is offered too, after its kind's others.
 */
export function transitionChoices(look: Look | undefined): TransitionChoice[] {
  const own = choiceOf(lookTransition(look))
  const offered = [CUT, ...KINDS.flatMap((kind) => TRANSITION_SECONDS.map((durationS) => ({ kind, durationS })))].map(choiceOf)
  if (offered.some((choice) => choice.key === own.key)) return offered
  const after = offered.findLastIndex((choice) => choice.transition.kind === own.transition.kind)
  return [...offered.slice(0, after + 1), own, ...offered.slice(after + 1)]
}

/** The choice a transition is, by its key. */
export const transitionKey = (transition: Transition): string => choiceOf(transition).key
```

- [ ] **Step 8: Write the consequence line**

Create `web/src/compose/consequence.ts`:

```ts
// The composer's consequence line (§8.2: "an explanation of consequences"; §11.3: "The UI must show the
// consequence before Start"): what starting the look takes over and stops, what the lights that wouldn't
// stream it do instead (the preview's answer, F4 ruling 1), and what a look that waits for an input does.
// The desktop says it all (Live-PutLookOn); the phone says one short line (Phone-PutLookOn). F4 ruling 14
// has the words.
import type { Id, InputKind, Light, Look, PreviewLight, RunningZone, Zone } from '@/api/contract'
import { formatList } from '@/lib/format'
import { effectWord } from '@/lights/firmware'
import { newestFirst } from '@/stage/show'
import { waitingText } from '@/zones/zone-view'

export interface ConsequencePart {
  text: string
  /** A look's name: serif italic in the renders. */
  look?: boolean
}

export interface Consequence {
  /** The desktop's line, sentence after sentence. */
  parts: ConsequencePart[]
  /** The phone's one line: "Takes over from <look>". */
  short: ConsequencePart[]
  /** Start can't go: no look is chosen, or the zone has no lights. */
  blocked: boolean
}

export interface ConsequenceSources {
  zone: Zone
  look: Look | undefined
  running: readonly RunningZone[]
  /** The home's lights by id, for their names. */
  lights: ReadonlyMap<Id, Pick<Light, 'id' | 'name'>>
  /** What each of the zone's lights would do: the preview's answer, null until it comes. */
  plan: readonly PreviewLight[] | null
  /** The inputs the look would wait for, in §6.3's chip order. */
  missing: readonly InputKind[]
  /** What the preview's failure says, when the server refused the look on the zone. */
  refused: string | null
}

const said = (text: string): ConsequencePart => ({ text })
const named = (text: string): ConsequencePart => ({ text, look: true })
const capital = (text: string) => text.charAt(0).toUpperCase() + text.slice(1)

/** "<A>", "<A> and <B>": look names in serif italic, joined as formatList joins. */
function looks(names: readonly string[]): ConsequencePart[] {
  return names.flatMap((name, index) => [...(index === 0 ? [] : [said(index === names.length - 1 ? ' and ' : ', ')]), named(name)])
}

/** "the <zone>"; the whole home is "the whole home". */
export const zonePhrase = (zone: Zone): string => (zone.kind === 'home' ? 'the whole home' : `the ${zone.name}`)

const only = (sentence: string, blocked: boolean): Consequence => ({ parts: [said(sentence)], short: [said(sentence)], blocked })

const unique = (names: readonly string[]) => [...new Set(names)]

/** A light named with a number: "<name> 2". */
const NUMBERED = /^(.*\S)\s+\d+$/
const plural = (word: string) => (/(s|x|z|ch|sh)$/i.test(word) ? `${word}es` : `${word}s`)

/**
 * The lights by name, each "the <name>" (F4 ruling 14). Numbered lights of one name fold into its plural when
 * every light of that name in the home is there ("the <name>s"), and more than three names say how many.
 */
export function lightsPhrase(ids: readonly Id[], lights: ReadonlyMap<Id, Pick<Light, 'id' | 'name'>>): string {
  const stem = (name: string) => NUMBERED.exec(name)?.[1] ?? null
  const chosen = new Set(ids)
  const phrases: string[] = []
  const folded = new Set<string>()
  for (const id of ids) {
    const name = lights.get(id)?.name ?? id
    const base = stem(name)
    const siblings = base === null ? [] : [...lights.values()].filter((light) => stem(light.name) === base)
    if (base !== null && siblings.length > 1 && siblings.every((light) => chosen.has(light.id))) {
      if (!folded.has(base)) phrases.push(`the ${plural(base)}`)
      folded.add(base)
    } else {
      phrases.push(`the ${name}`)
    }
  }
  return phrases.length > 3 ? `${ids.length} lights` : formatList(phrases)
}

/**
 * The lights that wouldn't stream the look, one sentence per effect, their own effects first: "The <name>
 * and the <name> will run <effect>." and "… will get a streamed copy of <effect>."
 */
function firmwareSentences(plan: readonly PreviewLight[], lights: ConsequenceSources['lights']): string[] {
  const groups = new Map<string, { mode: PreviewLight['mode']; effect: string; ids: Id[] }>()
  for (const { id, mode, effect } of plan) {
    if (mode === 'streaming' || effect === null) continue
    const key = `${mode}:${effect}`
    const group = groups.get(key) ?? { mode, effect, ids: [] }
    group.ids.push(id)
    groups.set(key, group)
  }
  return [...groups.values()]
    .sort((a, b) => Number(a.mode === 'streamed-copy') - Number(b.mode === 'streamed-copy'))
    .map(({ mode, effect, ids }) => {
      const who = capital(lightsPhrase(ids, lights))
      return mode === 'own-effect' ? `${who} will run ${effect}.` : `${who} will get a streamed copy of ${effectWord(effect)}.`
    })
}

export function consequence({ zone, look, running, lights, plan, missing, refused }: ConsequenceSources): Consequence {
  if (look === undefined) return only('Choose a look to see it on the stage first.', true)
  if (zone.lights.length === 0) return only(`${capital(zonePhrase(zone))} has no lights.`, true)
  if (refused !== null) return only(refused, false)

  const taking = new Set(zone.lights)
  const own = running.find((candidate) => candidate.zoneId === zone.id)
  const others = newestFirst(running).filter((other) => other.zoneId !== zone.id && other.lights.some((id) => taking.has(id)))
  const from = unique([...(own !== undefined && own.lookId !== look.id ? [own.lookName] : []), ...others.map((other) => other.lookName)])
  const stops = unique(others.filter((other) => other.lights.every((id) => taking.has(id))).map((other) => other.lookName))
  const again = own !== undefined && own.lookId === look.id
  const waiting = missing.length > 0 ? waitingText(missing[0]) : null

  const parts: ConsequencePart[] = []
  const sentence = (...next: ConsequencePart[]) => {
    if (parts.length > 0) parts.push(said(' '))
    parts.push(...next)
  }
  if (from.length > 0) sentence(said(`Takes over ${zonePhrase(zone)} from `), ...looks(from), said('.'))
  if (again) sentence(said('Starts '), named(look.name), said(` again on ${zonePhrase(zone)}.`))
  if (from.length === 0 && !again) sentence(said(`Nothing runs on ${zonePhrase(zone)} now.`))
  if (stops.length > 0) sentence(...looks(stops), said(stops.length === 1 ? ' stops.' : ' stop.'))
  for (const line of firmwareSentences(plan ?? [], lights)) sentence(said(line))
  if (waiting !== null) sentence(said(waiting))

  const short =
    waiting !== null
      ? [said(waiting)]
      : from.length > 0
        ? [said('Takes over from '), ...looks(from)]
        : again
          ? [said('Starts '), named(look.name), said(' again')]
          : [said('Nothing runs here now')]
  return { parts, short, blocked: false }
}
```

- [ ] **Step 9: Run them to see them pass**

Run: `(cd web && npx vitest run src/compose)`
Expected: PASS (30 tests).

- [ ] **Step 10: Run the gate**

```bash
(cd web && npm test 2>&1 | tail -4 && npm run lint && npx tsc -b && echo "tsc ok")
```

Expected: 762 tests in 96 files; lint is clean, and "tsc ok". The zone card's tests still pass, since its note and transition read the same words through the new exports.

- [ ] **Step 11: Commit**

```bash
git add web/src/compose web/src/lib/storage.ts web/src/stage/view-memory.ts web/src/zones/zone-view.ts
git commit -m "feat(web): the composer's model, and the consequence line's words"
```

---

### Task 5: The stage's `compose` mode

§7.6 compose, as F4 ruling 15 settles it:
- The rooms outside the chosen zone are dimmed, and the zone is outlined.
- While the preview is on, the zone's lights draw the preview stream and the labels name the look previewed.
- A room click chooses its zone.
- The PREVIEW ON SCREEN card shows on desktop, and the tag on the phone.
- The phone frames the zone as `focus` frames one.

`stageBehaviour()` says what each part does, so nothing else checks the mode. The outline is `ZoneOutline`, built from `zonePolygons()`, as F2's and F3's hand-offs asked.

**Files:**
- Modify: `web/src/stage/behaviour.ts`, `web/src/stage/frame-writer.ts`, `web/src/stage/labels.ts`, `web/src/stage/zone-shape.ts`
- Modify: `web/src/stage/overlays/zone-outline.tsx`, `web/src/stage/overlays/stage-svg.tsx`, `web/src/stage/stage-view.tsx`, `web/src/stage/stage.tsx`
- Create: `web/src/stage/overlays/preview-tag.tsx`
- Test: `web/src/stage/behaviour.test.ts`, `web/src/stage/frame-writer.test.ts`, `web/src/stage/labels.test.ts`, `web/src/stage/zone-shape.test.ts`, `web/src/stage/stage-view.test.tsx`

**Interfaces:**
- Consumes:
  - `SPEC.compose {dimmed, outlinePx}` and `SPEC.focus` (F3);
  - `zonePolygons()`, `ZoneOutline`, `newestFirst()`, `projectPoint()`, `useElementSize()`;
  - `FrameStore.get(id, stream)`; `pushFrame(…, { stream })` in tests (Task 3).
- Produces:
  - `behaviour.ts`: `StageMode` gains `'compose'`. `StageBehaviour` gains `roomClick: 'open' | 'choose' | null`, `framesComposeZone`, `legend` and `previewTag: 'card' | 'tag' | null`.
  - `frame-writer.ts`: `WriterEntry.stream`. `writerEntries(bodies, lights, states, rooms, previewed = null)` draws the lights in `previewed` from the preview stream.
  - `labels.ts`: `interface PreviewedLook {zoneId, lookName, lights}`; `stageLabels(home, running, lights, preview = null)`; `looksOn(zone, running)`.
  - `zone-shape.ts`: `zoneRooms(home, zone, lights)`, `interface StageBox`, `boxOf(polygons)` and `besideZone(zone, stage, card)`.
  - `overlays/zone-outline.tsx`: `ZoneDims`. `overlays/stage-svg.tsx`: `interface ComposeShape {dims, chosen}`, and `StageSvg`'s `compose` prop.
  - `overlays/preview-tag.tsx`: `interface PreviewWords`, `PreviewCard` and `PreviewTag`.
  - `stage-view.tsx`: `interface StageCompose {zoneId, lookId, previewing}`, and `StageView`'s `compose` prop. `stage.tsx`: `Stage`'s `compose` prop. In the composer a room's path keeps the look.

- [ ] **Step 1: Read the spec and the renders**

Read §6.3's last `ZonePicker` sentence, §7.2's focus framing, §7.6 (`compose` and `focus`), §8.2 and §8.10's Put a look on row. Then read the render markup:
- In `Live-PutLookOn.html`, the stage's SVG: the dimmed rooms, the zone's outline, the room labels' colours, and the PREVIEW ON SCREEN card.
- In `Phone-PutLookOn.html`, the stage's tag.
- Look at `Live-PutLookOn.png` and `Phone-PutLookOn.png` once each.

- [ ] **Step 2: Write the failing tests**

In `web/src/stage/behaviour.test.ts`:

```diff
--- a/web/src/stage/behaviour.test.ts
+++ b/web/src/stage/behaviour.test.ts
@@ -10,10 +10,14 @@ describe("the stage's behaviour in each mode (§7.6) and on the phone (§8.10)",
   it('is all there on desktop Live, labels as the Labels switch says', () => {
     expect(behaviour({})).toEqual({
       interactive: true,
+      roomClick: 'open',
+      framesComposeZone: false,
       overlays: true,
+      legend: true,
       labels: true,
       sunLabel: true,
       greyed: false,
+      previewTag: null,
       cadenceMs: 1000 / SPEC.target.fps,
     })
     expect(behaviour({ labels: false })).toMatchObject({ labels: false, sunLabel: true })
@@ -23,15 +27,43 @@ describe("the stage's behaviour in each mode (§7.6) and on the phone (§8.10)",
   it('draws the picture alone in focus, at the rate of its variant', () => {
     expect(behaviour({ mode: 'focus', variant: 'phone' })).toEqual({
       interactive: false,
+      roomClick: null,
+      framesComposeZone: true,
       overlays: false,
+      legend: false,
       labels: false,
       sunLabel: false,
       greyed: false,
+      previewTag: null,
       cadenceMs: 1000 / SPEC.phoneFps,
     })
     expect(behaviour({ mode: 'focus' })).toMatchObject({ overlays: false, labels: false, cadenceMs: 1000 / SPEC.target.fps })
   })
 
+  // §7.6 compose; Live-PutLookOn keeps the labels, the sun and the legend, and draws a PREVIEW ON SCREEN card.
+  it('chooses a zone by its room and says the preview is on screen only, in compose', () => {
+    expect(behaviour({ mode: 'compose' })).toEqual({
+      interactive: false,
+      roomClick: 'choose',
+      framesComposeZone: false,
+      overlays: true,
+      legend: true,
+      labels: true,
+      sunLabel: true,
+      greyed: false,
+      previewTag: 'card',
+      cadenceMs: 1000 / SPEC.target.fps,
+    })
+    // Phone-PutLookOn: the zone framed, a tag on the stage, and no labels or legend.
+    expect(behaviour({ mode: 'compose', variant: 'phone' })).toMatchObject({
+      roomClick: 'choose',
+      framesComposeZone: true,
+      legend: false,
+      labels: false,
+      previewTag: 'tag',
+    })
+  })
+
   it("has no labels or overlays on the phone, and draws at the phone's rate", () => {
     expect(behaviour({ variant: 'phone' })).toMatchObject({ interactive: true, overlays: false, labels: false, sunLabel: false })
     expect(behaviour({ variant: 'phone' }).cadenceMs).toBeCloseTo(1000 / SPEC.phoneFps)
@@ -45,6 +77,13 @@ describe("the stage's behaviour in each mode (§7.6) and on the phone (§8.10)",
 
   // §7.6 frozen: "Last frame, grayscale 85%, brightness 55%, no animation"; §9.4: controls come back with the link.
   it('is greyed, still and out of reach while frozen', () => {
-    expect(behaviour({ mode: 'frozen', reducedMotion: true })).toMatchObject({ interactive: false, greyed: true, cadenceMs: null })
+    expect(behaviour({ mode: 'frozen', reducedMotion: true })).toMatchObject({
+      interactive: false,
+      roomClick: null,
+      legend: false,
+      greyed: true,
+      previewTag: null,
+      cadenceMs: null,
+    })
   })
 })
```

In `web/src/stage/frame-writer.test.ts`:

```diff
--- a/web/src/stage/frame-writer.test.ts
+++ b/web/src/stage/frame-writer.test.ts
@@ -20,6 +20,7 @@ const bodyOf = (light: Light): Body => lightBodies(light)[0]
 const entry = (light: Light, patch: Partial<WriterEntry> = {}): WriterEntry => ({
   body: bodyOf(light),
   streamed: true,
+  stream: 'live',
   resting: null,
   room: 1,
   ...patch,
@@ -128,6 +129,19 @@ describe('the frame writer', () => {
     expect([...writer.glowColours]).toEqual([0, 0, 1])
   })
 
+  // §7.6 compose: "the chosen zone renders the preview stream instead of live".
+  it('draws a light from the stream its entry names', () => {
+    const frames = new FrameStore()
+    stream(frames, POINT.id, solid(POINT.leds, [255, 0, 0]))
+    pushFrame(POINT.id, (seq += 1), solid(POINT.leds, [0, 0, 255]), { store: frames, stream: 'preview' })
+    const writer = new FrameWriter([entry(POINT)])
+    writer.write(frames)
+    expect([...writer.glowColours]).toEqual([1, 0, 0])
+    writer.setEntries([entry(POINT, { stream: 'preview' })])
+    writer.write(frames)
+    expect([...writer.glowColours]).toEqual([0, 0, 1])
+  })
+
   it('lights no floor for a light in no room', () => {
     const frames = new FrameStore()
     stream(frames, POINT.id, solid(POINT.leds, [255, 255, 255]))
@@ -175,7 +189,7 @@ describe('the frame writer', () => {
     }
     const frames = new FrameStore()
     stream(frames, pc.id, solid(pc.leds, [9, 9, 9]))
-    const writer = new FrameWriter(lightBodies(placed).map((body) => ({ body, streamed: true, resting: null, room: 1 })))
+    const writer = new FrameWriter(lightBodies(placed).map((body) => ({ body, streamed: true, stream: 'live' as const, resting: null, room: 1 })))
     writer.write(frames)
     expect(writer.leds).toBe(pc.leds)
     writer.write(new FrameStore())
@@ -201,6 +215,15 @@ describe('the writer entries', () => {
     expect(homeFixture.rooms[only.room - 1].id).toBe(light.room)
   })
 
+  // §7.6 compose: the chosen zone's lights draw the preview, whatever they do now.
+  it('draw the previewed lights from the preview stream, streaming or not', () => {
+    const idle: Light = { ...POINT, status: 'idle', power: true, colour: '#00ff00' }
+    const entriesOf = (previewed: Set<Id> | null) => writerEntries(lightBodies(idle), [idle], lightStates([idle]), homeFixture.rooms, previewed)
+    expect(entriesOf(new Set([idle.id]))[0]).toMatchObject({ streamed: true, stream: 'preview', resting: [0, 255, 0] })
+    expect(entriesOf(new Set())[0]).toMatchObject({ streamed: false, stream: 'live' })
+    expect(entriesOf(null)[0]).toMatchObject({ streamed: false, stream: 'live' })
+  })
+
   // §9.1: offline and switched-off lights show only their marks, which are the overlay's.
   it('leave out offline and switched-off lights', () => {
     const lights: Light[] = [{ ...POINT, status: 'offline' }, { ...STRIP, status: 'switched-off' }, { ...GRID, status: 'streaming' }]
```

In `web/src/stage/labels.test.ts`:

```diff
--- a/web/src/stage/labels.test.ts
+++ b/web/src/stage/labels.test.ts
@@ -2,7 +2,7 @@ import { describe, expect, it } from 'vitest'
 import { lookName, OWNER_ROOM_NAMES, roomName } from '@/api/mocks/fixtures'
 import { buildScenario } from '@/api/mocks/scenarios'
 import { HERO_NOW } from '@/test/live'
-import { stageLabels } from './labels'
+import { looksOn, stageLabels } from './labels'
 
 describe('the room labels (§7.6)', () => {
   it("names every room, with the look on its lights beneath, as Main.png does", () => {
@@ -38,6 +38,21 @@ describe('the room labels (§7.6)', () => {
     expect(labels.find((label) => label.key === 'kitchen')!.look).toBe(lookName('homesunset'))
   })
 
+  // Live-PutLookOn: the room's name over the look previewed there.
+  it("names the composer's look on its zone, as the newest there", () => {
+    const hero = buildScenario('hero', HERO_NOW)
+    const zone = (id: string) => hero.zones.find((candidate) => candidate.id === id)!
+    const previewed = (id: string) => ({ zoneId: id, lookName: lookName('embers'), lights: zone(id).lights })
+    const looks = (id: string) =>
+      Object.fromEntries(stageLabels(hero.home, hero.running, hero.lights, previewed(id)).map((label) => [label.key, label.look]))
+    expect(looks('living')).toMatchObject({ living: lookName('embers'), kitchen: lookName('homesunset'), office: lookName('comets') })
+    expect(looks('office')).toMatchObject({ office: lookName('embers'), bedroom: lookName('homesunset') })
+    // The whole home covers the sub-zone's lights: its own label goes, and every lit room shows the preview.
+    const home = looks('home')
+    expect(home).toMatchObject({ living: lookName('embers'), bedroom: lookName('embers'), corridor: lookName('embers') })
+    expect(home).not.toHaveProperty('office')
+  })
+
   it('shows the newest look where two run on one room', () => {
     const hero = buildScenario('hero', HERO_NOW)
     const living = hero.running.find((zone) => zone.zoneId === 'living')!
@@ -46,3 +61,14 @@ describe('the room labels (§7.6)', () => {
     expect(labels.find((label) => label.key === 'living')!.look).toBe(lookName('fireflies'))
   })
 })
+
+describe("the looks a zone's lights still run", () => {
+  it('are its own look first, then the newest of the others on its lights', () => {
+    const hero = buildScenario('hero', HERO_NOW)
+    const zone = (id: string) => hero.zones.find((each) => each.id === id)!
+    expect(looksOn(zone('living'), hero.running)).toEqual([lookName('fireflies')])
+    expect(looksOn(zone('bedroom'), hero.running)).toEqual([lookName('comets'), lookName('homesunset')])
+    const quiet = buildScenario('nothing-running', HERO_NOW)
+    expect(looksOn(quiet.zones.find((each) => each.id === 'kitchen')!, quiet.running)).toEqual([])
+  })
+})
```

In `web/src/stage/zone-shape.test.ts`:

```diff
--- a/web/src/stage/zone-shape.test.ts
+++ b/web/src/stage/zone-shape.test.ts
@@ -4,7 +4,7 @@ import { buildScenario } from '@/api/mocks/scenarios'
 import { HERO_NOW } from '@/test/live'
 import { stageBodies } from './bodies'
 import { anchorOf } from './marks'
-import { zoneMiddle, zonePolygons } from './zone-shape'
+import { besideZone, boxOf, zoneMiddle, zonePolygons, zoneRooms } from './zone-shape'
 
 const { home, lights, zones } = buildScenario('hero', HERO_NOW)
 const zone = (id: string) => zones.find((each) => each.id === id)!
@@ -23,6 +23,29 @@ describe("a zone's place on the stage", () => {
     expect(zonePolygons(home, undefined, lights)).toEqual([])
   })
 
+  // §7.6 compose: "Rooms outside the chosen zone dimmed".
+  it('lights its own rooms: all of them for the whole home, its room for a sub-zone, its lights\' for a group', () => {
+    expect(zoneRooms(home, zone('home'), lights)).toEqual(new Set(home.rooms.map((room) => room.id)))
+    expect(zoneRooms(home, zone('living'), lights)).toEqual(new Set(['living']))
+    expect(zoneRooms(home, zone('office'), lights)).toEqual(new Set([home.subZones.find((sub) => sub.id === 'office')!.room]))
+    const pair = [lights.find((light) => light.room === 'kitchen')!, lights.find((light) => light.room === 'bedroom')!]
+    const group: Zone = { id: 'pair', name: 'Pair', kind: 'group', lights: pair.map((light) => light.id) }
+    expect(zoneRooms(home, group, lights)).toEqual(new Set(['kitchen', 'bedroom']))
+  })
+
+  // F4 ruling 15: Live-PutLookOn's card sits left of the room it previews on.
+  it('puts a card left of its zone, else right, else over it, and keeps it on the stage', () => {
+    const stage = { width: 1000, height: 800 }
+    const card = { width: 200, height: 80 }
+    const box = (left: number, right: number) => ({ left, right, top: 300, bottom: 500 })
+    expect(besideZone(box(500, 700), stage, card)).toEqual([300, 360])
+    expect(besideZone(box(100, 300), stage, card)).toEqual([300, 360])
+    expect(besideZone(box(100, 900), stage, card)).toEqual([400, 360])
+    expect(besideZone({ left: 500, right: 700, top: -100, bottom: 0 }, stage, card)).toEqual([300, 0])
+    expect(boxOf([[[1, 5], [4, 2]], [[3, 9]]])).toEqual({ left: 1, top: 2, right: 4, bottom: 9 })
+    expect(boxOf([])).toBeNull()
+  })
+
   // F3 decision 18.
   it("puts a zone's tag at the middle of its lights, and nowhere when none is placed", () => {
     const bodies = stageBodies(lights)
```

In `web/src/stage/stage-view.test.tsx`:

```diff
--- a/web/src/stage/stage-view.test.tsx
+++ b/web/src/stage/stage-view.test.tsx
@@ -1,10 +1,12 @@
 import { act, fireEvent, screen, within } from '@testing-library/react'
 import userEvent from '@testing-library/user-event'
+import { useSearchParams } from 'react-router'
 import { beforeEach, describe, expect, it, vi } from 'vitest'
 import { applyMessage, liveStore } from '@/api/live-store'
-import { roomName } from '@/api/mocks/fixtures'
+import { lookName, roomName } from '@/api/mocks/fixtures'
 import type { ScenarioName } from '@/api/mocks/scenarios'
 import { LIVE_SPEC } from '@/design/live-numbers'
+import type { ElementSize } from '@/lib/use-element-size'
 import { renderApp } from '@/test/app'
 import { renders, resetRenders } from '@/test/count-renders'
 import { pushFrame } from '@/test/live'
@@ -18,6 +20,7 @@ import { anchorOf } from './marks'
 import { STAGE_LABEL } from './stage-pending'
 import { sunPosition, sunScene } from './sun'
 import Stage from './stage'
+import type { StageVariant } from './stage-view'
 import { readStageView } from './view-memory'
 import { hasWebGL2 } from './webgl'
 import { zonePolygons } from './zone-shape'
@@ -319,3 +322,106 @@ describe('the stage in focus (§7.6)', () => {
     expect(picture().style.filter).toBe(`grayscale(${SPEC.frozen.grayscale}) brightness(${SPEC.frozen.brightness})`)
   })
 })
+
+describe('the stage in compose (§7.6)', () => {
+  /** The composer's stage on what the URL says, as the composer hands it over: ?zone=, ?look= and the look previewed. */
+  function Composing({ variant }: { variant: StageVariant }) {
+    const [params] = useSearchParams()
+    const compose = { zoneId: params.get('zone')!, lookId: params.get('look'), previewing: params.get('previewing') }
+    return <Stage variant={variant} compose={compose} />
+  }
+
+  async function openCompose(
+    search: string,
+    { variant = 'desktop', size = MAIN_STAGE, scenario = 'hero' }: { variant?: StageVariant; size?: ElementSize; scenario?: ScenarioName } = {},
+  ) {
+    const state = seedStage(scenario)
+    const router = renderApp(`/next/live/put${search}`, { routes: [{ path: '/live/put', element: <Composing variant={variant} /> }] })
+    await loadedStage()
+    act(() => resizeObserved(size.width, size.height))
+    return { state, router, pose: heroPose() }
+  }
+  const previewing = (id: string) => `&previewing=${encodeURIComponent(lookName(id))}`
+  /** The streams the canvas draws the zone's lights from, and the rest of the lights. */
+  const streams = (lights: readonly string[]) => {
+    const ids = new Set(lights)
+    const of = (inZone: boolean) => new Set(drawn.props!.entries.filter((entry) => ids.has(entry.body.lightId) === inZone).map((entry) => entry.stream))
+    return { zone: of(true), rest: of(false) }
+  }
+
+  // Live-PutLookOn: the other rooms dimmed under the zone's outline, the zone's labels bright, and a card.
+  it("dims the rooms outside the zone, outlines it, and draws the preview there with a card beside it", async () => {
+    const { state, router } = await openCompose(`?zone=living&look=embers${previewing('embers')}`)
+    const zone = state.zones.find((each) => each.id === 'living')!
+    const stage = within(screen.getByRole('region', { name: STAGE_LABEL }))
+    const dims = document.querySelector('[data-dims]')!
+    const outline = document.querySelector('[data-outline]')!
+    expect(dims.querySelectorAll('polygon')).toHaveLength(state.home.rooms.length - 1)
+    expect(outline).toHaveAttribute('data-outline', 'living')
+    // Over the labels, as the render layers them: the labels, then the dims, then the outline.
+    const label = stage.getByText(zone.name)
+    expect(label.compareDocumentPosition(dims) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
+    expect(dims.compareDocumentPosition(outline) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
+    expect(label).toHaveClass('fill-text')
+    const other = state.home.rooms.find((room) => room.id !== 'living' && room.hasLights)!
+    expect(stage.getByText(other.name)).toHaveClass('fill-text-3')
+    // The zone's label names the look previewed, and its lights draw the preview stream.
+    expect(stage.getByText(lookName('embers'))).toHaveClass('fill-text')
+    expect(streams(zone.lights)).toEqual({ zone: new Set(['preview']), rest: new Set(['live']) })
+    expect(document.querySelector('[data-preview-card]')).toHaveTextContent(
+      `Preview on screen${lookName('embers')} on ${zone.name}. The lights are still running ${lookName('fireflies')}.`,
+    )
+    // The legend and the sun stay; Live's tools, readout, tags and links don't.
+    expect(screen.getByRole('list', { name: 'What the lights show' })).toBeInTheDocument()
+    expect(stage.getByText(sunScene(state.home, state.inputs.sun)!.label!)).toBeInTheDocument()
+    expect(screen.queryByRole('switch', { name: 'Labels' })).not.toBeInTheDocument()
+    expect(screen.queryByText(sunPosition(state.inputs.sun)!)).not.toBeInTheDocument()
+    expect(screen.queryByRole('navigation', { name: 'Rooms' })).not.toBeInTheDocument()
+
+    // The preview ends: the lights draw the live stream again, and the card goes.
+    await act(() => router.navigate('/live/put?zone=living&look=embers', { replace: true }))
+    expect(streams(zone.lights)).toEqual({ zone: new Set(['live']), rest: new Set(['live']) })
+    expect(stage.getByText(lookName('fireflies'))).toHaveClass('fill-text')
+    expect(document.querySelector('[data-preview-card]')).toBeNull()
+    expect(document.querySelector('[data-outline]')).toHaveAttribute('data-outline', 'living')
+  })
+
+  it('says the lights are as they were where nothing runs', async () => {
+    await openCompose(`?zone=kitchen&look=embers${previewing('embers')}`, { scenario: 'nothing-running' })
+    expect(document.querySelector('[data-preview-card]')).toHaveTextContent(/\. The lights are as they were\.$/)
+  })
+
+  // §6.3 ZonePicker: "Clicking a room on the stage selects the same zone": in place, the look kept, no tooltip.
+  it('chooses the zone of a room clicked, keeping the look, and shows no tooltip', async () => {
+    const { state, router, pose } = await openCompose('?zone=living&look=embers')
+    const room = state.home.rooms.find((candidate) => candidate.hasLights && candidate.id !== 'living')!
+    const [x, y] = projectPoint(pose, [...room.labelAt, 0])
+    fireEvent.click(picture(), { clientX: x, clientY: y })
+    expect(router.state.location.pathname).toBe('/next/live/put')
+    expect(router.state.location.search).toBe(`?zone=${room.id}&look=embers`)
+    expect(router.state.historyAction).toBe('REPLACE')
+    expect(document.querySelector('[data-outline]')).toHaveAttribute('data-outline', room.id)
+    const light = state.lights.find((candidate) => candidate.shape != null)!
+    const [lx, ly] = projectPoint(pose, anchorOf(lightBodies(light)[0]))
+    fireEvent.pointerMove(picture(), { clientX: lx, clientY: ly, pointerType: 'mouse' })
+    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
+  })
+
+  // Phone-PutLookOn: framed on the zone as focus frames one, the lights round it kept, and a tag.
+  it("frames the phone's zone, keeps the lights round it, tags the preview, and keeps the frame through a drop", async () => {
+    const size = LIVE_SPEC.phoneStage
+    const { state } = await openCompose(`?zone=living&look=embers${previewing('embers')}`, { variant: 'phone', size })
+    const zone = state.zones.find((each) => each.id === 'living')!
+    const framed = fitPose(zonePolygons(state.home, zone, state.lights).flat(), size, FIT_VIEW, SPEC.focus.tiltDeg)
+    expect(drawn.props!.pose).toEqual(framed)
+    expect(drawn.props!.entries).toHaveLength(stageWriter(state.lights, { rooms: state.home.rooms }).entries.length)
+    expect(picture().querySelector('[data-vignette]')).toBeNull()
+    expect(screen.getByText('Preview on screen · lights unchanged')).toBeInTheDocument()
+    expect(document.querySelector('[data-preview-card]')).toBeNull()
+    expect(screen.queryByRole('list', { name: 'What the lights show' })).not.toBeInTheDocument()
+    act(() => liveStore.setState({ connection: { status: 'reconnecting', attempt: 1 } }))
+    expect(drawn.props!.pose).toEqual(framed)
+    expect(document.querySelector('[data-dims]')).not.toBeNull()
+    expect(screen.queryByText('Preview on screen · lights unchanged')).not.toBeInTheDocument()
+  })
+})
```

- [ ] **Step 3: Run them to see them fail**

Run: `(cd web && npx vitest run src/stage/behaviour.test.ts src/stage/frame-writer.test.ts src/stage/labels.test.ts src/stage/zone-shape.test.ts src/stage/stage-view.test.tsx)`
Expected: FAIL: `14 failed | 41 passed (55)`. There's no `compose` mode or `roomClick`, `zoneRooms` and `besideZone` aren't functions, the writer's entries have no stream, the labels take no preview, and `StageView` has no `compose`.

- [ ] **Step 4: Say what `compose` does**

In `web/src/stage/behaviour.ts`:

```diff
--- a/web/src/stage/behaviour.ts
+++ b/web/src/stage/behaviour.ts
@@ -1,14 +1,15 @@
 // §7.6's modes table in code: what the stage does in each mode, on each variant (§8.10's phone).
 // StageView asks once and hands the answers down; nothing else checks the mode or the variant. The
-// modes F4 and F7 bring (compose, map) extend it.
+// mode F7 brings (map) extends it.
 import { LIVE_SPEC } from '@/design/live-numbers'
 import { SPEC } from './design-numbers'
 
 /**
- * §7.6's modes so far: `live`; `focus`, framed on one zone (Zone detail; the editor's preview and the
- * phone's tweak later); and `frozen` while the link is down (§9.4 Reconnecting), on either.
+ * §7.6's modes so far: `live`; `compose`, the composer's (§8.2); `focus`, framed on one zone (Zone
+ * detail; the editor's preview and the phone's tweak later); and `frozen` while the link is down (§9.4
+ * Reconnecting), on any of them.
  */
-export type StageMode = 'live' | 'focus' | 'frozen'
+export type StageMode = 'live' | 'compose' | 'focus' | 'frozen'
 /** The phone's stage is §8.10's: no labels, no overlays. */
 export type StageVariant = 'desktop' | 'phone'
 
@@ -23,18 +24,35 @@ export interface StageOptions {
 
 export interface StageBehaviour {
   /**
-   * The interactive layer: the pointer on the picture (§8.1's hover tooltip and room click), the
-   * overlays and the rooms' links. §7.6 frozen has none: "Controls come back when the link does" (§9.4).
+   * Live's interactive layer: §8.1's hover tooltip, the overlays, the zones' tags and the rooms' links.
+   * §7.6 frozen has none: "Controls come back when the link does" (§9.4).
    */
   interactive: boolean
-  /** §8.1's overlays: the tools, the sun readout, the legend and the view controls. */
+  /**
+   * A click on a room: Live's opens the composer on it (§8.1), a page of its own; the composer's chooses
+   * its zone (§6.3 ZonePicker) in place. Null where a click does nothing.
+   */
+  roomClick: 'open' | 'choose' | null
+  /**
+   * The composer frames its zone as focus frames one (§7.2), keeping the other lights: on the phone, whose
+   * stage is too small for the whole home (Phone-PutLookOn). Desktop's keeps Live's view (Live-PutLookOn).
+   */
+  framesComposeZone: boolean
+  /** §8.1's overlays: the tools, the sun readout and the view controls, and so the view they keep. */
   overlays: boolean
+  /** §8.1's legend: Live's, and the composer's (Live-PutLookOn draws it). */
+  legend: boolean
   /** The rooms' labels (§7.6). */
   labels: boolean
   /** The sun's mono label (§7.4); Phone-Live.png draws the sun without it. */
   sunLabel: boolean
   /** The picture greyed as SPEC.frozen says (§7.6 frozen). */
   greyed: boolean
+  /**
+   * §7.6 compose's "PREVIEW ON SCREEN": a card beside the zone (Live-PutLookOn), a tag on the phone's
+   * stage (Phone-PutLookOn); null outside the composer.
+   */
+  previewTag: 'card' | 'tag' | null
   /**
    * Milliseconds between draws: SPEC.target.fps's on desktop and SPEC.phoneFps's on a phone (§7.5),
    * LIVE_SPEC.reducedMotionMs with reduced motion (§5.4); null while frames don't redraw the stage (§7.6
@@ -45,15 +63,20 @@ export interface StageBehaviour {
 
 export function stageBehaviour({ mode, variant, reducedMotion, labels }: StageOptions): StageBehaviour {
   const live = mode === 'live'
+  const compose = mode === 'compose'
   const phone = variant === 'phone'
   // §7.6 focus is the zone's picture alone: what frames it and hides the other lights is StageView's `focus`.
   const focus = mode === 'focus'
   return {
     interactive: live,
+    roomClick: live ? 'open' : compose ? 'choose' : null,
+    framesComposeZone: phone,
     overlays: !phone && !focus,
+    legend: !phone && (live || compose),
     labels: !phone && !focus && labels,
     sunLabel: !phone && !focus,
     greyed: mode === 'frozen',
+    previewTag: compose ? (phone ? 'tag' : 'card') : null,
     cadenceMs: mode === 'frozen' ? null : reducedMotion ? LIVE_SPEC.reducedMotionMs : 1000 / (phone ? SPEC.phoneFps : SPEC.target.fps),
   }
 }
```

- [ ] **Step 5: Draw the zone's lights from the preview stream**

In `web/src/stage/frame-writer.ts`:

```diff
--- a/web/src/stage/frame-writer.ts
+++ b/web/src/stage/frame-writer.ts
@@ -3,8 +3,9 @@
 // made once, when which bodies are drawn changes (sameLayout()), so a frame allocates nothing, and
 // nor does a `lights` push that changes only colours: setEntries() takes those in place. The light
 // layer hands these very arrays to three. Offline and switched-off lights have no entry (§9.1): their
-// marks are the overlay's.
-import type { Id, Light, Room } from '@/api/contract'
+// marks are the overlay's. In the composer the chosen zone's lights are drawn from the preview stream
+// (§7.6 compose), and every other light from the live one.
+import type { FrameStream, Id, Light, Room } from '@/api/contract'
 import type { FrameStore } from '@/api/frames'
 import { hueOf, isDark, mix, type RGB } from '@/lib/light-colour'
 import { anchorIndex, type Body } from './bodies'
@@ -18,6 +19,8 @@ export interface WriterEntry {
   body: Body
   /** Its light's frames are streamed: drawn from them once one has come. */
   streamed: boolean
+  /** The stream they're drawn from. */
+  stream: FrameStream
   /** The colour drawn without a frame; null draws the light dark. */
   resting: RGB | null
   /** The room whose floor its pools may light: 1-based in home.rooms; 0 lights none. */
@@ -35,6 +38,7 @@ interface Slot {
   body: Body
   room: number
   streamed: boolean
+  stream: FrameStream
   resting: RGB | null
   /** Its first halo and pool. */
   glow: number
@@ -98,11 +102,12 @@ export class FrameWriter {
     let glow = 0
     let core = 0
     const next = { narrow: 0, wide: 0 }
-    for (const { body, room, streamed, resting } of entries) {
+    for (const { body, room, streamed, stream, resting } of entries) {
       const slot: Slot = {
         body,
         room,
         streamed,
+        stream,
         resting,
         glow,
         core: -1,
@@ -136,14 +141,15 @@ export class FrameWriter {
   }
 
   /**
-   * Whether each light streams and the colour it rests on, from entries laid out as this writer's
-   * (sameLayout()): a `lights` push that changes only those reallocates nothing.
+   * Whether each light streams, from which stream, and the colour it rests on, from entries laid out as
+   * this writer's (sameLayout()): a `lights` push or a preview that changes only those reallocates nothing.
    */
   setEntries(entries: readonly WriterEntry[]): void {
     if (entries.length !== this.slots.length) throw new Error('FrameWriter.setEntries: the entries are laid out differently')
     entries.forEach((entry, index) => {
       const slot = this.slots[index]
       slot.streamed = entry.streamed
+      slot.stream = entry.stream
       slot.resting = entry.resting
     })
   }
@@ -158,7 +164,7 @@ export class FrameWriter {
     let leds = 0
     for (const slot of this.slots) {
       const { body, room, resting, strip } = slot
-      const frame = slot.streamed ? frames.get(body.lightId) : undefined
+      const frame = slot.streamed ? frames.get(body.lightId, slot.stream) : undefined
       if (frame !== undefined && slot.counts) leds += Math.min(frame.count, body.ledCount)
       const compact = body.form === 'compact'
       const count = body.samples.length
@@ -242,12 +248,16 @@ export class FrameWriter {
   }
 }
 
-/** Each drawn body with whether its light streams, the colour it rests on, and its room. */
+/**
+ * Each drawn body with whether its light streams and from which stream, the colour it rests on, and its
+ * room. A light in `previewed` is drawn from the preview stream, whatever it does now (§7.6 compose).
+ */
 export function writerEntries(
   bodies: readonly Body[],
   lights: readonly Light[],
   states: ReadonlyMap<Id, LightState>,
   rooms: readonly Room[],
+  previewed: ReadonlySet<Id> | null = null,
 ): WriterEntry[] {
   const byId = new Map(lights.map((light) => [light.id, light]))
   return bodies.flatMap((body) => {
@@ -255,7 +265,8 @@ export function writerEntries(
     const state = states.get(body.lightId)
     if (light === undefined || state === undefined || !isDrawn(state)) return []
     const room = rooms.findIndex((candidate) => candidate.id === light.room) + 1
-    return [{ body, streamed: isStreamed(state), resting: restingColour(state), room }]
+    const preview = previewed?.has(body.lightId) === true
+    return [{ body, streamed: preview || isStreamed(state), stream: preview ? 'preview' : 'live', resting: restingColour(state), room }]
   })
 }
 
```

- [ ] **Step 6: Label the look previewed**

In `web/src/stage/labels.ts`:

```diff
--- a/web/src/stage/labels.ts
+++ b/web/src/stage/labels.ts
@@ -2,7 +2,9 @@
 // whose lights a look runs on gets the look beneath, the newest one there. A running sub-zone gets a
 // label of its own at its middle, as Main.png shows one, and its lights don't count for its room. A zone
 // turning from one look into another names both, as State-Transition does ("Fireflies → Embers").
-import type { Home, Id, Light, RunningZone, Vec3 } from '@/api/contract'
+// In the composer the look previewed on its zone counts as the newest on the zone's lights, so
+// Live-PutLookOn labels the room with the look it previews.
+import type { Home, Id, Light, RunningZone, Vec3, Zone } from '@/api/contract'
 import { centroid } from './plan'
 import { newestFirst } from './show'
 
@@ -15,14 +17,33 @@ export interface StageLabel {
   at: Vec3
 }
 
-function lookOf(zone: RunningZone): string {
+/** The composer's look on its zone, while the stage draws it from the preview stream. */
+export interface PreviewedLook {
+  zoneId: Id
+  lookName: string
+  lights: readonly Id[]
+}
+
+type Labelled = PreviewedLook & Partial<Pick<RunningZone, 'state' | 'transition'>>
+
+function lookOf(zone: Labelled): string {
   return zone.state === 'transition' && zone.transition != null ? `${zone.transition.from} → ${zone.lookName}` : zone.lookName
 }
 
-export function stageLabels(home: Home, running: readonly RunningZone[], lights: readonly Light[]): StageLabel[] {
+export function stageLabels(
+  home: Home,
+  running: readonly RunningZone[],
+  lights: readonly Light[],
+  preview: PreviewedLook | null = null,
+): StageLabel[] {
   const subZones = new Map(home.subZones.map((subZone) => [subZone.id, subZone]))
   const roomOf = new Map<Id, Id | null | undefined>(lights.map((light) => [light.id, light.room]))
-  const newest = newestFirst(running)
+  // A zone the preview covers whole has nothing left to label.
+  const covered = new Set(preview?.lights)
+  const others = newestFirst(running).filter(
+    (zone) => preview === null || (zone.zoneId !== preview.zoneId && !zone.lights.every((id) => covered.has(id))),
+  )
+  const newest: Labelled[] = preview === null ? others : [preview, ...others]
   const wide = newest.filter((zone) => !subZones.has(zone.zoneId))
   const rooms = home.rooms.map((room): StageLabel => {
     const zone = wide.find((candidate) => candidate.lights.some((id) => roomOf.get(id) === room.id))
@@ -36,3 +57,14 @@ export function stageLabels(home: Home, running: readonly RunningZone[], lights:
   })
   return [...rooms, ...parts]
 }
+
+/**
+ * The looks a zone's lights run now, its own first, then the newest: what the composer's preview card
+ * says they still run (Live-PutLookOn: "The lights are still running <look>.").
+ */
+export function looksOn(zone: Pick<Zone, 'id' | 'lights'>, running: readonly RunningZone[]): string[] {
+  const lights = new Set(zone.lights)
+  const own = running.filter((candidate) => candidate.zoneId === zone.id)
+  const others = newestFirst(running).filter((candidate) => candidate.zoneId !== zone.id && candidate.lights.some((id) => lights.has(id)))
+  return [...new Set([...own, ...others].map((candidate) => candidate.lookName))]
+}
```

- [ ] **Step 7: The zone's rooms, and where the card goes**

In `web/src/stage/zone-shape.ts`:

```diff
--- a/web/src/stage/zone-shape.ts
+++ b/web/src/stage/zone-shape.ts
@@ -1,6 +1,8 @@
 // Where a zone is on the stage: its floor polygons, for §8.1's "Hover a card → its zone outlines on the
-// stage", and the middle of its lights, where its tag goes (F3 decision 18). Plan metres throughout.
+// stage", the rooms it lights, which §7.6 compose leaves undimmed, and the middle of its lights, where its
+// tag goes (F3 decision 18), in plan metres; and where a card beside it goes, in CSS px.
 import type { Home, Id, Light, Vec2, Vec3, Zone } from '@/api/contract'
+import type { ElementSize } from '@/lib/use-element-size'
 import type { Body } from './bodies'
 import { anchorOf } from './marks'
 
@@ -30,3 +32,56 @@ export function zoneMiddle(bodies: readonly Body[], lights: readonly Id[]): Vec3
   const sum = anchors.reduce<Vec3>((total, at) => [total[0] + at[0], total[1] + at[1], total[2] + at[2]], [0, 0, 0])
   return [sum[0] / anchors.length, sum[1] / anchors.length, sum[2] / anchors.length]
 }
+
+/**
+ * The rooms a zone lights (§7.6 compose: "Rooms outside the chosen zone dimmed"): every room for the
+ * whole home, a room itself, a sub-zone's room, and for a group the rooms its lights stand in.
+ */
+export function zoneRooms(home: Home, zone: Zone, lights: readonly Light[]): Set<Id> {
+  switch (zone.kind) {
+    case 'home':
+      return new Set(home.rooms.map((room) => room.id))
+    case 'room':
+      return new Set([zone.id])
+    case 'sub-zone':
+      return new Set(home.subZones.filter((sub) => sub.id === zone.id).map((sub) => sub.room))
+    case 'group': {
+      const members = new Set(zone.lights)
+      return new Set(lights.flatMap((light) => (members.has(light.id) && light.room != null ? [light.room] : [])))
+    }
+  }
+}
+
+/** A box round some points on the stage, CSS px. */
+export interface StageBox {
+  left: number
+  top: number
+  right: number
+  bottom: number
+}
+
+/** The box round projected polygons; null for none. */
+export function boxOf(polygons: readonly (readonly Vec2[])[]): StageBox | null {
+  const points = polygons.flat()
+  if (points.length === 0) return null
+  const xs = points.map(([x]) => x)
+  const ys = points.map(([, y]) => y)
+  return { left: Math.min(...xs), top: Math.min(...ys), right: Math.max(...xs), bottom: Math.max(...ys) }
+}
+
+/**
+ * Where a card goes beside a zone (F4 ruling 15; Live-PutLookOn's PREVIEW ON SCREEN): left of the zone
+ * where it fits, else right of it, else over its middle; centred on it from top to bottom; and inside the
+ * stage. Its top-left corner, CSS px.
+ */
+export function besideZone(zone: StageBox, stage: ElementSize, card: ElementSize): Vec2 {
+  const left =
+    zone.left - card.width >= 0
+      ? zone.left - card.width
+      : zone.right + card.width <= stage.width
+        ? zone.right
+        : (zone.left + zone.right - card.width) / 2
+  const top = (zone.top + zone.bottom - card.height) / 2
+  const inside = (value: number, room: number) => Math.min(Math.max(value, 0), Math.max(room, 0))
+  return [inside(left, stage.width - card.width), inside(top, stage.height - card.height)]
+}
```

- [ ] **Step 8: Dim the other rooms, and outline the zone over them**

Live-PutLookOn layers it so: the dims over the labels, and the outline over the dims.

In `web/src/stage/overlays/zone-outline.tsx`:

```diff
--- a/web/src/stage/overlays/zone-outline.tsx
+++ b/web/src/stage/overlays/zone-outline.tsx
@@ -1,9 +1,11 @@
 // §8.1 "Hover a card → its zone outlines on the stage", drawn as §7.6 compose outlines its chosen zone:
-// SPEC.compose.outlinePx of `text`, on the floor.
+// SPEC.compose.outlinePx of `text`, on the floor; and compose's other rooms, dimmed.
 import type { Id, Vec2 } from '@/api/contract'
 import { SPEC } from '../design-numbers'
 import { cssColour } from '../palette'
 
+const points = (polygon: readonly Vec2[]) => polygon.map(([x, y]) => `${x},${y}`).join(' ')
+
 export interface ZoneOutlineShape {
   zoneId: Id
   /** On the stage, in CSS px. */
@@ -14,7 +16,18 @@ export function ZoneOutline({ outline }: { outline: ZoneOutlineShape }) {
   return (
     <g data-outline={outline.zoneId} fill="none" stroke={cssColour('--color-text')} strokeWidth={SPEC.compose.outlinePx} strokeLinejoin="round">
       {outline.polygons.map((polygon, index) => (
-        <polygon key={index} points={polygon.map(([x, y]) => `${x},${y}`).join(' ')} />
+        <polygon key={index} points={points(polygon)} />
+      ))}
+    </g>
+  )
+}
+
+/** §7.6 compose: "Rooms outside the chosen zone dimmed", to SPEC.compose.dimmed: `bg` over their floors at the rest. */
+export function ZoneDims({ polygons }: { polygons: readonly (readonly Vec2[])[] }) {
+  return (
+    <g data-dims fill={cssColour('--color-bg')} fillOpacity={1 - SPEC.compose.dimmed}>
+      {polygons.map((polygon, index) => (
+        <polygon key={index} points={points(polygon)} />
       ))}
     </g>
   )
```

In `web/src/stage/overlays/stage-svg.tsx`:

```diff
--- a/web/src/stage/overlays/stage-svg.tsx
+++ b/web/src/stage/overlays/stage-svg.tsx
@@ -1,8 +1,11 @@
 // The stage's SVG layer, over the canvas: the lights' marks (§7.3, §9.1), the room labels (§7.6) and
-// the sun (§7.4). It depends on the pose, the lights' status, what runs and the sun, never on frames,
-// so React draws it only when one of those changes (memo). Every size and colour is SPEC's or RENDER's.
+// the sun (§7.4), and in the composer the other rooms dimmed and the chosen zone outlined over them all
+// (§7.6 compose, as Live-PutLookOn layers them). It depends on the pose, the lights' status, what runs
+// and the sun, never on frames, so React draws it only when one of those changes (memo). Every size and
+// colour is SPEC's or RENDER's.
 import { memo, useId } from 'react'
 import type { Vec2 } from '@/api/contract'
+import { cx } from '@/design/cx'
 import { LIVE_SPEC } from '@/design/live-numbers'
 import { projectPoint, type CameraPose } from '../camera'
 import { RENDER, SPEC } from '../design-numbers'
@@ -10,7 +13,15 @@ import type { StageLabel } from '../labels'
 import type { Mark } from '../marks'
 import { cssColour, cssSize } from '../palette'
 import type { SunScene } from '../sun'
-import { ZoneOutline, type ZoneOutlineShape } from './zone-outline'
+import { ZoneDims, ZoneOutline, type ZoneOutlineShape } from './zone-outline'
+
+/** §7.6 compose on the stage: the rooms outside the chosen zone, and which labels are the zone's. */
+export interface ComposeShape {
+  /** The other rooms' floors, on the stage in CSS px. */
+  dims: readonly (readonly Vec2[])[]
+  /** The keys of the labels in the chosen zone: its rooms, and itself where it's a sub-zone. */
+  chosen: ReadonlySet<string>
+}
 
 export interface StageSvgProps {
   pose: CameraPose
@@ -19,21 +30,30 @@ export interface StageSvgProps {
   labels: readonly StageLabel[] | null
   /** The sun, with its label where the stage has labels (behaviour.ts). */
   sun: SunScene | null
-  /** The zone a card is hovered over, or /live/zones/:zoneId names; null for none. */
+  /** The zone a card is hovered over, /live/zones/:zoneId names, or the composer chose; null for none. */
   outline?: ZoneOutlineShape | null
+  /** The composer's dims and chosen labels; null outside it. */
+  compose?: ComposeShape | null
 }
 
-export const StageSvg = memo(function StageSvg({ pose, marks, labels, sun, outline = null }: StageSvgProps) {
+export const StageSvg = memo(function StageSvg({ pose, marks, labels, sun, outline = null, compose = null }: StageSvgProps) {
   return (
     <svg aria-hidden="true" className="pointer-events-none absolute inset-0" width={pose.width} height={pose.height}>
       {sun !== null && <SunMark pose={pose} sun={sun} />}
-      {outline !== null && <ZoneOutline outline={outline} />}
+      {outline !== null && compose === null && <ZoneOutline outline={outline} />}
       {marks.map((mark) => (
         <MarkShape key={mark.key} mark={mark} />
       ))}
       {labels?.map((label) => (
-        <RoomLabel key={label.key} label={label} at={projectPoint(pose, label.at)} />
+        <RoomLabel
+          key={label.key}
+          label={label}
+          at={projectPoint(pose, label.at)}
+          chosen={compose === null ? null : compose.chosen.has(label.key)}
+        />
       ))}
+      {compose !== null && <ZoneDims polygons={compose.dims} />}
+      {outline !== null && compose !== null && <ZoneOutline outline={outline} />}
     </svg>
   )
 })
@@ -90,15 +110,25 @@ function MarkShape({ mark }: { mark: Mark }) {
   }
 }
 
-/** Room caps, and the look running there beneath in serif italic (§7.6, §5.2). */
-function RoomLabel({ label, at }: { label: StageLabel; at: Vec2 }) {
+/**
+ * Room caps, and the look running there beneath in serif italic (§7.6, §5.2). In the composer the chosen
+ * zone's label is all `text` and the others' all `text-3`, as Live-PutLookOn draws them; `chosen` is null
+ * outside it.
+ */
+function RoomLabel({ label, at, chosen }: { label: StageLabel; at: Vec2; chosen: boolean | null }) {
   return (
     <g>
-      <text x={at[0]} y={at[1]} textAnchor="middle" className="label-caps fill-text-3" style={{ fontSize: SPEC.label.capsPx }}>
+      <text x={at[0]} y={at[1]} textAnchor="middle" className={cx('label-caps', chosen === true ? 'fill-text' : 'fill-text-3')} style={{ fontSize: SPEC.label.capsPx }}>
         {label.name}
       </text>
       {label.look !== null && (
-        <text x={at[0]} y={at[1] + RENDER.label.lineGapPx} textAnchor="middle" className="fill-text font-serif italic" style={{ fontSize: SPEC.label.lookPx }}>
+        <text
+          x={at[0]}
+          y={at[1] + RENDER.label.lineGapPx}
+          textAnchor="middle"
+          className={cx('font-serif italic', chosen === false ? 'fill-text-3' : 'fill-text')}
+          style={{ fontSize: SPEC.label.lookPx }}
+        >
           {label.look}
         </text>
       )}
```

- [ ] **Step 9: The card and the tag**

The card's width, type and tracking are Live-PutLookOn's measurements, and the tag's are Phone-PutLookOn's:

Create `web/src/stage/overlays/preview-tag.tsx`:

```tsx
// §7.6 compose's "PREVIEW ON SCREEN" tag, which "says the lights are still running the old look": the
// desktop's card beside the chosen zone (Live-PutLookOn) and the phone's tag on its stage
// (Phone-PutLookOn), each shown while the preview stream draws the look.
import { Fragment } from 'react'
import { Icon } from '@/design/icon'
import { useElementSize, type ElementSize } from '@/lib/use-element-size'
import { besideZone, type StageBox } from '../zone-shape'

export interface PreviewWords {
  /** The look previewed, and the zone it's previewed on, by name. */
  look: string
  zone: string
  /** The looks the zone's lights still run (labels.ts's looksOn()). */
  running: readonly string[]
}

/** "<A>", "<A> and <B>": serif italic, as the render draws a look's name. */
function Looks({ names }: { names: readonly string[] }) {
  return names.map((name, index) => (
    <Fragment key={name}>
      {index === 0 ? '' : index === names.length - 1 ? ' and ' : ', '}
      <span className="font-serif text-[14px] text-text italic">{name}</span>
    </Fragment>
  ))
}

/** Live-PutLookOn's card, placed beside the zone once it's measured (F4 ruling 15). */
export function PreviewCard({ zoneBox, stage, look, zone, running }: PreviewWords & { zoneBox: StageBox; stage: ElementSize }) {
  const [ref, card] = useElementSize<HTMLDivElement>()
  const [left, top] = besideZone(zoneBox, stage, card)
  return (
    <div ref={ref} data-preview-card className="pointer-events-none absolute" style={{ left, top, visibility: card.width === 0 ? 'hidden' : undefined }}>
      <div className="flex w-59 flex-col gap-1 rounded-tile border border-text bg-bg/88 px-3 py-2.5">
        <span className="flex items-center gap-1.5 text-label font-bold tracking-[0.08em] text-text uppercase">
          <Icon name="eye" size={13} />
          Preview on screen
        </span>
        <p className="text-data leading-[1.4] text-text-2">
          {look} on {zone}.{' '}
          {running.length === 0 ? (
            'The lights are as they were.'
          ) : (
            <>
              The lights are still running <Looks names={running} />.
            </>
          )}
        </p>
      </div>
    </div>
  )
}

/** Phone-PutLookOn's tag, top left on the stage. */
export function PreviewTag() {
  return (
    <span className="pointer-events-none absolute top-1.5 left-4 inline-flex h-7 items-center gap-1.5 rounded-pill border border-text bg-bg/88 px-2.5 text-label font-bold tracking-[0.06em] text-text uppercase">
      <Icon name="eye" size={13} />
      Preview on screen · lights unchanged
    </span>
  )
}
```

- [ ] **Step 10: Put `compose` together**

In `web/src/stage/stage-view.tsx`:

```diff
--- a/web/src/stage/stage-view.tsx
+++ b/web/src/stage/stage-view.tsx
@@ -1,9 +1,9 @@
-// The stage (§7) in its `live`, `focus` and `frozen` modes: the canvas, the SVG layer over it and the HTML
-// overlays, all placed from one camera pose (camera.ts). What each mode does is decided once
+// The stage (§7) in its `live`, `compose`, `focus` and `frozen` modes: the canvas, the SVG layer over it
+// and the HTML overlays, all placed from one camera pose (camera.ts). What each mode does is decided once
 // (behaviour.ts), and the stage is two parts: the picture (the canvas and the SVG layer, greyed while
-// frozen) and the interactive layer (the pointer's tooltip and room click, the overlays, the rooms'
-// links), which only `live` has. React renders this when the data, the view or the hovered light
-// changes; frames go from the frame store to the canvas without it (§7.5).
+// frozen) and the interactive layer (the pointer's tooltip, the overlays, the rooms' links), which only
+// `live` has. A click on a room is `live`'s and `compose`'s. React renders this when the data, the view
+// or the hovered light changes; frames go from the frame store to the canvas without it (§7.5).
 import { useMemo, useState, type MouseEvent, type PointerEvent } from 'react'
 import { useNavigate } from 'react-router'
 import type { Id, Room } from '@/api/contract'
@@ -15,13 +15,14 @@ import { stageBodies } from './bodies'
 import { FIT_VIEW, fitPose, projectPoint } from './camera'
 import { SPEC } from './design-numbers'
 import { FrameWriter, sameLayout, writerEntries } from './frame-writer'
-import { stageLabels } from './labels'
+import { looksOn, stageLabels } from './labels'
 import { anchorOf, lightMarks, statusesOf } from './marks'
 import { Legend } from './overlays/legend'
 import { LightTooltip } from './overlays/light-tooltip'
 import { NoWebGL } from './overlays/no-webgl'
+import { PreviewCard, PreviewTag } from './overlays/preview-tag'
 import { RoomLinks } from './overlays/room-links'
-import { StageSvg } from './overlays/stage-svg'
+import { StageSvg, type ComposeShape } from './overlays/stage-svg'
 import { StageTools } from './overlays/stage-tools'
 import { ZoneTags } from './overlays/zone-tags'
 import { SunReadout } from './overlays/sun-readout'
@@ -36,7 +37,7 @@ import { tooltipText } from './tooltip'
 import type { StageData } from './use-stage-data'
 import { useStageView } from './view-memory'
 import { hasWebGL2 } from './webgl'
-import { zonePolygons } from './zone-shape'
+import { boxOf, zonePolygons, zoneRooms } from './zone-shape'
 
 /** §7.6 frozen: the last frame, greyed as SPEC.frozen says. */
 const GREYED = `grayscale(${SPEC.frozen.grayscale}) brightness(${SPEC.frozen.brightness})`
@@ -49,46 +50,62 @@ const FOCUS_VIGNETTE = 'radial-gradient(closest-side, transparent 60%, color-mix
 
 export type { StageVariant } from './behaviour'
 
+/** §7.6 compose: what the composer (§8.2) shows on the stage. */
+export interface StageCompose {
+  /** The zone it puts the look on: outlined, with the rooms outside it dimmed. */
+  zoneId: Id
+  /** The look chosen, which a click on a room keeps; null for none yet. */
+  lookId: Id | null
+  /** The look the preview stream draws on the zone, by name; null while it draws none. */
+  previewing: string | null
+}
+
 export interface StageViewProps {
   data: StageData
   /** The phone's stage has no labels and no overlays (§8.10). */
   variant: StageVariant
   /** Where the view is remembered (view-memory.ts). */
   route: string
-  /** Where a click on a room goes: its zone's composer (§8.1). */
+  /** Where a click on a room goes: its zone's composer (§8.1), or in the composer the room's zone (§6.3). */
   roomTo: (room: Room) => string
   /** The zone to outline: the card under the pointer, or the one /live/zones/:zoneId names (F3 decision 23). */
   outlined?: Id | null
   /** §7.6 focus: framed on this zone, the other zones' lights hidden, a soft vignette (Zone detail). */
   focus?: Id | null
+  /** §7.6 compose: the composer's zone and preview (Put a look on). */
+  compose?: StageCompose | null
 }
 
-export function StageView({ data, variant, route, roomTo, outlined = null, focus = null }: StageViewProps) {
+export function StageView({ data, variant, route, roomTo, outlined = null, focus = null, compose = null }: StageViewProps) {
   const { home, lights, states, running, zoneNames, zones, sun, frozen } = data
   const [ref, size] = useElementSize<HTMLElement>()
   const [stored, store] = useStageView(route)
   const reducedMotion = useReducedMotion()
   // The zone in focus, once the zones load. A drop keeps its frame and its lights (§7.6 frozen).
   const focusZone = focus === null ? undefined : zones.find((zone) => zone.id === focus)
-  const mode = frozen ? 'frozen' : focusZone !== undefined ? 'focus' : 'live'
+  // The composer's zone, once the zones load; a drop keeps it, greyed (§7.6 frozen).
+  const composeZone = compose === null ? undefined : zones.find((zone) => zone.id === compose.zoneId)
+  const previewing = composeZone === undefined ? null : (compose?.previewing ?? null)
+  const mode = frozen ? 'frozen' : focusZone !== undefined ? 'focus' : composeZone !== undefined ? 'compose' : 'live'
   const behaviour = stageBehaviour({ mode, variant, reducedMotion, labels: stored.labels })
   // The phone's stage has no view controls, so it shows the fitted view (§8.10).
   const view = behaviour.overlays ? stored.view : FIT_VIEW
   const [webgl] = useState(hasWebGL2)
   const [hovered, setHovered] = useState<Id | null>(null)
   const [overRoom, setOverRoom] = useState(false)
-  // Out of the interactive layer, the pointer picks nothing, and the link's return finds nothing picked.
-  if (!behaviour.interactive && (hovered !== null || overRoom)) {
-    setHovered(null)
-    setOverRoom(false)
-  }
+  // Out of the interactive layer the pointer picks no light, and with no room click no room; the link's
+  // return finds nothing picked.
+  if (!behaviour.interactive && hovered !== null) setHovered(null)
+  if (behaviour.roomClick === null && overRoom) setOverRoom(false)
   const navigate = useNavigate()
 
-  // §7.2: "fit the zone's polygon, tilt …°"; §7.6: "other zones' lights hidden".
+  // §7.2: "fit the zone's polygon, tilt …°": focus's zone, or the phone composer's (Phone-PutLookOn).
+  // §7.6 focus: "other zones' lights hidden".
+  const framedZone = focusZone ?? (behaviour.framesComposeZone ? composeZone : undefined)
   const framing = useMemo(() => {
-    const polygons = focusZone === undefined ? [] : zonePolygons(home, focusZone, lights)
+    const polygons = framedZone === undefined ? [] : zonePolygons(home, framedZone, lights)
     return polygons.length === 0 ? null : polygons.flat()
-  }, [focusZone, home, lights])
+  }, [framedZone, home, lights])
   const shown = useMemo(() => {
     if (focusZone === undefined) return lights
     const ids = new Set(focusZone.lights)
@@ -99,25 +116,42 @@ export function StageView({ data, variant, route, roomTo, outlined = null, focus
     [framing, home.outline, size, view],
   )
   const bodies = useMemo(() => stageBodies(shown), [shown])
+  // §7.6 compose: "the chosen zone renders the preview stream instead of live", while it draws a look there.
+  const previewedLights = previewing === null || composeZone === undefined ? null : composeZone.lights
+  const previewed = useMemo(() => (previewedLights === null ? null : new Set(previewedLights)), [previewedLights])
   // The engine pushes `lights` every few seconds while a look plays. The writer's arrays (and the
-  // meshes over them) are made from which bodies are drawn alone, and take each push's colours in
-  // place; the marks, from each light's status alone (I1).
-  const entries = useMemo(() => writerEntries(bodies, shown, states, home.rooms), [bodies, shown, states, home.rooms])
+  // meshes over them) are made from which bodies are drawn alone, and take each push's colours (and
+  // a preview's stream) in place; the marks, from each light's status alone (I1).
+  const entries = useMemo(() => writerEntries(bodies, shown, states, home.rooms, previewed), [bodies, shown, states, home.rooms, previewed])
   const layout = useStable(entries, sameLayout)
   const writer = useMemo(() => new FrameWriter(layout), [layout])
   const mask = useMemo(() => roomMask(home.rooms), [home.rooms])
   const statuses = useStable(useMemo(() => statusesOf(states), [states]), sameEntries)
   const marks = useMemo(() => (pose === null ? [] : lightMarks(pose, bodies, statuses)), [pose, bodies, statuses])
-  const labels = useMemo(() => (behaviour.labels ? stageLabels(home, running, lights) : null), [behaviour.labels, home, running, lights])
+  const previewedLook = useMemo(
+    () => (previewing === null || composeZone === undefined ? null : { zoneId: composeZone.id, lookName: previewing, lights: composeZone.lights }),
+    [previewing, composeZone],
+  )
+  const labels = useMemo(
+    () => (behaviour.labels ? stageLabels(home, running, lights, previewedLook) : null),
+    [behaviour.labels, home, running, lights, previewedLook],
+  )
   const sunDrawn = useMemo(() => sunScene(home, sun, behaviour.sunLabel), [home, sun, behaviour.sunLabel])
   const points = useMemo(() => (pose === null ? [] : screenPoints(pose, bodies)), [pose, bodies])
-  // §8.1 "Hover a card → its zone outlines on the stage", drawn as §7.6 compose draws its zone.
-  const outlineZone = outlined === null ? undefined : zones.find((zone) => zone.id === outlined)
+  // §7.6 compose outlines its zone; §8.1 "Hover a card → its zone outlines on the stage", drawn alike.
+  const outlineZone = composeZone ?? (outlined === null ? undefined : zones.find((zone) => zone.id === outlined))
   const outline = useMemo(() => {
     if (pose === null || outlineZone === undefined) return null
     const polygons = zonePolygons(home, outlineZone, lights).map((polygon) => polygon.map(([x, y]) => projectPoint(pose, [x, y, 0])))
     return polygons.length === 0 ? null : { zoneId: outlineZone.id, polygons }
   }, [pose, outlineZone, home, lights])
+  // §7.6 compose: "Rooms outside the chosen zone dimmed", and the zone's own labels in `text`.
+  const composeShape = useMemo((): ComposeShape | null => {
+    if (pose === null || composeZone === undefined) return null
+    const lit = zoneRooms(home, composeZone, lights)
+    const dims = home.rooms.filter((room) => !lit.has(room.id)).map((room) => room.polygon.map(([x, y]) => projectPoint(pose, [x, y, 0])))
+    return { dims, chosen: new Set([...lit, composeZone.id]) }
+  }, [pose, composeZone, home, lights])
   // State-Problems' and State-Transition's tags: desktop `live` only (F3 decision 18).
   const tagged = behaviour.overlays && behaviour.interactive
   const tags = useMemo(() => (tagged ? zoneTags(running, bodies) : []), [tagged, running, bodies])
@@ -129,12 +163,12 @@ export function StageView({ data, variant, route, roomTo, outlined = null, focus
     const room = pose === null ? null : pickRoom(home, pose, x, y)
     return { x, y, room: room?.hasLights ? room : null }
   }
-  /** The picture's pointer: the interactive layer's, so only while there is one. */
+  /** The picture's pointer, while a click on a room does something; the light under it is Live's alone. */
   const pointer = {
     onPointerMove: (event: PointerEvent<HTMLElement>) => {
       const { x, y, room } = under(event)
       // A light's tooltip is for a mouse; a touch goes to the room under it.
-      setHovered(event.pointerType === 'mouse' ? pickLight(points, x, y) : null)
+      setHovered(behaviour.interactive && event.pointerType === 'mouse' ? pickLight(points, x, y) : null)
       setOverRoom(room !== null)
     },
     onPointerLeave: () => {
@@ -143,13 +177,16 @@ export function StageView({ data, variant, route, roomTo, outlined = null, focus
     },
     onClick: (event: MouseEvent<HTMLElement>) => {
       const { room } = under(event)
-      if (room !== null) navigate(roomTo(room))
+      if (room !== null) navigate(roomTo(room), { replace: behaviour.roomClick === 'choose' })
     },
   }
 
   const light = hovered === null ? undefined : lights.find((candidate) => candidate.id === hovered)
   const body = bodies.find((candidate) => candidate.lightId === hovered)
   const state = hovered === null ? undefined : states.get(hovered)
+  const previewWords =
+    previewing === null || composeZone === undefined ? null : { look: previewing, zone: composeZone.name, running: looksOn(composeZone, running) }
+  const zoneBox = outline === null ? null : boxOf(outline.polygons)
 
   return (
     <section ref={ref} aria-label={STAGE_LABEL} className="relative size-full overflow-hidden bg-bg">
@@ -158,7 +195,7 @@ export function StageView({ data, variant, route, roomTo, outlined = null, focus
         <div
           className="absolute inset-0"
           style={{ filter: behaviour.greyed ? GREYED : undefined, cursor: overRoom ? 'pointer' : undefined }}
-          {...(behaviour.interactive ? pointer : {})}
+          {...(behaviour.roomClick !== null ? pointer : {})}
         >
           {pose !== null && (
             <>
@@ -170,8 +207,8 @@ export function StageView({ data, variant, route, roomTo, outlined = null, focus
                 pose={pose}
                 cadenceMs={behaviour.cadenceMs}
               />
-              <StageSvg pose={pose} marks={marks} labels={labels} sun={sunDrawn} outline={outline} />
-              {framing !== null && (
+              <StageSvg pose={pose} marks={marks} labels={labels} sun={sunDrawn} outline={outline} compose={composeShape} />
+              {focusZone !== undefined && framing !== null && (
                 <div aria-hidden="true" data-vignette className="pointer-events-none absolute inset-0" style={{ background: FOCUS_VIGNETTE }} />
               )}
             </>
@@ -180,6 +217,11 @@ export function StageView({ data, variant, route, roomTo, outlined = null, focus
       ) : (
         <NoWebGL />
       )}
+      {webgl && behaviour.legend && <Legend />}
+      {webgl && previewWords !== null && behaviour.previewTag === 'card' && zoneBox !== null && (
+        <PreviewCard {...previewWords} zoneBox={zoneBox} stage={size} />
+      )}
+      {webgl && previewWords !== null && behaviour.previewTag === 'tag' && <PreviewTag />}
       {/* The interactive layer: §7.6 `live` only. */}
       {behaviour.interactive && (
         <>
@@ -192,7 +234,6 @@ export function StageView({ data, variant, route, roomTo, outlined = null, focus
                 onLabels={(on) => store({ ...stored, labels: on })}
               />
               <SunReadout sun={sun} />
-              <Legend />
               <ViewControls view={view} onView={(next) => store({ ...stored, view: next })} />
             </>
           )}
```

In `web/src/stage/stage.tsx`:

```diff
--- a/web/src/stage/stage.tsx
+++ b/web/src/stage/stage.tsx
@@ -4,11 +4,15 @@
 import type { Id, Room } from '@/api/contract'
 import { StagePending } from './stage-pending'
 import type { StageVariant } from './behaviour'
-import { StageView } from './stage-view'
+import { StageView, type StageCompose } from './stage-view'
 import { useStageData } from './use-stage-data'
 
-/** "Click a room → /live/put?zone=<room>" (§8.1): a room's zone has the room's id. */
-const composerFor = (room: Room) => `/live/put?zone=${encodeURIComponent(room.id)}`
+/**
+ * "Click a room → /live/put?zone=<room>" (§8.1): a room's zone has the room's id. In the composer the
+ * room becomes its zone, and the look stays chosen.
+ */
+const composerFor = (room: Room, lookId: Id | null = null) =>
+  `/live/put?zone=${encodeURIComponent(room.id)}${lookId === null ? '' : `&look=${encodeURIComponent(lookId)}`}`
 
 export interface StageProps {
   variant: StageVariant
@@ -16,10 +20,13 @@ export interface StageProps {
   outlined?: Id | null
   /** §7.6 focus: the zone the stage frames (Zone detail). */
   focus?: Id | null
+  /** §7.6 compose: the composer's zone and preview (Put a look on). */
+  compose?: StageCompose | null
 }
 
-export default function Stage({ variant, outlined = null, focus = null }: StageProps) {
+export default function Stage({ variant, outlined = null, focus = null, compose = null }: StageProps) {
   const data = useStageData()
   if (data === null) return <StagePending />
-  return <StageView data={data} variant={variant} route="live" roomTo={composerFor} outlined={outlined} focus={focus} />
+  const roomTo = compose === null ? composerFor : (room: Room) => composerFor(room, compose.lookId)
+  return <StageView data={data} variant={variant} route="live" roomTo={roomTo} outlined={outlined} focus={focus} compose={compose} />
 }
```

- [ ] **Step 11: Run them to see them pass**

Run: `(cd web && npx vitest run src/stage/behaviour.test.ts src/stage/frame-writer.test.ts src/stage/labels.test.ts src/stage/zone-shape.test.ts src/stage/stage-view.test.tsx)`
Expected: PASS (55 tests).

- [ ] **Step 12: Run the gate**

```bash
(cd web && npm test 2>&1 | tail -4 && npm run lint && npx tsc -b && echo "tsc ok")
```

Expected: 773 tests in 96 files; lint is clean, and "tsc ok".

- [ ] **Step 13: Commit**

```bash
git add web/src/stage
git commit -m "feat(web): the stage's compose mode: the zone outlined, the rest dimmed, the preview on its lights"
```

---

### Task 6: `LookThumb`, `LookTile` and the phone's look row

The pieces that show a look in the composer:
- `LookTile` (§6.4) on desktop, with its PREVIEWING and RUNNING HERE tags, its input icons, and the first input it would wait for in signal.
- The phone's look row (Phone-PutLookOn), its chosen row framed with a check.
- `LookThumb` in both: the scene's plain tile until F5 draws each look's motif (F4 ruling 7).

**Files:**
- Create: `web/src/looks/look-thumb.tsx`, `web/src/compose/look-tile.tsx`, `web/src/compose/look-row.tsx`
- Modify: `web/src/compose/model.ts` (`lookLabel()`, `rowNote()`), `web/src/live/nothing-running.tsx` (its comment)
- Test: `web/src/looks/look-thumb.test.tsx`, `web/src/compose/look-tile.test.tsx`, `web/src/compose/model.test.ts`

**Interfaces:**
- Consumes:
  - `LIVE_RENDER.lookThumb`, `LIVE_SPEC.lookTile` and `LIVE_SPEC.phoneComposer.thumb` (Task 2);
  - `queries.looks()`; `chipsFor(look, waiting)` (`zones/zone-view.ts`);
  - `CATEGORIES`, `MISSING_SIGNAL` and `type MissingInput` (Task 4).
- Produces:
  - `src/looks/look-thumb.tsx`: `type ThumbSize = 'tile' | 'row'`, `interface LookThumbProps {lookId, size, className?, children?}` and `LookThumb`. It's `aria-hidden`, with `data-thumb` holding the look's `thumbnail`.
  - `src/compose/look-tile.tsx`: `interface LookTileProps {look, selected, here, missing, tabbable, onSelect}` and `LookTile`, a button with `aria-pressed` and `data-look`.
  - `src/compose/look-row.tsx`: `LookRow`, which takes the same props.
  - `src/compose/model.ts`: `lookLabel(look, here, missing)`, the name a screen reader hears, and `rowNote(look, selected, here, missing) -> {text, signal}`, a row's line.

- [ ] **Step 1: Read the spec and the renders**

Read §6.4 (`LookThumb` and `LookTile`), §8.2's sentence on a missing input, §8.10's look rows, and §14's contrast. Then read the render markup:
- In `Live-PutLookOn.html`, the tiles: the thumb, the PREVIEWING and RUNNING HERE tags, the input icons, and a tile's signal line.
- In `Phone-PutLookOn.html`, the look rows and the chosen one's check.
- Look at `Live-PutLookOn.png` and `Phone-PutLookOn.png` once each.

- [ ] **Step 2: Write the failing tests**

Create `web/src/looks/look-thumb.test.tsx`:

```tsx
import { QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { queryClient } from '@/api/queries'
import { LIVE_RENDER, LIVE_SPEC } from '@/design/live-numbers'
import { seedRest } from '@/test/rest'
import { LookThumb } from './look-thumb'

describe('LookThumb (§6.4)', () => {
  // F4 ruling 7: the scene with no motif until F5 ports them, keyed by the look's thumbnail.
  it("draws a look's scene, keyed by its thumbnail, at 16:10 in a tile and at the row's size in a row", () => {
    const { looks } = seedRest('hero')
    const look = looks.find((each) => each.id === 'embers')!
    render(
      <QueryClientProvider client={queryClient}>
        <LookThumb lookId={look.id} size="tile" />
        <LookThumb lookId={look.id} size="row" />
      </QueryClientProvider>,
    )
    const [tile, row] = document.querySelectorAll<HTMLElement>('[data-thumb]')
    expect(tile).toHaveAttribute('data-thumb', look.thumbnail)
    expect(tile).toHaveAttribute('aria-hidden', 'true')
    expect(tile).toHaveStyle({ background: LIVE_RENDER.lookThumb.background })
    expect(tile.style.aspectRatio).toBe(`${LIVE_RENDER.lookThumb.width} / ${LIVE_RENDER.lookThumb.height}`)
    expect(row).toHaveStyle({ width: `${LIVE_SPEC.phoneComposer.thumb.width}px`, height: `${LIVE_SPEC.phoneComposer.thumb.height}px` })
  })
})
```

Create `web/src/compose/look-tile.test.tsx`:

```tsx
import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { lookFixtures, lookName } from '@/api/mocks/fixtures'
import { queryClient } from '@/api/queries'
import { LIVE_SPEC } from '@/design/live-numbers'
import { seedRest } from '@/test/rest'
import { LookRow } from './look-row'
import { LookTile, type LookTileProps } from './look-tile'

const inQuery = (ui: ReactNode) => render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>)

/** A tile's props for a look: not chosen, not running, waiting for nothing. */
function props(id: string, overrides: Partial<LookTileProps> = {}): LookTileProps {
  const look = lookFixtures.find((each) => each.id === id)!
  return { look, selected: false, here: false, missing: [], tabbable: false, onSelect: () => {}, ...overrides }
}

// The thumbs read the looks from REST's cache.
beforeEach(() => {
  seedRest('hero')
})

describe('LookTile (§6.4)', () => {
  // Live-PutLookOn's chosen tile.
  it('says PREVIEWING on the look the stage previews, framed in text', () => {
    inQuery(<LookTile {...props('embers', { selected: true, tabbable: true })} />)
    const tile = screen.getByRole('button', { name: lookName('embers') })
    expect(tile).toHaveAttribute('aria-pressed', 'true')
    expect(tile).toHaveAttribute('tabindex', '0')
    expect(within(tile).getByText('Previewing')).toHaveClass('bg-text')
    expect(tile.querySelector('[data-thumb]')).toHaveClass('border-text')
    expect(within(tile).getByText(lookName('embers'))).toHaveStyle({ fontSize: `${LIVE_SPEC.lookTile.namePx}px` })
  })

  // Live-PutLookOn's tile for the look the room runs.
  it('says RUNNING HERE on the look the zone runs', () => {
    inQuery(<LookTile {...props('fireflies', { here: true })} />)
    const tile = screen.getByRole('button', { name: `${lookName('fireflies')}, running here` })
    expect(tile).toHaveAttribute('aria-pressed', 'false')
    expect(tile).toHaveAttribute('tabindex', '-1')
    expect(within(tile).getByText('Running here')).toBeInTheDocument()
    expect(tile.querySelector('[data-thumb]')).toHaveClass('border-line')
  })

  // §8.2: "A look whose input is missing stays selectable; its tile says 'Waits for music' … in signal".
  it('says the input a look would wait for in signal, and still selects', async () => {
    const onSelect = vi.fn()
    inQuery(<LookTile {...props('spectrum', { missing: ['music'], onSelect })} />)
    const tile = screen.getByRole('button', { name: `${lookName('spectrum')}, Waits for music` })
    expect(within(tile).getByText('Waits for music')).toHaveClass('text-signal')
    await userEvent.click(tile)
    expect(onSelect).toHaveBeenCalledOnce()
  })
})

describe('LookRow (§8.10)', () => {
  // Phone-PutLookOn's first three rows.
  it('frames the chosen row with a check, and says what each row is', () => {
    inQuery(
      <>
        <LookRow {...props('embers', { selected: true })} />
        <LookRow {...props('fireflies', { here: true })} />
        <LookRow {...props('aurora')} />
      </>,
    )
    const chosen = screen.getByRole('button', { name: lookName('embers') })
    expect(chosen).toHaveClass('border-text')
    // F4 ruling 19: on the chosen row's control fill the line is text-2, for §14's contrast.
    expect(within(chosen).getByText('Previewing on screen')).toHaveClass('text-text-2')
    expect(chosen.querySelectorAll('svg')).toHaveLength(1)
    const here = screen.getByRole('button', { name: `${lookName('fireflies')}, running here` })
    expect(within(here).getByText('Running here now')).toBeInTheDocument()
    expect(here.querySelectorAll('svg')).toHaveLength(0)
    expect(within(screen.getByRole('button', { name: lookName('aurora') })).getByText('Ambient · no input')).toHaveClass('text-text-3')
  })
})
```

In `web/src/compose/model.test.ts`:

```diff
--- a/web/src/compose/model.test.ts
+++ b/web/src/compose/model.test.ts
@@ -6,10 +6,12 @@ import { HERO_NOW } from '@/test/live'
 import {
   CATEGORIES,
   chosenZone,
+  lookLabel,
   looksShown,
   lookTransition,
   missingInputs,
   openingCategory,
+  rowNote,
   runningOn,
   transitionChoices,
   transitionKey,
@@ -112,6 +114,23 @@ describe('the looks the composer shows', () => {
   })
 })
 
+describe("a look's words in the composer", () => {
+  // Phone-PutLookOn's rows: "Previewing on screen", "Running here now", "Ambient · no input".
+  it("say what a phone row's line says", () => {
+    expect(rowNote(look('embers'), true, false, [])).toEqual({ text: 'Previewing on screen', signal: false })
+    expect(rowNote(look('fireflies'), false, true, [])).toEqual({ text: 'Running here now', signal: false })
+    expect(rowNote(look('aurora'), false, false, [])).toEqual({ text: 'Ambient · no input', signal: false })
+    expect(rowNote(look('spectrum'), false, false, []).text).toMatch(/^Audio · Music/)
+  })
+
+  // §8.2: "its tile says 'Waits for music' / 'Needs Home Assistant' in signal", chosen or not.
+  it('say the input a look would wait for first, in signal', () => {
+    expect(rowNote(look('spectrum'), true, false, ['music'])).toEqual({ text: 'Waits for music', signal: true })
+    expect(lookLabel(look('goodnight'), false, ['home-assistant'])).toBe(`${look('goodnight').name}, Needs Home Assistant`)
+    expect(lookLabel(look('fireflies'), true, [])).toBe(`${look('fireflies').name}, running here`)
+  })
+})
+
 describe('the transitions', () => {
   it('are a cut and each kind at 1, 3 and 5 s, said as the cards say them', () => {
     const choices = transitionChoices(look('embers'))
```

- [ ] **Step 3: Run them to see them fail**

Run: `(cd web && npx vitest run src/looks src/compose/look-tile.test.tsx src/compose/model.test.ts)`
Expected: FAIL. The two new suites can't resolve their modules, and `model.test.ts` reports `2 failed | 16 passed (18)`: `rowNote is not a function`.

- [ ] **Step 4: A look's words**

In `web/src/compose/model.ts`:

```diff
--- a/web/src/compose/model.ts
+++ b/web/src/compose/model.ts
@@ -4,7 +4,7 @@
 // scenario. The words are the spec's and the renders' (Live-PutLookOn, Phone-PutLookOn).
 import type { Id, InputKind, Inputs, Look, RunningZone, Transition, Zone } from '@/api/contract'
 import { newestFirst } from '@/stage/show'
-import { transitionLabel } from '@/zones/zone-view'
+import { chipsFor, transitionLabel } from '@/zones/zone-view'
 
 /** §8.2's category chips: Starred, then the looks' own categories. */
 export type Category = 'starred' | Look['category']
@@ -81,6 +81,27 @@ export function missingInputs(look: Look, inputs: Pick<Inputs, 'music' | 'homeAs
   return missing
 }
 
+/**
+ * A tile's or a row's name for a screen reader: the look, and what its tags and signal say (its
+ * PREVIEWING tag is its aria-pressed).
+ */
+export function lookLabel(look: Look, here: boolean, missing: readonly MissingInput[]): string {
+  return [look.name, ...(here ? ['running here'] : []), ...(missing.length > 0 ? [MISSING_SIGNAL[missing[0]]] : [])].join(', ')
+}
+
+/**
+ * A phone look row's line (Phone-PutLookOn): the input it would wait for, in signal (§8.2), else
+ * "Previewing on screen", "Running here now", or its category and the inputs it uses.
+ */
+export function rowNote(look: Look, selected: boolean, here: boolean, missing: readonly MissingInput[]): { text: string; signal: boolean } {
+  if (missing.length > 0) return { text: MISSING_SIGNAL[missing[0]], signal: true }
+  if (selected) return { text: 'Previewing on screen', signal: false }
+  if (here) return { text: 'Running here now', signal: false }
+  const category = CATEGORIES.find((each) => each.id === look.category)?.label ?? look.category
+  const inputs = chipsFor(look).map((chip) => chip.label)
+  return { text: `${category} · ${inputs.length === 0 ? 'no input' : inputs.join(' · ')}`, signal: false }
+}
+
 /** The tiles a category shows, or a search's over every look (F4 ruling 10), in the server's order. */
 export function looksShown(looks: readonly Look[], category: Category, query: string): Look[] {
   const words = query.trim().toLowerCase()
```

- [ ] **Step 5: `LookThumb`**

Create `web/src/looks/look-thumb.tsx`:

```tsx
// §6.4 LookThumb, a look's motion portrait: a 16:10 scene keyed by looks.json's `thumbnail`. F5 ports the
// 29 motifs from reference/Looks.html; until then a thumb is the scene with no motif on it, the ground
// every render draws one on (F4 ruling 7), so F5 swaps the motif in without touching a caller. It takes
// §6.4's `live` with the motifs, which are what moves.
import { useQuery } from '@tanstack/react-query'
import type { CSSProperties, ReactNode } from 'react'
import type { Id } from '@/api/contract'
import { queries } from '@/api/queries'
import { cx } from '@/design/cx'
import { LIVE_RENDER, LIVE_SPEC } from '@/design/live-numbers'

/** The composer's tile (§6.4 LookTile: its width, at 16:10) or the phone's look row (§8.10). */
export type ThumbSize = 'tile' | 'row'

const { width, height, background } = LIVE_RENDER.lookThumb
const BOX: Record<ThumbSize, { className: string; style: CSSProperties }> = {
  tile: { className: 'w-full rounded-tile border', style: { aspectRatio: `${width} / ${height}` } },
  row: { className: 'shrink-0 rounded-control', style: { ...LIVE_SPEC.phoneComposer.thumb } },
}

export interface LookThumbProps {
  lookId: Id
  size: ThumbSize
  /** The frame's border, which a tile's state sets. */
  className?: string
  /** What's drawn over the scene: a tile's tag. */
  children?: ReactNode
}

export function LookThumb({ lookId, size, className, children }: LookThumbProps) {
  const thumbnail = useQuery(queries.looks()).data?.find((look) => look.id === lookId)?.thumbnail
  const box = BOX[size]
  return (
    <span
      aria-hidden="true"
      data-thumb={thumbnail}
      className={cx('relative block overflow-hidden', box.className, className)}
      style={{ ...box.style, background }}
    >
      {children}
    </span>
  )
}
```

- [ ] **Step 6: The tile and the row**

The tile's tags and signal line are Live-PutLookOn's sizes, and the row's name and line are Phone-PutLookOn's:

Create `web/src/compose/look-tile.tsx`:

```tsx
// §6.4 LookTile (composer, LIVE_SPEC.lookTile.px wide): the look's thumb, its name in serif and the
// icons of the inputs it uses; PREVIEWING while the stage previews it, RUNNING HERE while it runs on the
// chosen zone, and the first input it would wait for in signal (§8.2). Live-PutLookOn draws it.
import type { Look } from '@/api/contract'
import { cx } from '@/design/cx'
import { Icon } from '@/design/icon'
import { LIVE_SPEC } from '@/design/live-numbers'
import { LookThumb } from '@/looks/look-thumb'
import { chipsFor } from '@/zones/zone-view'
import { lookLabel, MISSING_SIGNAL, type MissingInput } from './model'

export interface LookTileProps {
  look: Look
  /** The look the stage previews: aria-pressed. */
  selected: boolean
  /** The look the chosen zone runs now. */
  here: boolean
  /** The inputs it would wait for (missingInputs()). */
  missing: readonly MissingInput[]
  /** The list's one tab stop (F4 ruling 12). */
  tabbable: boolean
  onSelect: () => void
}

const TAG = 'absolute top-2 left-2 inline-flex h-5 items-center gap-1.25 rounded-pill px-1.75 text-[10.5px] font-bold tracking-[0.06em] uppercase'

export function LookTile({ look, selected, here, missing, tabbable, onSelect }: LookTileProps) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      aria-label={lookLabel(look, here, missing)}
      data-look={look.id}
      tabIndex={tabbable ? 0 : -1}
      className="flex min-w-0 flex-col gap-2 text-left"
      onClick={onSelect}
    >
      <LookThumb lookId={look.id} size="tile" className={selected ? 'border-[1.5px] border-text' : 'border-line'}>
        {selected ? (
          <span className={cx(TAG, 'bg-text text-on-text')}>
            <Icon name="eye" size={12} />
            Previewing
          </span>
        ) : (
          here && <span className={cx(TAG, 'border border-line bg-bg/80 text-text-2')}>Running here</span>
        )}
      </LookThumb>
      <span className="flex items-center justify-between gap-1.5 px-0.5">
        <span className="font-serif leading-[1.1] text-text" style={{ fontSize: LIVE_SPEC.lookTile.namePx }}>
          {look.name}
        </span>
        <span className="inline-flex gap-1">
          {chipsFor(look, missing).map((chip) => (
            <Icon key={chip.kind} name={chip.icon} size={13} className={chip.waiting ? 'text-signal' : 'text-text-3'} />
          ))}
        </span>
      </span>
      {missing.length > 0 && <span className="px-0.5 text-[11.5px] text-signal">{MISSING_SIGNAL[missing[0]]}</span>}
    </button>
  )
}
```

Create `web/src/compose/look-row.tsx`:

```tsx
// §8.10 Put a look on's look rows (Phone-PutLookOn): the thumb at LIVE_SPEC.phoneComposer.thumb, the
// name in serif, and one line (rowNote()); the chosen row framed in `text` with a check. On the chosen
// row's control fill the line is text-2, not the render's text-3, for §14's contrast (F4 ruling 19).
import { cx } from '@/design/cx'
import { Icon } from '@/design/icon'
import { LookThumb } from '@/looks/look-thumb'
import type { LookTileProps } from './look-tile'
import { lookLabel, rowNote } from './model'

export function LookRow({ look, selected, here, missing, tabbable, onSelect }: LookTileProps) {
  const note = rowNote(look, selected, here, missing)
  return (
    <button
      type="button"
      aria-pressed={selected}
      aria-label={lookLabel(look, here, missing)}
      data-look={look.id}
      tabIndex={tabbable ? 0 : -1}
      className={cx('flex w-full items-center gap-3 rounded-card border p-2 text-left', selected ? 'border-text bg-control' : 'border-transparent')}
      onClick={onSelect}
    >
      <LookThumb lookId={look.id} size="row" />
      <span className="flex min-w-0 grow flex-col gap-0.5">
        <span className="font-serif text-[21px] leading-[1.1] text-text">{look.name}</span>
        <span className={cx('text-[11.5px]', note.signal ? 'text-signal' : selected ? 'text-text-2' : 'text-text-3')}>{note.text}</span>
      </span>
      {selected && <Icon name="check" size={18} className="shrink-0 text-text" />}
    </button>
  )
}
```

Start again keeps its own plain tile until F5 (F3 decision 27), so `NothingRunning` changes only its comment:

In `web/src/live/nothing-running.tsx`:

```diff
--- a/web/src/live/nothing-running.tsx
+++ b/web/src/live/nothing-running.tsx
@@ -1,6 +1,6 @@
 // §9.4 Nothing running (State-Nothing-Running): the lights as they were, and "Start again", recent looks
 // with one-tap play (`GET /api/running/recent`, newest stop first: F3 decision 35). The thumbnail is a
-// plain tile until F4 ports LookThumb (F3 decision 27).
+// plain tile until F5 ports LookThumb's motifs (F3 decision 27, F4 ruling 7).
 import { useQuery } from '@tanstack/react-query'
 import { failureText, startAgain } from '@/api/actions'
 import type { RecentLook } from '@/api/contract'
```

- [ ] **Step 7: Run them to see them pass**

Run: `(cd web && npx vitest run src/looks src/compose/look-tile.test.tsx src/compose/model.test.ts)`
Expected: PASS (23 tests).

- [ ] **Step 8: Run the gate**

```bash
(cd web && npm test 2>&1 | tail -4 && npm run lint && npx tsc -b && echo "tsc ok")
```

Expected: 780 tests in 98 files; lint is clean, and "tsc ok".

- [ ] **Step 9: Commit**

```bash
git add web/src/looks web/src/compose web/src/live/nothing-running.tsx
git commit -m "feat(web): LookThumb, LookTile and the phone's look row"
```

---

### Task 7: `ZonePicker`

§6.3's `ZonePicker` covers both sizes:
- Desktop: chips that wrap along the top of the stage.
- Phone: `LIVE_SPEC.phoneComposer.zonePx` buttons in a row that scrolls sideways.

Every zone shows in the server's order, with what runs there (F4 rulings 4 and 5). The chosen chip is inverted. A home look leaves only the whole home to choose. "Pick lights…" is drawn and does nothing (ruling 6). The notes on a `control` fill are `text-2` (ruling 19).

**Files:**
- Create: `web/src/compose/zone-picker.tsx`
- Test: `web/src/compose/zone-picker.test.tsx`

**Interfaces:**
- Consumes:
  - `runningOn()` and `zoneNote()` (Task 4);
  - `LIVE_SPEC.phoneComposer.zonePx` and `LIVE_RENDER.selectedZoneNote` (Task 2).
- Produces: `interface ZonePickerProps {zones, running, selected, locked, onSelect, variant}` and `ZonePicker`. It's a group labelled "Where" with one `aria-pressed` button per zone, then "Pick lights…" (`aria-disabled`).

- [ ] **Step 1: Read the spec and the renders**

Read §6.3 (`ZonePicker`), §8.2's Where, §8.10's Put a look on row and §14's contrast. Then read the render markup:
- In `Live-PutLookOn.html`, the zone chips, with the chosen one (`aria-pressed="true"`) and the dashed "Pick lights…".
- In `Phone-PutLookOn.html`, the zone buttons and their row.
- Look at `Live-PutLookOn.png` and `Phone-PutLookOn.png` once each.

- [ ] **Step 2: Write the failing tests**

Create `web/src/compose/zone-picker.test.tsx`:

```tsx
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, onTestFinished, vi } from 'vitest'
import type { Id } from '@/api/contract'
import { lookName } from '@/api/mocks/fixtures'
import { buildScenario } from '@/api/mocks/scenarios'
import { LIVE_RENDER, LIVE_SPEC } from '@/design/live-numbers'
import { HERO_NOW } from '@/test/live'
import { ZonePicker, type ZonePickerProps } from './zone-picker'

const hero = buildScenario('hero', HERO_NOW)
const name = (id: Id) => hero.zones.find((zone) => zone.id === id)!.name

function pick(overrides: Partial<ZonePickerProps> = {}) {
  const onSelect = vi.fn()
  const props: ZonePickerProps = { zones: hero.zones, running: hero.running, selected: 'living', locked: false, onSelect, variant: 'desktop', ...overrides }
  const { rerender } = render(<ZonePicker {...props} />)
  const group = screen.getByRole('group', { name: 'Where' })
  // A chip's name is the zone's and the note's: it starts with the zone's name.
  const chip = (id: Id) => within(group).getAllByRole('button').find((button) => button.firstChild?.textContent === name(id))!
  /** The zone chosen changes, as the composer's URL changes it. */
  const choose = (selected: Id) => rerender(<ZonePicker {...props} selected={selected} />)
  return { onSelect, group, chip, choose }
}

describe('ZonePicker (§6.3)', () => {
  // Live-PutLookOn's Where: the chosen chip inverted, each chip with what runs there.
  it("has a chip for every zone in the server's order, the chosen one inverted, each saying what runs there", () => {
    const { group, chip } = pick()
    const zones = within(group)
      .getAllByRole('button')
      .filter((button) => button.getAttribute('aria-disabled') !== 'true')
    expect(zones.map((button) => button.getAttribute('aria-pressed'))).toEqual(hero.zones.map((zone) => String(zone.id === 'living')))
    expect(chip('living')).toHaveClass('bg-text')
    expect(within(chip('living')).getByText(lookName('fireflies'))).toHaveStyle({ color: LIVE_RENDER.selectedZoneNote.chip })
    // F4 ruling 19: text-2 on the control fill, where the render's text-3 falls short of §14's contrast.
    expect(within(chip('home')).getByText(lookName('homesunset'))).toHaveClass('text-text-2')
    expect(within(chip('office')).getByText(lookName('comets'))).toBeInTheDocument()
    expect(within(chip('counter')).getByText('no lights')).toBeInTheDocument()
  })

  it('chooses a zone', async () => {
    const { onSelect, chip } = pick()
    await userEvent.click(chip('kitchen'))
    expect(onSelect).toHaveBeenCalledWith('kitchen')
  })

  // §8.2: "Home looks (whole-home scope) lock the zone to Whole home."
  it('leaves only the whole home to choose while a home look is chosen', () => {
    const { chip } = pick({ selected: 'home', locked: true })
    expect(chip('home')).toBeEnabled()
    for (const zone of hero.zones.filter((each) => each.kind !== 'home')) expect(chip(zone.id)).toBeDisabled()
  })

  // F4 ruling 6: picking lights has no milestone yet.
  it('draws Pick lights… dashed, and it does nothing', async () => {
    const { onSelect, group } = pick()
    const pickLights = within(group).getByRole('button', { name: 'Pick lights…' })
    expect(pickLights).toHaveAttribute('aria-disabled', 'true')
    expect(pickLights).toHaveClass('border-dashed')
    await userEvent.click(pickLights)
    expect(onSelect).not.toHaveBeenCalled()
  })

  // Phone-PutLookOn's Where: tall buttons in a row that scrolls. The chosen one leads the row as the
  // composer opens, as drawn; a later choice scrolls only as far as it must.
  it("draws the phone's buttons at LIVE_SPEC.phoneComposer.zonePx and keeps the chosen one in view", () => {
    const scrolled: [Element, ScrollIntoViewOptions | boolean | undefined][] = []
    const original = Element.prototype.scrollIntoView
    Element.prototype.scrollIntoView = function (this: Element, options?: ScrollIntoViewOptions | boolean) {
      scrolled.push([this, options])
    }
    onTestFinished(() => void (Element.prototype.scrollIntoView = original))
    const { chip, choose } = pick({ variant: 'phone', selected: 'bedroom' })
    expect(chip('bedroom')).toHaveStyle({ height: `${LIVE_SPEC.phoneComposer.zonePx}px` })
    expect(within(chip('bedroom')).getByText(lookName('homesunset'))).toHaveStyle({ color: LIVE_RENDER.selectedZoneNote.button })
    expect(scrolled).toEqual([[chip('bedroom'), { block: 'nearest', inline: 'start' }]])
    choose('kitchen')
    expect(scrolled.slice(1)).toEqual([[chip('kitchen'), { block: 'nearest', inline: 'nearest' }]])
  })
})
```

- [ ] **Step 3: Run them to see them fail**

Run: `(cd web && npx vitest run src/compose/zone-picker.test.tsx)`
Expected: FAIL. `./zone-picker` doesn't resolve, and Vitest finds no tests.

- [ ] **Step 4: Write the picker**

The desktop chip's sizes are Live-PutLookOn's, and the phone button's are Phone-PutLookOn's, its height `LIVE_SPEC.phoneComposer.zonePx`. The phone's row snaps (`snap-x snap-proximity`, and `snap-start` on each button). Without the snap, the row stopped wherever `scrollIntoView` left it as the fonts and the notes landed, and Task 10's screenshots flaked (Task 11 adds this to CLAUDE.md's gotchas):

Create `web/src/compose/zone-picker.tsx`:

```tsx
// §6.3 ZonePicker: "chips for Whole home, each room with lights, each sub-zone …, saved custom groups,
// and a dashed 'Pick lights…' chip. Each chip shows what's running there in small text; the selected chip
// is inverted." The zones come in the server's order (F4 ruling 5) with F4 ruling 4's notes. The desktop's
// chips wrap along the top of the stage (§8.2 Where; Live-PutLookOn); the phone's are
// LIVE_SPEC.phoneComposer.zonePx buttons in a row that scrolls (§8.10; Phone-PutLookOn), where the chosen
// one leads the row as the composer opens, as drawn, and a later choice scrolls only as far as it must.
// A note on a chip that isn't chosen is text-2, not the renders' text-3, which on the control fill falls
// short of §14's contrast (F4 ruling 19). Picking lights has no milestone yet, so its chip is drawn but
// can't be used (F4 ruling 6).
import { useEffect, useId, useRef } from 'react'
import type { Id, RunningZone, Zone } from '@/api/contract'
import { cx } from '@/design/cx'
import { Icon } from '@/design/icon'
import { LIVE_RENDER, LIVE_SPEC } from '@/design/live-numbers'
import { runningOn, zoneNote } from './model'

export interface ZonePickerProps {
  zones: readonly Zone[]
  running: readonly RunningZone[]
  /** The chosen zone. */
  selected: Id
  /** §8.2: "Home looks (whole-home scope) lock the zone to Whole home": the others can't be chosen. */
  locked: boolean
  onSelect: (zoneId: Id) => void
  variant: 'desktop' | 'phone'
}

export function ZonePicker({ zones, running, selected, locked, onSelect, variant }: ZonePickerProps) {
  const label = useId()
  const chosen = useRef<HTMLButtonElement>(null)
  const opened = useRef(false)
  const phone = variant === 'phone'
  useEffect(() => {
    if (!phone) return
    chosen.current?.scrollIntoView?.({ block: 'nearest', inline: opened.current ? 'nearest' : 'start' })
    opened.current = true
  }, [phone, selected])

  const chips = zones.map((zone) => {
    const on = zone.id === selected
    const note = zoneNote(zone, runningOn(zone, running, zones))
    const tone = on ? 'border-text bg-text text-on-text' : 'border-line bg-control text-text'
    const noteColour = on ? { color: phone ? LIVE_RENDER.selectedZoneNote.button : LIVE_RENDER.selectedZoneNote.chip } : undefined
    return (
      <button
        key={zone.id}
        ref={on ? chosen : undefined}
        type="button"
        aria-pressed={on}
        disabled={locked && zone.kind !== 'home'}
        className={cx(
          'border disabled:opacity-45',
          phone
            ? 'flex shrink-0 snap-start flex-col items-start justify-center gap-0.5 rounded-card px-3.5'
            : 'inline-flex h-8 items-center gap-1.75 rounded-pill px-3 text-size-control font-semibold',
          tone,
        )}
        style={phone ? { height: LIVE_SPEC.phoneComposer.zonePx } : undefined}
        onClick={() => onSelect(zone.id)}
      >
        {phone ? <span className="text-body font-semibold whitespace-nowrap">{zone.name}</span> : zone.name}
        <span className={cx(phone ? 'text-label whitespace-nowrap' : 'text-[11.5px] font-medium', !on && 'text-text-2')} style={noteColour}>
          {note}
        </span>
      </button>
    )
  })
  const pickLights = (
    <button
      type="button"
      aria-disabled="true"
      className={cx(
        'inline-flex shrink-0 items-center gap-1.5 border border-dashed border-line-strong font-semibold text-text-2',
        phone ? 'snap-start rounded-card px-3.5 text-body' : 'h-8 rounded-pill px-3 text-size-control',
      )}
      style={phone ? { height: LIVE_SPEC.phoneComposer.zonePx } : undefined}
    >
      <Icon name="plus" size={14} />
      Pick lights…
    </button>
  )

  if (phone) {
    return (
      <div className="flex flex-col gap-2">
        <span id={label} className="label-caps text-text-3">
          Where
        </span>
        <div role="group" aria-labelledby={label} className="flex snap-x snap-proximity gap-2 overflow-x-auto">
          {chips}
          {pickLights}
        </div>
      </div>
    )
  }
  return (
    <div role="group" aria-labelledby={label} className="flex flex-wrap items-center gap-2">
      <span id={label} className="mr-1 text-meta text-text-3">
        Where
      </span>
      {chips}
      {pickLights}
    </div>
  )
}
```

- [ ] **Step 5: Run them to see them pass**

Run: `(cd web && npx vitest run src/compose/zone-picker.test.tsx)`
Expected: PASS (5 tests).

- [ ] **Step 6: Run the gate**

```bash
(cd web && npm test 2>&1 | tail -4 && npm run lint && npx tsc -b && echo "tsc ok")
```

Expected: 785 tests in 99 files; lint is clean, and "tsc ok".

- [ ] **Step 7: Commit**

```bash
git add web/src/compose/zone-picker.tsx web/src/compose/zone-picker.test.tsx
git commit -m "feat(web): ZonePicker, as chips on desktop and a scrolling row of buttons on the phone"
```

---

### Task 8: Put a look on, on desktop

`/live/put` becomes Live with the composer in the Running panel's place (§8.2, Live-PutLookOn):
- Where's zone chips sit along the top of the stage.
- The panel holds the search, the category chips and the grid of tiles, then the transition, the consequence line, **Cancel** and **Start**.
- Choosing a tile previews its look on the stage, in `compose` mode, at once.
- The URL holds the zone and the look (F4 ruling 9). `L` opens the composer and Esc closes it (ruling 12). Start starts the look and goes back to Live (ruling 13).

This task holds §13.1's done-when test: "starts a look in three clicks from Live, and leaves the lights alone until Start".

**Files:**
- Create: `web/src/compose/use-composer.ts`, `web/src/compose/use-composer-view.ts`, `web/src/compose/use-composer-keys.ts`
- Create: `web/src/compose/consequence-text.tsx`, `web/src/compose/composer-panel.tsx`
- Modify: `web/src/compose/model.ts` (`composerPath()`), `web/src/stage/stage.tsx` (a room's path through `composerPath()`)
- Modify: `web/src/app/routes.tsx` (`/live/put` a child of Live), `web/src/pages/live.tsx` (the composer in the panel's place)
- Modify: `web/e2e/shell.spec.ts` (the notched phone's race, from Before Task 1)
- Test: `web/src/compose/composer.test.tsx`, `web/src/compose/model.test.ts`

**Interfaces:**
- Consumes:
  - `previewSession`, `usePreview()` and `usePreviewState()`; `startLook()` and `failureText()` (Task 3);
  - the model, `consequence()`, `lastZone()` and `rememberZone()` (Task 4);
  - `StageCompose`, and `Stage`'s `compose` prop (Task 5);
  - `LookTile` (Task 6) and `ZonePicker` (Task 7);
  - F0's `Select`, `Button`, `IconButton` and `Icon`; `useAnnounce()`; `useLive()` and `useLiveBy()`;
  - in tests: `restOn()` and `startMockDataLayer()` (`test/live.ts`), `renderApp()` (`test/app.tsx`), and `loadedStage()` (`test/stage.ts`).
- Produces:
  - `model.ts`: `composerPath(zoneId, lookId = null)`, the composer's URL.
  - `use-composer.ts`:
    - `interface ComposeChoice {zones, looks, zone, look, locked, choose, pick}` and `useComposeChoice()`, which the stage needs too;
    - `useStageCompose(composing): StageCompose | null` and `useRunning()`;
    - `interface Composer extends ComposeChoice {running, preview, missing, consequence, starting, start, close}` and `useComposer()`.
  - `use-composer-view.ts`: `type LookSteps`, `interface ComposerView extends Composer` and `useComposerView(steps, list)`, what the panel and Task 9's sheet share.
  - `use-composer-keys.ts`: `useComposerKeys(composing)`.
  - `consequence-text.tsx`: `ConsequenceText({parts, lookClassName})`.
  - `composer-panel.tsx`: `ComposerWhere`, and `ComposerPanel`, an `aside` labelled "Put a look on".

- [ ] **Step 1: Read the spec and the render**

Read §4.3 (the URL), §8.2 whole (Where, What, How and the keyboard), §11.3, §13.1's M4 row, and §14's "composer flow" and keyboard path. Then read `Live-PutLookOn.html`'s markup:
- the panel's header, the search, the category chips and the grid;
- the footer: the transition, the consequence line, Cancel and Start;
- where the zone chips sit over the stage.

Look at `Live-PutLookOn.png` once.

- [ ] **Step 2: Write the failing tests**

The composer's tests run on Vitest's fake timers, as F3's page tests do, so the mock's socket and the beat clock move only when `settle()` moves them. Three things about them:
- `userEvent` hangs under fake timers: Testing Library's `asyncWrapper` waits on a `setTimeout(0)` that never fires. So the tests drive the page with `fireEvent`. Task 11 adds this to CLAUDE.md's gotchas.
- Base UI's Select picks an option as the pointer comes up, so `press()` sends the whole sequence a mouse sends.
- `restOn(server)` answers the REST calls from the same mock server the socket plays, so a start changes what the socket sends next.

Create `web/src/compose/composer.test.tsx`:

```tsx
import { act, fireEvent, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Id } from '@/api/contract'
import { previewSession } from '@/api/live'
import { lookName } from '@/api/mocks/fixtures'
import type { MockServer } from '@/api/mocks/mock-server'
import { api, ApiError } from '@/api/rest'
import { renderApp } from '@/test/app'
import { HERO_NOW, restOn, startMockDataLayer } from '@/test/live'
import { resizeObserved } from '@/test/resize'
import { loadedStage, MAIN_STAGE } from '@/test/stage'

// jsdom has no WebGL: src/test/stage.ts's stand-in takes the canvas's place, and the rest of the stage is real.
vi.mock('@/stage/webgl', () => import('@/test/stage').then((stage) => stage.webglMock()))
vi.mock('@/stage/stage-canvas', (importOriginal) => import('@/test/stage').then((stage) => stage.canvasMock(importOriginal)))

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(HERO_NOW)
  // The last zone used is this browser's (F4 ruling 9): each test starts without one.
  localStorage.clear()
})

/** Time for the in-memory socket and the stubbed fetch, which answer in microtasks between the timers. */
const settle = (ms = 1000) => act(() => vi.advanceTimersByTimeAsync(ms))

/** The app at `path` on the hero's mock server, REST and socket alike, settled. */
async function openApp(path: string) {
  const server = startMockDataLayer()
  restOn(server)
  const router = renderApp(path)
  await settle()
  return { server, router }
}

const composer = () => screen.getByRole('complementary', { name: 'Put a look on' })
const title = () => within(composer()).getByRole('heading', { level: 2 })
const tile = (id: Id) => composer().querySelector<HTMLElement>(`[data-look="${id}"]`)!
const tilesShown = () => [...composer().querySelectorAll<HTMLElement>('[data-look]')].map((each) => each.dataset.look)
const consequenceLine = () => composer().querySelector('[data-consequence]')!
const startButton = (look?: Id) => within(composer()).getByRole('button', { name: look === undefined ? 'Start' : `Start ${lookName(look)}` })
const zoneName = (server: MockServer, id: Id) => server.state.zones.find((zone) => zone.id === id)!.name
/** A mouse press as a browser sends one: Base UI's list picks an option as the button comes up. */
function press(element: HTMLElement) {
  fireEvent.pointerDown(element, { pointerType: 'mouse', button: 0 })
  fireEvent.mouseDown(element, { button: 0 })
  fireEvent.pointerUp(element, { pointerType: 'mouse', button: 0 })
  fireEvent.mouseUp(element, { button: 0 })
  fireEvent.click(element, { button: 0 })
}
/** A zone's chip in Where, by the zone's name (a chip's name runs on into its note). */
const chip = (name: string) =>
  within(screen.getByRole('group', { name: 'Where' }))
    .getAllByRole('button')
    .find((button) => button.firstChild?.textContent === name)!

describe('Put a look on (§8.2)', () => {
  // §13.1 F4's exit check: "Start a look in ≤ 3 clicks from Live; lights unchanged until Start (mock asserts)".
  it('starts a look in three clicks from Live, and leaves the lights alone until Start', async () => {
    const { server, router } = await openApp('/next/live')
    const running = structuredClone(server.state.running)
    const lights = structuredClone(server.state.lights)
    const home = server.state.zones.find((zone) => zone.kind === 'home')!
    // The whole home runs a home look, so the composer opens on the home looks (F4 ruling 10).
    const look = server.state.looks.find((each) => each.category === 'home' && each.id !== 'homesunset')!

    fireEvent.click(screen.getByRole('link', { name: 'Put a look on' }))
    await settle()
    expect(router.state.location.pathname).toBe('/next/live/put')
    expect(screen.queryByRole('complementary', { name: 'Running' })).not.toBeInTheDocument()
    expect(title()).toHaveTextContent(`Put a look on ${home.name}`)

    fireEvent.click(tile(look.id))
    await settle()
    expect(previewSession.snapshot()).toMatchObject({ status: 'on', zoneId: home.id, lookId: look.id })
    expect(server.state.running).toEqual(running)
    expect(server.state.lights).toEqual(lights)

    fireEvent.click(startButton(look.id))
    await settle()
    expect(server.state.running.find((zone) => zone.zoneId === home.id)?.lookId).toBe(look.id)
    expect(router.state.location.pathname).toBe('/next/live')
    expect(screen.getByRole('status')).toHaveTextContent(`Started ${look.name} on ${home.name}.`)
    expect(previewSession.snapshot().status).toBe('idle')
  })

  // §4.3: the zone and the look are the URL's, changed in place, so Back leaves the composer whole.
  it('keeps the zone and the look in its URL, previews the look on the stage, and says what Start would do', async () => {
    const { server, router } = await openApp('/next/live/put?zone=living')
    await loadedStage()
    act(() => resizeObserved(MAIN_STAGE.width, MAIN_STAGE.height))
    const living = zoneName(server, 'living')
    expect(title()).toHaveTextContent(`Put a look on ${living}`)
    expect(document.querySelector('[data-outline]')).toHaveAttribute('data-outline', 'living')

    fireEvent.click(tile('embers'))
    await settle()
    expect(router.state.location.search).toBe('?zone=living&look=embers')
    expect(router.state.historyAction).toBe('REPLACE')
    expect(tile('embers')).toHaveAttribute('aria-pressed', 'true')
    expect(document.querySelector('[data-preview-card]')).toHaveTextContent(`${lookName('embers')} on ${living}.`)
    expect(consequenceLine()).toHaveTextContent(new RegExp(`^Takes over the ${living} from ${lookName('fireflies')}\\. `))
    expect(startButton('embers')).toBeEnabled()

    // A room's chip chooses its zone, keeping the look.
    const kitchen = zoneName(server, 'kitchen')
    fireEvent.click(chip(kitchen))
    await settle()
    expect(router.state.location.search).toBe('?zone=kitchen&look=embers')
    expect(router.state.historyAction).toBe('REPLACE')
    expect(title()).toHaveTextContent(`Put a look on ${kitchen}`)
    expect(consequenceLine()).toHaveTextContent(new RegExp(`^Takes over the ${kitchen} from ${lookName('homesunset')}\\.`))

    // Start remembers the zone: the composer opens on it next time.
    fireEvent.click(startButton('embers'))
    await settle()
    expect(router.state.location.pathname).toBe('/next/live')
    fireEvent.click(screen.getByRole('link', { name: 'Put a look on' }))
    await settle()
    expect(title()).toHaveTextContent(`Put a look on ${kitchen}`)
  })

  it('holds Start until a look is chosen, and on a zone with no lights', async () => {
    const ask = vi.spyOn(api, 'startPreview')
    const { server, router } = await openApp('/next/live/put?zone=living')
    expect(consequenceLine()).toHaveTextContent('Choose a look to see it on the stage first.')
    expect(startButton()).toBeDisabled()

    await act(() => router.navigate('/live/put?zone=counter&look=embers', { replace: true }))
    await settle()
    expect(consequenceLine()).toHaveTextContent(`The ${zoneName(server, 'counter')} has no lights.`)
    expect(startButton('embers')).toBeDisabled()
    expect(ask).not.toHaveBeenCalled()
  })

  // §8.2: "Home looks (whole-home scope) lock the zone to Whole home."
  it('locks the zone to the whole home for a home look', async () => {
    const { server } = await openApp('/next/live/put?zone=living&look=goodnight')
    const home = server.state.zones.find((zone) => zone.kind === 'home')!
    expect(title()).toHaveTextContent(`Put a look on ${home.name}`)
    expect(chip(home.name)).toBeEnabled()
    expect(chip(zoneName(server, 'living'))).toBeDisabled()
    expect(previewSession.snapshot()).toMatchObject({ zoneId: home.id, lookId: 'goodnight' })
  })

  // F4 ruling 10: a search spans every category; a category's chip clears it.
  it('searches every category, and a category clears the search', async () => {
    const { server } = await openApp('/next/live/put?zone=living&look=embers')
    const categories = screen.getByRole('group', { name: 'Categories' })
    expect(within(categories).getByRole('button', { name: 'Ambient' })).toHaveAttribute('aria-pressed', 'true')
    const search = within(composer()).getByRole('searchbox', { name: 'Search looks' })
    expect(search).toHaveAttribute('placeholder', `Search ${server.state.looks.length} looks`)

    fireEvent.change(search, { target: { value: lookName('comets') } })
    expect(tilesShown()).toEqual(['comets'])
    expect(within(categories).queryByRole('button', { pressed: true })).not.toBeInTheDocument()
    fireEvent.change(search, { target: { value: 'zzzz' } })
    expect(composer()).toHaveTextContent('No looks match “zzzz”.')
    // Esc clears a search first, and the composer stays.
    fireEvent.keyDown(search, { key: 'Escape' })
    expect(search).toHaveValue('')
    expect(composer()).toBeInTheDocument()

    fireEvent.change(search, { target: { value: 'zzzz' } })
    fireEvent.click(within(categories).getByRole('button', { name: 'Tempo' }))
    expect(search).toHaveValue('')
    expect(tilesShown()).toEqual(server.state.looks.filter((each) => each.category === 'tempo').map((each) => each.id))
    fireEvent.click(within(categories).getByRole('button', { name: 'Starred' }))
    expect(composer()).toHaveTextContent('No starred looks yet.')
  })

  // F4 ruling 12.
  it('opens on L, chooses on the arrows, starts on Enter and closes on Esc', async () => {
    const { server, router } = await openApp('/next/live')
    // Not while typing, and not with a modifier: Ctrl+L is the browser's.
    const typing = document.body.appendChild(document.createElement('input'))
    fireEvent.keyDown(typing, { key: 'l' })
    fireEvent.keyDown(document.body, { key: 'l', ctrlKey: true })
    typing.remove()
    expect(router.state.location.pathname).toBe('/next/live')

    fireEvent.keyDown(document.body, { key: 'l' })
    await settle()
    expect(router.state.location.pathname).toBe('/next/live/put')
    // The focus is on the first look; the grid has two looks a row.
    const shown = tilesShown()
    expect(document.activeElement).toBe(tile(shown[0]!))
    fireEvent.keyDown(document.activeElement!, { key: 'ArrowRight' })
    expect(router.state.location.search).toBe(`?look=${shown[1]}`)
    expect(document.activeElement).toBe(tile(shown[1]!))
    fireEvent.keyDown(document.activeElement!, { key: 'ArrowDown' })
    expect(document.activeElement).toBe(tile(shown[3]!))
    fireEvent.keyDown(document.activeElement!, { key: 'ArrowUp' })
    expect(router.state.location.search).toBe(`?look=${shown[1]}`)
    await settle()

    fireEvent.keyDown(document.activeElement!, { key: 'Enter' })
    await settle()
    expect(router.state.location.pathname).toBe('/next/live')
    const home = server.state.zones.find((zone) => zone.kind === 'home')!
    expect(server.state.running.find((zone) => zone.zoneId === home.id)?.lookId).toBe(shown[1])

    // Esc closes it from anywhere on the page: Where's chips sit on the stage, outside the panel.
    fireEvent.keyDown(document.body, { key: 'l' })
    await settle()
    fireEvent.keyDown(chip(home.name), { key: 'Escape' })
    await settle()
    expect(router.state.location.pathname).toBe('/next/live')
  })

  it('says why Start failed, and stays open', async () => {
    vi.spyOn(api, 'start').mockRejectedValue(new ApiError(503, 'The engine is busy', '/api/zones/living/start'))
    const { router } = await openApp('/next/live/put?zone=living&look=embers')
    fireEvent.click(startButton('embers'))
    await settle()
    expect(screen.getByRole('status')).toHaveTextContent(`Couldn't start ${lookName('embers')}. The engine is busy`)
    expect(router.state.location.pathname).toBe('/next/live/put')
    expect(startButton('embers')).toBeEnabled()
  })

  // F4 ruling 3: the engine refuses a whole-home look until M6 (the mock plays one, so a refusal stands in).
  it('says why the preview was refused, and leaves Start to try', async () => {
    vi.spyOn(api, 'startPreview').mockRejectedValue(new ApiError(400, 'Home looks (whole-home scope) arrive in M6', '/api/preview'))
    await openApp('/next/live/put?look=goodnight')
    expect(consequenceLine()).toHaveTextContent(`Couldn't preview ${lookName('goodnight')}. Home looks (whole-home scope) arrive in M6`)
    expect(startButton('goodnight')).toBeEnabled()
  })

  // F4 ruling 11: the look's own transition unless another is chosen, and it's sent with Start.
  it('starts with the transition chosen', async () => {
    const start = vi.spyOn(api, 'start')
    await openApp('/next/live/put?zone=living&look=embers')
    const transition = within(composer()).getByRole('combobox', { name: 'Transition' })
    expect(transition).toHaveTextContent('Cut')
    fireEvent.click(transition)
    await settle(100)
    press(screen.getByRole('option', { name: 'Fade · 3 s' }))
    await settle(100)
    expect(transition).toHaveTextContent('Fade · 3 s')
    fireEvent.click(startButton('embers'))
    await settle()
    expect(start).toHaveBeenCalledWith('living', { lookId: 'embers', transition: { kind: 'fade', durationS: 3 } })
  })

  // Review focus 3: Back leaves the composer as Cancel does, and the preview ends with it.
  it('ends the preview when Back leaves', async () => {
    const stop = vi.spyOn(api, 'stopPreview')
    const { router } = await openApp('/next/live')
    await act(() => router.navigate('/live/put?zone=living&look=embers'))
    await settle()
    expect(previewSession.snapshot()).toMatchObject({ status: 'on', zoneId: 'living', lookId: 'embers' })
    await act(() => router.navigate(-1))
    await settle()
    expect(router.state.location.pathname).toBe('/next/live')
    expect(stop).toHaveBeenCalledTimes(1)
    expect(previewSession.snapshot().status).toBe('idle')
  })

  // Review focus 5: the transition's list opens outside the panel; an Esc there closes the list alone.
  it('closes only the transition list on an Esc in it', async () => {
    const { router } = await openApp('/next/live/put?zone=living&look=embers')
    const transition = within(composer()).getByRole('combobox', { name: 'Transition' })
    fireEvent.click(transition)
    await settle(100)
    expect(screen.getByRole('listbox')).toContainElement(document.activeElement as HTMLElement)
    fireEvent.keyDown(document.activeElement!, { key: 'Escape' })
    await settle(100)
    expect(screen.queryByRole('listbox')).not.toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/next/live/put')

    fireEvent.keyDown(transition, { key: 'Escape' })
    await settle()
    expect(router.state.location.pathname).toBe('/next/live')
  })
})
```

In `web/src/compose/model.test.ts`:

```diff
--- a/web/src/compose/model.test.ts
+++ b/web/src/compose/model.test.ts
@@ -6,6 +6,7 @@ import { HERO_NOW } from '@/test/live'
 import {
   CATEGORIES,
   chosenZone,
+  composerPath,
   lookLabel,
   looksShown,
   lookTransition,
@@ -22,6 +23,15 @@ const hero = buildScenario('hero', HERO_NOW)
 const zone = (id: string) => hero.zones.find((candidate) => candidate.id === id)!
 const look = (id: string) => hero.looks.find((candidate) => candidate.id === id)!
 
+describe("the composer's URL", () => {
+  it('names the zone and the look chosen, each only when there is one', () => {
+    expect(composerPath(null)).toBe('/live/put')
+    expect(composerPath('living')).toBe('/live/put?zone=living')
+    expect(composerPath('living', 'embers')).toBe('/live/put?zone=living&look=embers')
+    expect(composerPath(null, 'embers')).toBe('/live/put?look=embers')
+  })
+})
+
 describe('the zone the composer puts a look on', () => {
   it("is the URL's, else the last one used, else the whole home", () => {
     expect(chosenZone(hero.zones, 'kitchen', 'living', look('embers'))?.id).toBe('kitchen')
```

- [ ] **Step 3: Run them to see them fail**

Run: `(cd web && npx vitest run src/compose/composer.test.tsx src/compose/model.test.ts)`
Expected: FAIL: `12 failed | 18 passed (30)`.
- `/live/put` still draws F0's placeholder, so all 11 composer tests fail to find the "Put a look on" panel (or its Categories group).
- `model.test.ts`'s new test fails with `composerPath is not a function`.

- [ ] **Step 4: The composer's URL**

In `web/src/compose/model.ts`:

```diff
--- a/web/src/compose/model.ts
+++ b/web/src/compose/model.ts
@@ -6,6 +6,15 @@ import type { Id, InputKind, Inputs, Look, RunningZone, Transition, Zone } from
 import { newestFirst } from '@/stage/show'
 import { chipsFor, transitionLabel } from '@/zones/zone-view'
 
+/** The composer's URL (spec §4.3, F4 ruling 9): /live/put, with ?zone= and ?look= as chosen. */
+export function composerPath(zoneId: Id | null, lookId: Id | null = null): string {
+  const params = new URLSearchParams()
+  if (zoneId !== null) params.set('zone', zoneId)
+  if (lookId !== null) params.set('look', lookId)
+  const query = params.toString()
+  return query === '' ? '/live/put' : `/live/put?${query}`
+}
+
 /** §8.2's category chips: Starred, then the looks' own categories. */
 export type Category = 'starred' | Look['category']
 
```

A room clicked on the stage builds its path the same way:

In `web/src/stage/stage.tsx`:

```diff
--- a/web/src/stage/stage.tsx
+++ b/web/src/stage/stage.tsx
@@ -2,6 +2,7 @@
 // three.js and React Three Fiber arrive in a chunk of their own (§14: the first load's budget
 // excludes three.js).
 import type { Id, Room } from '@/api/contract'
+import { composerPath } from '@/compose/model'
 import { StagePending } from './stage-pending'
 import type { StageVariant } from './behaviour'
 import { StageView, type StageCompose } from './stage-view'
@@ -11,8 +12,7 @@ import { useStageData } from './use-stage-data'
  * "Click a room → /live/put?zone=<room>" (§8.1): a room's zone has the room's id. In the composer the
  * room becomes its zone, and the look stays chosen.
  */
-const composerFor = (room: Room, lookId: Id | null = null) =>
-  `/live/put?zone=${encodeURIComponent(room.id)}${lookId === null ? '' : `&look=${encodeURIComponent(lookId)}`}`
+const composerFor = (room: Room, lookId: Id | null = null) => composerPath(room.id, lookId)
 
 export interface StageProps {
   variant: StageVariant
```

- [ ] **Step 5: The composer's state**

`useComposeChoice()` reads the zone and the look from the URL and changes them in place (ruling 9). `useComposer()` holds the preview only while the zone has lights, works out the consequence (ruling 14), and starts the look (ruling 13):

Create `web/src/compose/use-composer.ts`:

```ts
// The composer's state (§8.2, F4 rulings 9–13). The zone and the look are the URL's (?zone=, ?look=,
// spec §4.3), changed in place, so Back leaves the composer whole; the zone falls back to the last one
// used, then the whole home, and a home look locks it to the whole home. useComposeChoice() is what the
// stage needs too; useComposer() is the panel's and the phone's sheet's, and holds the preview while
// either is mounted. Start, Cancel and Close go back to Live, which ends the preview.
import { useQuery } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { failureText, startLook } from '@/api/actions'
import type { Id, Inputs, Light, Look, RunningZone, Transition, Zone } from '@/api/contract'
import { useLive, useLiveBy } from '@/api/live-store'
import type { PreviewState } from '@/api/preview'
import { queries } from '@/api/queries'
import { usePreview, usePreviewState } from '@/api/use-preview'
import { useAnnounce } from '@/design/announce'
import type { StageCompose } from '@/stage/stage-view'
import { consequence, type Consequence } from './consequence'
import { lastZone, rememberZone } from './last-zone'
import { chosenZone, composerPath, locksToHome, missingInputs, type MissingInput } from './model'

export interface ComposeChoice {
  zones: readonly Zone[] | undefined
  looks: readonly Look[] | undefined
  /** The zone the look goes on: undefined until the zones load. */
  zone: Zone | undefined
  look: Look | undefined
  /** A home look is chosen, so the zone is the whole home. */
  locked: boolean
  /** Chooses a zone, keeping the look. */
  choose: (zoneId: Id) => void
  /** Chooses a look, keeping the zone asked for. */
  pick: (lookId: Id) => void
}

export function useComposeChoice(): ComposeChoice {
  const zones = useQuery(queries.zones()).data
  const looks = useQuery(queries.looks()).data
  const [params] = useSearchParams()
  const navigate = useNavigate()
  const [remembered] = useState(lastZone)
  const asked = params.get('zone')
  const lookId = params.get('look')
  const look = lookId === null ? undefined : looks?.find((each) => each.id === lookId)
  const zone = zones === undefined ? undefined : chosenZone(zones, asked, remembered, look)
  return {
    zones,
    looks,
    zone,
    look,
    locked: locksToHome(look),
    choose: (zoneId) => navigate(composerPath(zoneId, lookId), { replace: true }),
    pick: (next) => navigate(composerPath(asked, next), { replace: true }),
  }
}

/** The look the preview stream draws on the composer's zone, by name: what the stage says it previews. */
function previewing(preview: PreviewState, zone: Zone, looks: readonly Look[] | undefined): string | null {
  if (preview.showing !== zone.id) return null
  return looks?.find((look) => look.id === preview.lookId)?.name ?? null
}

/** What the stage shows of the composer (§7.6 compose), while it's open. */
export function useStageCompose(composing: boolean): StageCompose | null {
  const { zone, look, looks } = useComposeChoice()
  const preview = usePreviewState()
  if (!composing || zone === undefined) return null
  return { zoneId: zone.id, lookId: look?.id ?? null, previewing: previewing(preview, zone, looks) }
}

type InputsRead = Pick<Inputs, 'music' | 'homeAssistant'> | null
/** The heartbeat sends the inputs every second as an equal copy: the same, for what the composer reads. */
const sameInputs = (a: InputsRead, b: InputsRead) => JSON.stringify(a) === JSON.stringify(b)
const NOTHING_RUNS: readonly RunningZone[] = []

/** What runs now, from the live store. */
export const useRunning = (): readonly RunningZone[] => useLive((state) => state.running?.zones ?? NOTHING_RUNS)

export interface Composer extends ComposeChoice {
  running: readonly RunningZone[]
  preview: PreviewState
  /** The inputs a look would wait for (F4 ruling 8). */
  missing: (look: Look) => MissingInput[]
  /** What Start would do (§8.2); null until the zones load. */
  consequence: Consequence | null
  /** Start is on its way. */
  starting: boolean
  /** Starts the look on the zone with `transition` (F4 ruling 13); a failure is said, and the composer stays. */
  start: (transition: Transition) => void
  /** Cancel and Close: back to Live, the lights as they were. */
  close: () => void
}

export function useComposer(): Composer {
  const choice = useComposeChoice()
  const { zone, look } = choice
  const lights = useQuery(queries.lights()).data
  const running = useRunning()
  const inputs = useLiveBy((state): InputsRead => (state.inputs === null ? null : { music: state.inputs.music, homeAssistant: state.inputs.homeAssistant }), sameInputs)
  // A zone with no lights has nothing to preview: the engine would refuse it.
  const preview = usePreview(zone !== undefined && zone.lights.length > 0 ? zone.id : null, look?.id ?? null)
  const navigate = useNavigate()
  const announce = useAnnounce()
  const [starting, setStarting] = useState(false)
  const names = useMemo(() => new Map<Id, Light>((lights ?? []).map((light) => [light.id, light])), [lights])

  const missing = (each: Look) => missingInputs(each, inputs)
  const answered = preview.zoneId === zone?.id && preview.lookId === look?.id
  const said =
    zone === undefined
      ? null
      : consequence({
          zone,
          look,
          running,
          lights: names,
          plan: answered && preview.status === 'on' ? preview.lights : null,
          missing: look === undefined ? [] : missing(look),
          refused: answered && preview.status === 'failed' && look !== undefined ? failureText(`preview ${look.name}`, preview.error) : null,
        })
  const close = () => navigate('/live', { replace: true })
  const start = (transition: Transition) => {
    if (zone === undefined || look === undefined || starting) return
    setStarting(true)
    startLook(zone.id, look.id, transition).then(
      () => {
        rememberZone(zone.id)
        announce(`Started ${look.name} on ${zone.name}.`)
        close()
      },
      (error: unknown) => {
        setStarting(false)
        announce(failureText(`start ${look.name}`, error))
      },
    )
  }
  return { ...choice, running, preview, missing, consequence: said, starting, start, close }
}
```

- [ ] **Step 6: What the panel and the sheet share**

The search, the category, the transition chosen, the arrows and Enter (rulings 10 to 12). The face passes in its list's ref, because the React Compiler's rules forbid a ref inside the object a hook returns:

Create `web/src/compose/use-composer-view.ts`:

```ts
// What the composer's two faces share (§8.2, §8.10): the desktop panel and the phone's sheet show the
// looks in the server's order (F4 ruling 18), open on the same category (ruling 10), keep a transition
// chosen for the look chosen (ruling 11) and take the same keys (ruling 12): the arrows move through the
// looks by `steps`, choosing each as they go, and Enter on the look chosen starts it. The look chosen,
// else the first, takes the focus as the composer opens. `list` is the face's element that holds the
// looks, each one `[data-look]`.
import { useEffect, useRef, useState, type KeyboardEvent, type RefObject } from 'react'
import type { Id, Look, RunningZone } from '@/api/contract'
import {
  looksShown,
  lookTransition,
  openingCategory,
  runningOn,
  transitionChoices,
  transitionKey,
  type Category,
  type TransitionChoice,
} from './model'
import { useComposer, type Composer } from './use-composer'

/** The element of look `id` among those `list` holds. */
const lookElement = (list: HTMLElement | null, id: Id) =>
  [...(list?.querySelectorAll<HTMLElement>('[data-look]') ?? [])].find((each) => each.dataset.look === id)

/** How far each arrow key moves through the looks. */
export type LookSteps = Partial<Record<string, number>>

export interface ComposerView extends Composer {
  /** What runs on the zone now (F4 ruling 4): its look is the one running here. */
  here: RunningZone | null
  category: Category
  /** Shows a category's looks, ending a search. */
  chooseCategory: (category: Category) => void
  query: string
  search: (query: string) => void
  /** A search is on: it spans every category, so no category is chosen (F4 ruling 10). */
  searching: boolean
  shown: Look[]
  transitions: TransitionChoice[]
  /** The transition chosen, by its key: the look's own until another is chosen for it. */
  transition: string
  chooseTransition: (key: string) => void
  /** Start can't go yet; the consequence line says why. */
  blocked: boolean
  /** The looks' one tab stop: the look chosen, else the first shown. */
  tabbable: Id | undefined
  onListKey: (event: KeyboardEvent<HTMLElement>) => void
  /** Starts the look chosen with the transition chosen. */
  startChosen: () => void
}

export function useComposerView(steps: LookSteps, list: RefObject<HTMLElement | null>): ComposerView {
  const composer = useComposer()
  const { zones, looks, zone, look, running, consequence: said } = composer
  const [category, setCategory] = useState<Category | null>(null)
  const [query, setQuery] = useState('')
  const [chosen, setChosen] = useState<{ lookId: Id | null; key: string } | null>(null)

  const here = zone === undefined || zones === undefined ? null : runningOn(zone, running, zones)
  const shownCategory = category ?? openingCategory(look, looks?.find((each) => each.id === here?.lookId))
  const shown = looks === undefined ? [] : looksShown(looks, shownCategory, query)
  const transitions = transitionChoices(look)
  const key = chosen !== null && chosen.lookId === (look?.id ?? null) ? chosen.key : transitionKey(lookTransition(look))
  const blocked = said?.blocked ?? true
  const tabbable = shown.find((each) => each.id === look?.id)?.id ?? shown[0]?.id
  const startChosen = () => composer.start(transitions.find((choice) => choice.key === key)?.transition ?? lookTransition(look))

  const focused = useRef(false)
  useEffect(() => {
    if (focused.current || tabbable === undefined) return
    focused.current = true
    lookElement(list.current, tabbable)?.focus()
  }, [list, tabbable])

  const onListKey = (event: KeyboardEvent<HTMLElement>) => {
    const id = event.target instanceof HTMLElement ? event.target.closest<HTMLElement>('[data-look]')?.dataset.look : undefined
    if (id === undefined) return
    if (event.key === 'Enter' && id === look?.id) {
      // Enter on another look chooses it, as a click does.
      event.preventDefault()
      if (!blocked) startChosen()
      return
    }
    const step = steps[event.key]
    if (step === undefined) return
    event.preventDefault()
    const index = shown.findIndex((each) => each.id === id)
    const next = shown[Math.min(Math.max(index + step, 0), shown.length - 1)]
    if (next === undefined || next.id === id) return
    composer.pick(next.id)
    lookElement(list.current, next.id)?.focus()
  }

  return {
    ...composer,
    here,
    category: shownCategory,
    chooseCategory: (next) => {
      setCategory(next)
      setQuery('')
    },
    query,
    search: setQuery,
    searching: query.trim() !== '',
    shown,
    transitions,
    transition: key,
    chooseTransition: (next) => setChosen({ lookId: look?.id ?? null, key: next }),
    blocked,
    tabbable,
    onListKey,
    startChosen,
  }
}
```

- [ ] **Step 7: `L` and Esc**

The page's two keys listen on `window` and leave alone a key that something took first. Base UI's dismiss handles an Esc that closes its list: it calls `preventDefault()` and `stopPropagation()` on it. The search's own Esc clears it first with `preventDefault()`. "closes only the transition list on an Esc in it" pins Base UI's side (Review Focus 5):

Create `web/src/compose/use-composer-keys.ts`:

```ts
// §8.2: "Keyboard: `L` opens the composer from Live; arrows move through tiles; Enter starts; Esc cancels."
// The page's two (F4 ruling 12): L, unless it's typed into a field or comes with Ctrl, Alt or Meta (the
// browser's), and Esc anywhere on the page while the composer is open. Whatever takes an Esc first keeps
// it: an open list or popover closes (Base UI stops the key there), and a search clears.
import { useEffect } from 'react'
import { useNavigate } from 'react-router'
import { composerPath } from './model'

const typing = (target: EventTarget | null) =>
  target instanceof HTMLElement && (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName))

/** L opens the composer while it's closed, and Esc closes it while it's open. */
export function useComposerKeys(composing: boolean): void {
  const navigate = useNavigate()
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.defaultPrevented) return
      if (composing && event.key === 'Escape') {
        event.preventDefault()
        navigate('/live', { replace: true })
      } else if (!composing && event.key.toLowerCase() === 'l' && !event.ctrlKey && !event.altKey && !event.metaKey && !typing(event.target)) {
        event.preventDefault()
        navigate(composerPath(null))
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [composing, navigate])
}
```

- [ ] **Step 8: The panel**

The consequence line's look names are serif italic, at the size each render draws them:

Create `web/src/compose/consequence-text.tsx`:

```tsx
// The consequence line's words (§8.2; consequence.ts), each look's name in serif italic as the renders
// draw it, at each one's size (Live-PutLookOn, Phone-PutLookOn), which the caller's class gives.
import type { ConsequencePart } from './consequence'

export function ConsequenceText({ parts, lookClassName }: { parts: readonly ConsequencePart[]; lookClassName: string }) {
  return parts.map((part, index) =>
    part.look === true ? (
      <span key={index} className={lookClassName}>
        {part.text}
      </span>
    ) : (
      part.text
    ),
  )
}
```

The panel's sizes are Live-PutLookOn's. The grid has two tiles a row, so Up and Down move by two (ruling 12):

Create `web/src/compose/composer-panel.tsx`:

```tsx
// §8.2 Put a look on (desktop; Live-PutLookOn): the composer takes the Running panel's place and the
// stage goes into `compose` mode. Where: the zone chips along the top of the stage (ComposerWhere). What:
// the search, the category chips and the LookTile grid, where choosing a tile previews its look on the
// stage at once. How: the transition, the consequence line, Cancel and Start <Look>. Keyboard (F4
// ruling 12): the arrows move through the tiles, previewing each, and Enter starts the look previewed;
// the page's L and Esc are useComposerKeys()'s.
import { useId, useRef, type CSSProperties } from 'react'
import { Button, IconButton } from '@/design/button'
import { cx } from '@/design/cx'
import { Icon } from '@/design/icon'
import { Select } from '@/design/select'
import { ConsequenceText } from './consequence-text'
import { LookTile } from './look-tile'
import { CATEGORIES } from './model'
import { useComposeChoice, useRunning } from './use-composer'
import { useComposerView, type LookSteps } from './use-composer-view'
import { ZonePicker } from './zone-picker'

/** Live-PutLookOn's grid: two tiles a row, so Up and Down move by two. */
const GRID_STEPS: LookSteps = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -2, ArrowDown: 2 }

/** §8.2 "Where": the zone chips along the top of the stage, under preview only's label when it shows. */
export function ComposerWhere({ style }: { style?: CSSProperties }) {
  const { zones, zone, locked, choose } = useComposeChoice()
  const running = useRunning()
  if (zones === undefined || zone === undefined) return null
  return (
    <div className="absolute top-[calc(1rem+var(--stage-top-shift,0px))] right-5 left-5 z-10" style={style}>
      <ZonePicker zones={zones} running={running} selected={zone.id} locked={locked} onSelect={choose} variant="desktop" />
    </div>
  )
}

export function ComposerPanel({ className }: { className?: string }) {
  const grid = useRef<HTMLDivElement>(null)
  const view = useComposerView(GRID_STEPS, grid)
  const { looks, zone, look, consequence: said } = view
  const searchId = useId()

  return (
    <aside aria-label="Put a look on" className={cx('flex min-h-0 flex-col border-l border-line-soft bg-panel', className)}>
      <div className="flex items-center justify-between pt-4 pr-4 pb-2.5 pl-5">
        <h2 className="text-section font-semibold">
          Put a look on{zone !== undefined && <span className="font-medium text-text-3"> {zone.name}</span>}
        </h2>
        <IconButton icon="x" label="Close" onClick={view.close} />
      </div>
      {zone !== undefined && looks !== undefined && (
        <>
          <div className="flex flex-col gap-2.5 px-5 pb-3">
            <div className="flex h-9 items-center gap-2 rounded-control border border-line bg-control px-3 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-text">
              <Icon name="search" size={15} className="text-text-3" />
              <label htmlFor={searchId} className="sr-only">
                Search looks
              </label>
              <input
                id={searchId}
                type="search"
                value={view.query}
                placeholder={`Search ${looks.length} looks`}
                className="min-w-0 grow bg-transparent text-size-control text-text outline-none placeholder:text-text-3"
                onChange={(event) => view.search(event.target.value)}
                onKeyDown={(event) => {
                  // A search's Esc clears it first, and the page's Esc leaves a key handled alone.
                  if (event.key !== 'Escape' || !view.searching) return
                  event.preventDefault()
                  view.search('')
                }}
              />
            </div>
            <div role="group" aria-label="Categories" className="flex gap-1.5 overflow-hidden">
              {CATEGORIES.map(({ id, label }) => {
                const on = !view.searching && id === view.category
                return (
                  <button
                    key={id}
                    type="button"
                    aria-pressed={on}
                    className={cx(
                      'h-7 rounded-pill border px-2.25 text-meta font-semibold whitespace-nowrap',
                      on ? 'border-text bg-control-hover text-text' : 'border-line text-text-2',
                    )}
                    onClick={() => view.chooseCategory(id)}
                  >
                    {label}
                  </button>
                )
              })}
            </div>
          </div>
          <div className="min-h-0 grow overflow-y-auto px-5 pt-1 pb-4">
            {view.shown.length === 0 ? (
              <p className="text-meta text-text-3">
                {view.searching
                  ? `No looks match “${view.query.trim()}”.`
                  : `No ${CATEGORIES.find((each) => each.id === view.category)?.label.toLowerCase()} looks yet.`}
              </p>
            ) : (
              <div ref={grid} role="group" aria-label="Looks" className="grid grid-cols-2 gap-x-3 gap-y-4" onKeyDown={view.onListKey}>
                {view.shown.map((each) => (
                  <LookTile
                    key={each.id}
                    look={each}
                    selected={each.id === look?.id}
                    here={each.id === view.here?.lookId}
                    missing={view.missing(each)}
                    tabbable={each.id === view.tabbable}
                    onSelect={() => view.pick(each.id)}
                  />
                ))}
              </div>
            )}
          </div>
          <div className="flex flex-col gap-3 border-t border-line-soft px-5 pt-3.5 pb-5">
            <div className="flex items-center justify-between gap-2.5">
              <span className="text-data text-text-2">Transition</span>
              <Select
                label="Transition"
                value={view.transition}
                items={Object.fromEntries(view.transitions.map((choice) => [choice.key, choice.label]))}
                onValueChange={view.chooseTransition}
                className="w-42.5"
              />
            </div>
            {said !== null && (
              <p data-consequence className="flex items-start gap-2 text-meta text-text-3">
                <Icon name="layers" size={15} />
                <span>
                  <ConsequenceText parts={said.parts} lookClassName="font-serif text-[14px] text-text italic" />
                </span>
              </p>
            )}
            <div className="flex gap-2.5">
              <Button size="lg" onClick={view.close}>
                Cancel
              </Button>
              <Button variant="primary" size="lg" icon="play" className="grow" disabled={view.blocked || view.starting} onClick={view.startChosen}>
                {look === undefined ? 'Start' : `Start ${look.name}`}
              </Button>
            </div>
          </div>
        </>
      )}
    </aside>
  )
}
```

- [ ] **Step 9: `/live/put` is Live, with the composer**

The route has no element of its own, as `/live/zones/:zoneId` has none, so the stage stays mounted (ruling 16):

In `web/src/app/routes.tsx`:

```diff
--- a/web/src/app/routes.tsx
+++ b/web/src/app/routes.tsx
@@ -24,6 +24,8 @@ const LIVE: PageMeta = {
 }
 /** Zone detail (Phone-Zone): the zone's name with Back to Live, and no context line or tempo strip. On desktop it's Live (F3 decision 23). */
 const ZONE: PageMeta = { title: LIVE.title, context: LIVE.context, PhoneTitle: ZoneTitle, phoneBack: '/live' }
+/** Put a look on (§8.2): Live, with the composer in the Running panel's place. */
+const PUT: PageMeta = { title: LIVE.title, context: LIVE.context }
 const LOOKS: PageMeta = { title: 'Looks' }
 const MAP: PageMeta = {
   title: 'Map',
@@ -53,8 +55,16 @@ export const routes: RouteObject[] = [
           { index: true, element: <Navigate to="/live" replace /> },
           // F3 decision 23: /live/zones/:zoneId is Live, so the stage stays mounted between them. LivePage
           // reads the id: on desktop it outlines the zone's card, and on the phone it draws Zone detail.
-          { path: 'live', handle: LIVE, element: <LivePage />, children: [{ path: 'zones/:zoneId', handle: ZONE, element: null }] },
-          { path: 'live/put', handle: LIVE, element: <Placeholder name="Put a look on" milestone="F4" /> },
+          // /live/put is Live too, with the composer, so the stage goes into `compose` mode in place (F4 ruling 16).
+          {
+            path: 'live',
+            handle: LIVE,
+            element: <LivePage />,
+            children: [
+              { path: 'zones/:zoneId', handle: ZONE, element: null },
+              { path: 'put', handle: PUT, element: null },
+            ],
+          },
           { path: 'looks', handle: LOOKS, element: <Placeholder name="Looks" milestone="F5" /> },
           { path: 'looks/:lookId', handle: LOOKS, element: <Placeholder name="Look editor" milestone="F8" /> },
           { path: 'map', handle: MAP, element: <Placeholder name="Home map" milestone="F7" /> },
```

On desktop the composer takes the Running panel's place. Between the breakpoints it lies over the stage's right side, as the panel does, and Where's chips stop short of it. The hovered card is forgotten as the composer opens, because no card stays under the pointer:

In `web/src/pages/live.tsx`:

```diff
--- a/web/src/pages/live.tsx
+++ b/web/src/pages/live.tsx
@@ -1,14 +1,18 @@
 // Live (§8.1, §8.10): the stage, and beside it the Running panel. The stage's code loads on demand,
 // keeping three.js out of the first load (§14); its place keeps the stage's background meanwhile, and
 // its REST reads start at once rather than when its code arrives. /live/zones/:zoneId is Live with that
-// zone's card outlined (F3 decision 23). Between 768 and 1199 px the panel lies over the stage's right
-// side and can hide (§4.4, F3 decision 22).
+// zone's card outlined (F3 decision 23); /live/put is Live with the composer in the panel's place and the
+// stage in `compose` mode (§8.2), which `L` opens and Esc closes. Between 768 and 1199 px the panel lies
+// over the stage's right side and can hide (§4.4, F3 decision 22); the composer lies there too.
 import { usePrefetchQuery } from '@tanstack/react-query'
 import { lazy, Suspense, useState, type CSSProperties } from 'react'
-import { useParams } from 'react-router'
+import { useMatch, useParams } from 'react-router'
 import type { Id } from '@/api/contract'
 import { queries } from '@/api/queries'
 import { usePreviewOnly } from '@/chrome/hooks'
+import { ComposerPanel, ComposerWhere } from '@/compose/composer-panel'
+import { useStageCompose } from '@/compose/use-composer'
+import { useComposerKeys } from '@/compose/use-composer-keys'
 import { Button } from '@/design/button'
 import { LIVE_SPEC } from '@/design/live-numbers'
 import { useIsPhone, useMediaQuery } from '@/lib/use-media-query'
@@ -34,6 +38,9 @@ export function LivePage() {
   usePrefetchQuery(queries.zones())
   usePrefetchQuery(queries.looks())
   const { zoneId } = useParams()
+  const composing = useMatch('/live/put') !== null
+  const compose = useStageCompose(composing)
+  useComposerKeys(composing)
   const phone = useIsPhone()
   const narrow = useMediaQuery(NARROW_QUERY)
   const previewOnly = usePreviewOnly() === true
@@ -45,9 +52,20 @@ export function LivePage() {
     setNamed(zoneId)
     if (zoneId !== undefined && panel === 'hidden') setPanel('open')
   }
+  const [wasComposing, setWasComposing] = useState(composing)
+  if (composing !== wasComposing) {
+    // The composer takes the Running panel's place, so no card stays under the pointer.
+    setWasComposing(composing)
+    setHovered(null)
+  }
   const stage = (
     <Suspense fallback={<StagePending />}>
-      <Stage variant={phone ? 'phone' : 'desktop'} outlined={phone ? null : (hovered ?? zoneId ?? null)} focus={phone ? (zoneId ?? null) : null} />
+      <Stage
+        variant={phone ? 'phone' : 'desktop'}
+        outlined={phone ? null : (hovered ?? zoneId ?? null)}
+        focus={phone ? (zoneId ?? null) : null}
+        compose={compose}
+      />
     </Suspense>
   )
   if (phone) {
@@ -67,12 +85,16 @@ export function LivePage() {
         style={previewOnly ? ({ '--stage-top-shift': `${PREVIEW_LABEL_FOOT_PX}px` } as CSSProperties) : undefined}
       >
         {stage}
+        {composing && <ComposerWhere style={narrow ? { right: 'calc(var(--live-panel-w) + 1.25rem)' } : undefined} />}
         {previewOnly && <PreviewOnlyLabel />}
         <ReconnectingCard variant="desktop" />
         <EmptyHome variant="desktop" />
       </div>
-      {!narrow && <RunningPanel selected={zoneId} className="w-(--live-panel-w) shrink-0" onZoneHover={setHovered} />}
-      {narrow && panel !== 'hidden' && (
+      {composing && (
+        <ComposerPanel className={narrow ? 'absolute inset-y-0 right-0 z-20 w-(--live-panel-w) shadow-pop' : 'w-(--live-panel-w) shrink-0'} />
+      )}
+      {!composing && !narrow && <RunningPanel selected={zoneId} className="w-(--live-panel-w) shrink-0" onZoneHover={setHovered} />}
+      {!composing && narrow && panel !== 'hidden' && (
         <RunningPanel
           selected={zoneId}
           className="absolute inset-y-0 right-0 z-20 w-(--live-panel-w) shadow-pop"
@@ -81,7 +103,7 @@ export function LivePage() {
           focusHide={panel === 'reopened'}
         />
       )}
-      {narrow && panel === 'hidden' && (
+      {!composing && narrow && panel === 'hidden' && (
         <Button icon="left" autoFocus className="absolute top-1/2 right-4 z-20 -translate-y-1/2 shadow-pop" onClick={() => setPanel('reopened')}>
           Running
         </Button>
```

- [ ] **Step 10: The notched phone's race**

Before Task 1, Step 4 describes the race: the stage's room links are a hidden `nav` one pixel outside the screen, and a notched phone's check reads it as crossing the left edge. While this plan was checked, it failed about one run in three from this task on. The check now passes over a landmark that's drawn nowhere:

In `web/e2e/shell.spec.ts`:

```diff
--- a/web/e2e/shell.spec.ts
+++ b/web/e2e/shell.spec.ts
@@ -67,6 +67,9 @@ function outsideSafeArea(page: Page, insets: Insets): Promise<string[]> {
     const crossed: string[] = []
     for (const landmark of document.querySelectorAll('nav, header, main')) {
       const box = landmark.getBoundingClientRect()
+      // A landmark hidden until it has focus (the stage's room links, sr-only) is drawn nowhere: its 1 px box
+      // sits a pixel outside its place, so once the stage has loaded it would cross the screen's left edge.
+      if (box.width <= 1 && box.height <= 1) continue
       const name = landmark.tagName.toLowerCase()
       if (box.left < insets.left) crossed.push(`${name} left`)
       if (box.top < insets.top) crossed.push(`${name} top`)
```

- [ ] **Step 11: Run them to see them pass**

Run: `(cd web && npx vitest run src/compose/composer.test.tsx src/compose/model.test.ts)`
Expected: PASS (30 tests).

- [ ] **Step 12: Run the gate**

```bash
(cd web && npm test 2>&1 | tail -4 && npm run lint && npx tsc -b && echo "tsc ok" && npm run build 2>&1 | tail -1)
for i in $(seq 1 60); do [ "$(ss -ltn | grep -cE ':(4174|4175) ')" = 0 ] && break; sleep 10; done; ss -ltn | grep -cE ':(4174|4175) '
(cd web && npm run e2e 2>&1 | tail -3)
```

Expected:
- 797 tests in 100 files; lint is clean, and "tsc ok".
- The build ends `…/web/dist: no mocks, 280.1 KB of gzipped JS`.
- The port check prints `0`.
- e2e: 90 passed and 48 skipped, as before Task 1. `shell.spec.ts`'s `/next/live/put` route now draws the composer, and axe passes on it.

- [ ] **Step 13: Commit**

```bash
git add web/src/compose web/src/stage/stage.tsx web/src/app/routes.tsx web/src/pages/live.tsx web/e2e/shell.spec.ts
git commit -m "feat(web): Put a look on, on desktop: the composer in the Running panel's place, its look on the stage"
```

---

### Task 9: Put a look on, on the phone

§8.10's Put a look on, as Phone-PutLookOn draws it:
- The composer is a sheet under the stage, which frames the zone and shows the preview with its tag (Task 5).
- The sheet holds Where's zone buttons in a row that scrolls, What's category chips and look rows (there's no search on the phone), then the short consequence beside the transition, and **Start <look> on <zone>**.
- It's a focused task: no header and no tab bar (F4 ruling 16).
- The sheet is part of the page, not a dialog. The stage above it stays live, and a room tapped there chooses its zone.

**Files:**
- Create: `web/src/compose/composer-sheet.tsx`
- Modify: `web/src/design/overlays.tsx` (`Grabber`), `web/src/app/page-meta.ts` (`focusedTask`), `web/src/app/routes.tsx` (`/live/put` a focused task)
- Modify: `web/src/shell/app-shell.tsx` (a focused task hides the phone's header and tab bar), `web/src/pages/live.tsx` (the phone's sheet)
- Modify: `web/e2e/helpers.ts` (`open()` waits for the composer's looks too)
- Test: `web/src/compose/composer.test.tsx`

**Interfaces:**
- Consumes: `useComposerView()`, `ConsequenceText` and the short consequence (Tasks 4 and 8), `LookRow` (Task 6), `ZonePicker` (Task 7), and F0's `Select`, `Button` and `Icon`.
- Produces:
  - `design/overlays.tsx`: `Grabber({className})`, which `Sheet` now draws too.
  - `app/page-meta.ts`: `PageMeta.focusedTask?: boolean`. On the phone, the shell draws a focused task with no header and no tab bar.
  - `compose/composer-sheet.tsx`: `ComposerSheet`, a `section` labelled "Put a look on", whose title is the page's `h1`.

- [ ] **Step 1: Read the spec and the render**

Read §4.2 (the phone's chrome), §8.10's Put a look on row, and its Phone-Map row's "No tab bar (a focused task)". Then read `Phone-PutLookOn.html`'s markup:
- the sheet's grabber, title and Close;
- the zone buttons, What and the category chips;
- the look rows;
- the footer: the short consequence, the transition and Start.

Look at `Phone-PutLookOn.png` once.

- [ ] **Step 2: Write the failing tests**

In `web/src/compose/composer.test.tsx`:

```diff
--- a/web/src/compose/composer.test.tsx
+++ b/web/src/compose/composer.test.tsx
@@ -9,6 +9,7 @@ import { renderApp } from '@/test/app'
 import { HERO_NOW, restOn, startMockDataLayer } from '@/test/live'
 import { resizeObserved } from '@/test/resize'
 import { loadedStage, MAIN_STAGE } from '@/test/stage'
+import { setViewportWidth } from '@/test/viewport'
 
 // jsdom has no WebGL: src/test/stage.ts's stand-in takes the canvas's place, and the rest of the stage is real.
 vi.mock('@/stage/webgl', () => import('@/test/stage').then((stage) => stage.webglMock()))
@@ -273,3 +274,50 @@ describe('Put a look on (§8.2)', () => {
     expect(router.state.location.pathname).toBe('/next/live')
   })
 })
+
+describe('Put a look on, on the phone (§8.10)', () => {
+  beforeEach(() => {
+    setViewportWidth(390)
+  })
+
+  const sheet = () => screen.getByRole('region', { name: 'Put a look on' })
+  const row = (id: Id) => sheet().querySelector<HTMLElement>(`[data-look="${id}"]`)!
+  const rowsShown = () => [...sheet().querySelectorAll<HTMLElement>('[data-look]')].map((each) => each.dataset.look)
+
+  // Phone-PutLookOn: a sheet under the stage, with no header or tab bar; Start names the look and the zone.
+  it('puts the composer in a sheet under the stage, and starts the look there', async () => {
+    const { server, router } = await openApp('/next/live/put?zone=living&look=embers')
+    const living = zoneName(server, 'living')
+    expect(screen.queryByRole('banner')).not.toBeInTheDocument()
+    expect(screen.queryByRole('navigation', { name: 'Main' })).not.toBeInTheDocument()
+    expect(within(sheet()).getByRole('heading', { level: 1 })).toHaveTextContent('Put a look on')
+    expect(within(sheet()).getByRole('group', { name: 'Where' })).toBeInTheDocument()
+    expect(rowsShown()).toEqual(server.state.looks.filter((each) => each.category === 'ambient').map((each) => each.id))
+    expect(row('embers')).toHaveAttribute('aria-pressed', 'true')
+    expect(sheet().querySelector('[data-consequence]')).toHaveTextContent(`Takes over from ${lookName('fireflies')}`)
+
+    fireEvent.click(within(sheet()).getByRole('button', { name: `Start ${lookName('embers')} on ${living}` }))
+    await settle()
+    expect(router.state.location.pathname).toBe('/next/live')
+    expect(server.state.running.find((zone) => zone.zoneId === 'living')?.lookId).toBe('embers')
+    expect(screen.getByRole('banner')).toBeInTheDocument()
+    expect(screen.getByRole('navigation', { name: 'Main' })).toBeInTheDocument()
+  })
+
+  // F4 ruling 12: one look a row, so Up and Down move by one.
+  it('moves through the looks a row at a time, and closes', async () => {
+    const { router } = await openApp('/next/live/put?zone=living&look=embers')
+    const shown = rowsShown()
+    const next = shown[shown.indexOf('embers') + 1]!
+    expect(document.activeElement).toBe(row('embers'))
+    fireEvent.keyDown(document.activeElement!, { key: 'ArrowDown' })
+    expect(router.state.location.search).toBe(`?zone=living&look=${next}`)
+    expect(document.activeElement).toBe(row(next))
+    fireEvent.keyDown(document.activeElement!, { key: 'ArrowUp' })
+    expect(router.state.location.search).toBe('?zone=living&look=embers')
+
+    fireEvent.click(within(sheet()).getByRole('button', { name: 'Close' }))
+    await settle()
+    expect(router.state.location.pathname).toBe('/next/live')
+  })
+})
```

- [ ] **Step 3: Run them to see them fail**

Run: `(cd web && npx vitest run src/compose/composer.test.tsx)`
Expected: FAIL: `2 failed | 11 passed (13)`. The phone's `/live/put` still draws the header, the tab bar and the Running sheet. The first test finds the header, and the second finds no "Put a look on" region.

- [ ] **Step 4: The grabber, shared**

The composer's sheet draws `Sheet`'s grabber, so it moves into a component of its own:

In `web/src/design/overlays.tsx`:

```diff
--- a/web/src/design/overlays.tsx
+++ b/web/src/design/overlays.tsx
@@ -3,6 +3,7 @@ import { Popover as BasePopover } from '@base-ui/react/popover'
 import { Tooltip as BaseTooltip } from '@base-ui/react/tooltip'
 import type { ReactElement, ReactNode } from 'react'
 import { IconButton } from './button'
+import { cx } from './cx'
 import { Icon } from './icon'
 
 interface OverlayProps {
@@ -112,6 +113,11 @@ export function Dialog({ title, children, ...modal }: OverlayProps) {
   )
 }
 
+/** §6.1 Sheet's grabber, which the phone's composer sheet draws too (Phone-PutLookOn). */
+export function Grabber({ className }: { className?: string }) {
+  return <span aria-hidden="true" className={cx('mx-auto h-1.25 w-10 shrink-0 rounded-[3px] bg-line-strong', className)} />
+}
+
 /**
  * §6.1 Sheet: the phone's bottom sheet, with a grabber, its title (Phone-State-Problems: `aside` beside
  * it, the count) and a Close at the row's end, bare as Phone-State-Problems and Phone-PutLookOn draw it:
@@ -123,7 +129,7 @@ export function Sheet({ title, aside, children, ...modal }: OverlayProps & { asi
       {...modal}
       className="fixed inset-x-0 bottom-0 z-50 flex max-h-[85dvh] flex-col gap-1 overflow-y-auto rounded-t-sheet border-t border-line bg-panel px-4 pt-2 pb-[max(1rem,env(safe-area-inset-bottom))] shadow-sheet outline-none"
     >
-      <span aria-hidden="true" className="mx-auto mb-1.5 h-1.25 w-10 shrink-0 rounded-[3px] bg-line-strong" />
+      <Grabber className="mb-1.5" />
       <div className="flex items-center justify-between gap-2">
         <div className="flex items-baseline gap-1">
           <BaseDialog.Title className="text-title font-semibold text-text">{title}</BaseDialog.Title>
```

- [ ] **Step 5: A focused task**

`/live/put` is one on the phone (ruling 16). The desktop shell is unchanged:

In `web/src/app/page-meta.ts`:

```diff
--- a/web/src/app/page-meta.ts
+++ b/web/src/app/page-meta.ts
@@ -27,6 +27,8 @@ export interface PageMeta {
   PhoneTitle?: ComponentType
   /** Phone only: a Back link before the title, to this path (Zone detail: Live). */
   phoneBack?: string
+  /** Phone only: a focused task (§8.10), drawn with no header and no tab bar (Phone-PutLookOn). */
+  focusedTask?: boolean
 }
 
 const FALLBACK: PageMeta = { title: 'dj-ledfx' }
```

In `web/src/app/routes.tsx`:

```diff
--- a/web/src/app/routes.tsx
+++ b/web/src/app/routes.tsx
@@ -24,8 +24,8 @@ const LIVE: PageMeta = {
 }
 /** Zone detail (Phone-Zone): the zone's name with Back to Live, and no context line or tempo strip. On desktop it's Live (F3 decision 23). */
 const ZONE: PageMeta = { title: LIVE.title, context: LIVE.context, PhoneTitle: ZoneTitle, phoneBack: '/live' }
-/** Put a look on (§8.2): Live, with the composer in the Running panel's place. */
-const PUT: PageMeta = { title: LIVE.title, context: LIVE.context }
+/** Put a look on (§8.2): Live, with the composer in the Running panel's place; on the phone, a focused task (Phone-PutLookOn). */
+const PUT: PageMeta = { title: LIVE.title, context: LIVE.context, focusedTask: true }
 const LOOKS: PageMeta = { title: 'Looks' }
 const MAP: PageMeta = {
   title: 'Map',
```

In `web/src/shell/app-shell.tsx`:

```diff
--- a/web/src/shell/app-shell.tsx
+++ b/web/src/shell/app-shell.tsx
@@ -14,7 +14,8 @@ import { TabBar } from './tab-bar'
 import { TopBar } from './top-bar'
 
 /**
- * §4.1–4.2: rail and top bar on desktop; header (with the tempo strip on Live) and tab bar on phone.
+ * §4.1–4.2: rail and top bar on desktop; header (with the tempo strip on Live) and tab bar on phone,
+ * except around a focused task (§8.10), which has the phone's screen to itself.
  * `<main>` keeps its place in the tree, so crossing the breakpoint swaps the chrome without
  * remounting the page. The root alone keeps everything out of the safe-area insets (index.html
  * sets viewport-fit=cover): a notch, a home indicator, a phone turned sideways, in either layout.
@@ -26,6 +27,7 @@ export function AppShell() {
   const isPhone = useIsPhone()
   const meta = usePageMeta()
   const { PhoneTitle } = meta
+  const focused = isPhone && meta.focusedTask === true
   const news = useConnectionNews(useConnectionStatus())
   const server = useServerName()
 
@@ -39,7 +41,7 @@ export function AppShell() {
         )}
       >
         <title>{documentTitle(meta.title)}</title>
-        {isPhone ? (
+        {focused ? null : isPhone ? (
           <PhoneHeader
             title={PhoneTitle ? <PhoneTitle /> : (meta.phoneTitle ?? meta.title)}
             back={meta.phoneBack}
@@ -58,7 +60,7 @@ export function AppShell() {
         <main className="min-h-0 flex-1 overflow-y-auto">
           <Outlet />
         </main>
-        {isPhone && <TabBar />}
+        {isPhone && !focused && <TabBar />}
       </div>
       <TapeFrame />
     </Announcer>
```

- [ ] **Step 6: The sheet**

Its sizes are Phone-PutLookOn's. The category chips and the transition are drawn smaller than `--touch-min`, so they get `touch-target`. The footer pads below as the render does, and on a phone with a home indicator the OS's inset adds below that (ruling 16):

Create `web/src/compose/composer-sheet.tsx`:

```tsx
// §8.10 Put a look on (Phone-PutLookOn): the composer as a sheet under the focused stage, which shows
// the preview with its tag. Where: the zone buttons in a row that scrolls. What: the category chips and
// the look rows (there's no search on the phone). Then the short consequence beside the transition, and
// Start <Look> on <Zone>. The sheet is part of the page, not a dialog: the stage above stays live, and a
// room tapped there chooses its zone. Its title is the page's h1, since the header that holds one steps
// aside (a focused task). Keyboard (F4 ruling 12): Up and Down move through the rows, previewing each,
// and Enter starts the look previewed; the page's Esc closes it.
import { useRef } from 'react'
import { Button } from '@/design/button'
import { cx } from '@/design/cx'
import { Icon } from '@/design/icon'
import { Grabber } from '@/design/overlays'
import { Select } from '@/design/select'
import { ConsequenceText } from './consequence-text'
import { LookRow } from './look-row'
import { CATEGORIES } from './model'
import { useComposerView, type LookSteps } from './use-composer-view'
import { ZonePicker } from './zone-picker'

/** Phone-PutLookOn's list: one look a row. */
const ROW_STEPS: LookSteps = { ArrowUp: -1, ArrowDown: 1 }

export function ComposerSheet({ className }: { className?: string }) {
  const rows = useRef<HTMLDivElement>(null)
  const view = useComposerView(ROW_STEPS, rows)
  const { zones, looks, zone, look, running, consequence: said } = view

  return (
    <section aria-label="Put a look on" className={cx('flex flex-col rounded-t-sheet border-t border-line bg-panel', className)}>
      <Grabber className="mt-2" />
      <div className="flex items-center justify-between px-4 pt-2">
        <h1 className="text-title font-semibold">Put a look on</h1>
        <button type="button" aria-label="Close" className="inline-flex size-11 shrink-0 items-center justify-center text-text-2" onClick={view.close}>
          <Icon name="x" size={20} />
        </button>
      </div>
      {zones !== undefined && looks !== undefined && zone !== undefined && (
        <>
          <div className="px-4">
            <ZonePicker zones={zones} running={running} selected={zone.id} locked={view.locked} onSelect={view.choose} variant="phone" />
          </div>
          <div className="flex flex-col gap-2 px-4 pt-3.5">
            <span className="label-caps text-text-3">What</span>
            {/* The chips are drawn smaller than --touch-min; the row's padding keeps their grown hit areas in it. */}
            <div role="group" aria-label="Categories" className="-my-1 flex gap-1.5 overflow-x-auto py-1">
              {CATEGORIES.map(({ id, label }) => (
                <button
                  key={id}
                  type="button"
                  aria-pressed={id === view.category}
                  className={cx(
                    'h-9 shrink-0 rounded-pill border px-3.5 text-data font-semibold whitespace-nowrap touch-target',
                    id === view.category ? 'border-text bg-control-hover text-text' : 'border-line text-text-2',
                  )}
                  onClick={() => view.chooseCategory(id)}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          <div ref={rows} role="group" aria-label="Looks" className="flex min-h-0 grow flex-col gap-0.5 overflow-y-auto px-2 pt-2" onKeyDown={view.onListKey}>
            {view.shown.length === 0 ? (
              <p className="px-2 text-meta text-text-3">{`No ${CATEGORIES.find((each) => each.id === view.category)?.label.toLowerCase()} looks yet.`}</p>
            ) : (
              view.shown.map((each) => (
                <LookRow
                  key={each.id}
                  look={each}
                  selected={each.id === look?.id}
                  here={each.id === view.here?.lookId}
                  missing={view.missing(each)}
                  tabbable={each.id === view.tabbable}
                  onSelect={() => view.pick(each.id)}
                />
              ))
            )}
          </div>
          <div className="flex flex-col gap-2.5 border-t border-line-soft px-4 pt-3 pb-7.5">
            <div className="flex items-center justify-between gap-2.5 text-data text-text-3">
              <span data-consequence>{said !== null && <ConsequenceText parts={said.short} lookClassName="font-serif text-[15px] text-text italic" />}</span>
              <Select
                label="Transition"
                value={view.transition}
                items={Object.fromEntries(view.transitions.map((choice) => [choice.key, choice.label]))}
                onValueChange={view.chooseTransition}
                className="h-9! w-37.5 shrink-0 touch-target"
              />
            </div>
            <Button variant="primary" size="cta" icon="play" disabled={view.blocked || view.starting} onClick={view.startChosen}>
              <span className="min-w-0 truncate">{look === undefined ? 'Start' : `Start ${look.name} on ${zone.name}`}</span>
            </Button>
          </div>
        </>
      )}
    </section>
  )
}
```

- [ ] **Step 7: The page**

The stage keeps Phone-Live's box, and the sheet fills the screen under it, over the stage's foot (ruling 16):

In `web/src/pages/live.tsx`:

```diff
--- a/web/src/pages/live.tsx
+++ b/web/src/pages/live.tsx
@@ -11,9 +11,11 @@ import type { Id } from '@/api/contract'
 import { queries } from '@/api/queries'
 import { usePreviewOnly } from '@/chrome/hooks'
 import { ComposerPanel, ComposerWhere } from '@/compose/composer-panel'
+import { ComposerSheet } from '@/compose/composer-sheet'
 import { useStageCompose } from '@/compose/use-composer'
 import { useComposerKeys } from '@/compose/use-composer-keys'
 import { Button } from '@/design/button'
+import { cx } from '@/design/cx'
 import { LIVE_SPEC } from '@/design/live-numbers'
 import { useIsPhone, useMediaQuery } from '@/lib/use-media-query'
 import { EmptyHome } from '@/live/empty-home'
@@ -69,12 +71,19 @@ export function LivePage() {
     </Suspense>
   )
   if (phone) {
+    // Phone-PutLookOn: the composer's sheet fills the screen under the stage, over the stage's foot.
     return (
-      <div className="flex min-h-full flex-col">
+      <div className={cx('flex flex-col', composing ? 'h-full' : 'min-h-full')}>
         <div className="relative shrink-0" style={{ aspectRatio: `${LIVE_SPEC.phoneStage.width} / ${LIVE_SPEC.phoneStage.height}` }}>
           {stage}
         </div>
-        {zoneId === undefined ? <PhoneRunning /> : <ZoneDetail zoneId={zoneId} />}
+        {composing ? (
+          <ComposerSheet className="relative z-10 -mt-9 min-h-0 flex-1" />
+        ) : zoneId === undefined ? (
+          <PhoneRunning />
+        ) : (
+          <ZoneDetail zoneId={zoneId} />
+        )}
       </div>
     )
   }
```

- [ ] **Step 8: e2e's `open()`**

The phone's composer has no header, so it has no attention button for `open()` to wait for. `open()` waits for the composer's Looks group instead. Without this, the phone's run of `shell.spec.ts`'s `/next/live/put` route fails, waiting for that button:

In `web/e2e/helpers.ts`:

```diff
--- a/web/e2e/helpers.ts
+++ b/web/e2e/helpers.ts
@@ -3,13 +3,15 @@ import { expect, type Locator, type Page } from '@playwright/test'
 
 /**
  * Opens a page and waits for the chrome's first data from the mock (the hero, unless the path asks
- * for another scenario): the attention button, whatever it says, or `ready` where there's none to wait
- * for (the phone's header hides it while nothing needs attention).
+ * for another scenario): the attention button, whatever it says, or on the phone's Put a look on, a
+ * focused task with no header (Phone-PutLookOn), the looks it offers; or `ready` where there's none
+ * of those to wait for (the phone's header hides the button while nothing needs attention).
  */
 export async function open(page: Page, path: string, ready?: Locator): Promise<void> {
   await page.goto(path)
   // The mock build renders once MSW's worker is up (app/boot.tsx), so the chrome comes first, then its fonts.
-  await expect(ready ?? page.getByRole('banner').getByRole('button', { name: /needs? attention$|^All good$/ })).toBeVisible()
+  const attention = page.getByRole('banner').getByRole('button', { name: /needs? attention$|^All good$/ })
+  await expect(ready ?? attention.or(page.getByRole('group', { name: 'Looks' })).first()).toBeVisible()
   await page.evaluate(() => document.fonts.ready)
 }
 
```

- [ ] **Step 9: Run them to see them pass**

Run: `(cd web && npx vitest run src/compose/composer.test.tsx)`
Expected: PASS (13 tests).

- [ ] **Step 10: Run the gate**

```bash
(cd web && npm test 2>&1 | tail -4 && npm run lint && npx tsc -b && echo "tsc ok" && npm run build 2>&1 | tail -1)
for i in $(seq 1 60); do [ "$(ss -ltn | grep -cE ':(4174|4175) ')" = 0 ] && break; sleep 10; done; ss -ltn | grep -cE ':(4174|4175) '
(cd web && npm run e2e 2>&1 | tail -3)
```

Expected:
- 799 tests in 100 files; lint is clean, and "tsc ok".
- The build ends `…/web/dist: no mocks, 280.6 KB of gzipped JS`.
- The port check prints `0`.
- e2e: 90 passed and 48 skipped.

- [ ] **Step 11: Commit**

```bash
git add web/src/compose web/src/design/overlays.tsx web/src/app web/src/shell/app-shell.tsx web/src/pages/live.tsx web/e2e/helpers.ts
git commit -m "feat(web): Put a look on, on the phone: a sheet under the focused stage, with no header or tab bar"
```

---

### Task 10: Put a look on in the browser, on both sizes

Every state the composer has, screenshotted on both sizes from the mock, each compared by eye with its render before its baseline is recorded. Then §14's "full keyboard path through Live → composer → Start", §6.4's and §8.10's sizes, a phone chip's touch band, and axe with the transition list open.

**Files:**
- Create: `web/e2e/compose.spec.ts`
- Create: `web/e2e/compose.spec.ts-snapshots/*.png` (Playwright records them)
- Modify: `web/e2e/shell.spec.ts` (`axeViolations()` takes an `exclude`; the transition list joins `OVERLAYS`)

**Interfaces:**
- Consumes:
  - the mock's `hero`, `dj-playing` and `inputs-down` scenarios, and what Tasks 5 to 9 draw;
  - `LIVE_SPEC.lookTile` and `LIVE_SPEC.phoneComposer` (Task 2);
  - `open()` and `stageCanvas()` (`e2e/helpers.ts`).
- Produces:
  - §13.1's done-when for F4 in the browser.
  - The baselines: `preview` (both renders' state, a look previewed on a room that runs another), `no-look`, `waits-for-music`, `home-look` and `no-lights` on both sizes, and `no-match` on desktop.

- [ ] **Step 1: Read the spec, and check the ports**

Read §13.1's M4 row, §14 (E2E, accessibility and visual) and CLAUDE.md's e2e gotchas. Then run the port check (Global Constraints, Workflow):

```bash
for i in $(seq 1 60); do [ "$(ss -ltn | grep -cE ':(4174|4175) ')" = 0 ] && break; sleep 10; done; ss -ltn | grep -cE ':(4174|4175) '
```

It must print `0`.

- [ ] **Step 2: Write the states and the flows**

The states hold the beat and the frames with `?still`, and fix the clock at the hero's time, as `live.spec.ts` does. No name is typed: the ids are in the paths, and what each state waits for is the composer's own words. The composer gives a look the focus as it opens (ruling 12), so each state blurs it before its screenshot, because the renders draw the page at rest:

Create `web/e2e/compose.spec.ts`:

```ts
import { expect, test, type Locator, type Page } from '@playwright/test'
import { LIVE_SPEC } from '../src/design/live-numbers'
import { open, stageCanvas } from './helpers'

// The hero moment (spec §12.5): Wednesday 23 September, 19:14 in the home's time zone (timezoneId in the config).
const HERO_TIME = new Date('2026-09-23T19:14:00-05:00')

/** The path with ?still: the mock holds the beat and the frames, so a screenshot is the same every run. */
const still = (path: string) => `${path}&still`

/** An element's box, which must be on screen. */
async function box(locator: Locator) {
  const found = await locator.boundingBox()
  if (!found) throw new Error(`${locator} is not on screen`)
  return found
}

interface State {
  /** The screenshot's name; Playwright adds the project's. */
  name: string
  path: string
  /** The render its baseline is compared with by eye, the project's own; null for a state no render draws. */
  render: 'PutLookOn' | null
  /** What shows once the state is drawn. */
  ready: (page: Page) => Locator
  /** Brings the state about once the page is open. */
  then?: (page: Page) => Promise<void>
  /** Desktop only: the phone's composer has no search (Phone-PutLookOn). */
  desktop?: true
}

// §13.1 F4: Put a look on, in each state the composer has, on both sizes. Names come from the mock, so
// none is written here: the ids are in the paths, and what's waited for is the composer's own words.
const STATES: State[] = [
  // Live-PutLookOn and Phone-PutLookOn: a look previewed on a room that runs another.
  { name: 'preview', path: '/next/live/put?zone=living&look=embers', render: 'PutLookOn', ready: (page) => page.getByText(/^Preview on screen/) },
  { name: 'no-look', path: '/next/live/put?zone=living', render: null, ready: (page) => page.getByText('Choose a look to see it on the stage first.') },
  {
    name: 'waits-for-music',
    path: '/next/live/put?scenario=dj-playing&zone=living&look=spectrum',
    render: null,
    ready: (page) => page.getByText('Waits for music', { exact: true }).first(),
  },
  // §8.2: a home look locks the zone to the whole home; with Home Assistant down, it would wait for it.
  {
    name: 'home-look',
    path: '/next/live/put?scenario=inputs-down&zone=living&look=goodnight',
    render: null,
    ready: (page) => page.getByText('Needs Home Assistant', { exact: true }).first(),
  },
  { name: 'no-lights', path: '/next/live/put?zone=counter&look=embers', render: null, ready: (page) => page.getByText(/ has no lights\.$/) },
  {
    name: 'no-match',
    path: '/next/live/put?zone=living&look=embers',
    render: null,
    ready: (page) => page.getByText(/^Preview on screen/),
    then: async (page) => {
      await page.getByRole('searchbox', { name: 'Search looks' }).fill('zzzz')
      await expect(page.getByText('No looks match “zzzz”.')).toBeVisible()
    },
    desktop: true,
  },
]

test.beforeEach(async ({ page }) => {
  await page.clock.setFixedTime(HERO_TIME)
})

for (const size of ['desktop', 'phone'] as const) {
  test.describe(`Put a look on's states on ${size === 'desktop' ? 'desktop' : 'the phone'}`, () => {
    test.skip(({ isMobile }) => isMobile !== (size === 'phone'))

    for (const state of STATES.filter((each) => size === 'desktop' || each.desktop !== true)) {
      test(`${state.name}${state.render === null ? '' : `, as ${size === 'desktop' ? 'Live' : 'Phone'}-${state.render}`}`, async ({ page }) => {
        await open(page, still(state.path))
        await expect(stageCanvas(page)).toBeVisible()
        await expect(state.ready(page)).toBeVisible()
        // As live.spec.ts: on desktop, the banner's frame rate settled.
        if (size === 'desktop') await expect(page.getByRole('banner').getByText('60 fps')).toBeVisible({ timeout: 10_000 })
        await state.then?.(page)
        // The composer gives a look the focus as it opens (F4 ruling 12), and a page opened by its URL
        // rings it as a keyboard would; the renders draw the page at rest.
        await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur())
        await expect(page).toHaveScreenshot(`${state.name}.png`)
      })
    }
  })
}

test.describe('on desktop', () => {
  test.skip(({ isMobile }) => isMobile)

  // F4 ruling 12: L opens the composer on the first look; the arrows choose as they move; Enter starts the
  // look chosen, and Esc leaves.
  test('the keyboard puts a look on: L, the arrows and Enter', async ({ page }) => {
    await open(page, '/next/live')
    await page.keyboard.press('l')
    await expect(page).toHaveURL(/\/next\/live\/put$/)
    const tiles = page.getByRole('group', { name: 'Looks' }).locator('[data-look]')
    await expect(tiles.first()).toBeFocused()
    await page.keyboard.press('ArrowRight')
    await expect(tiles.nth(1)).toBeFocused()
    await expect(page).toHaveURL(new RegExp(`look=${await tiles.nth(1).getAttribute('data-look')}$`))
    await expect(tiles.nth(1)).toHaveAttribute('aria-pressed', 'true')
    await page.keyboard.press('Enter')
    await expect(page).toHaveURL(/\/next\/live$/)
    await expect(page.getByRole('status')).toHaveText(/^Started .+ on .+\.$/)

    await page.keyboard.press('l')
    await expect(tiles.first()).toBeFocused()
    await page.keyboard.press('Escape')
    await expect(page).toHaveURL(/\/next\/live$/)
  })

  // §6.4's composer tiles, to the pixel: the panel's border leaves each of the grid's two columns half a
  // pixel short, as the render's own grid does.
  test('the tiles are as wide as §6.4 says', async ({ page }) => {
    await open(page, '/next/live/put?zone=living&look=embers')
    const tiles = page.getByRole('group', { name: 'Looks' }).locator('[data-look]')
    await expect(tiles.first()).toBeVisible()
    for (const tile of await tiles.all()) {
      expect(Math.round((await box(tile)).width)).toBe(LIVE_SPEC.lookTile.px)
    }
  })
})

test.describe('on the phone', () => {
  test.skip(({ isMobile }) => !isMobile)

  // §8.10's zone buttons and the look rows' thumbs, at the sizes it gives them (LIVE_SPEC.phoneComposer).
  test("the zone buttons and the rows' thumbs are §8.10's", async ({ page }) => {
    await open(page, '/next/live/put?zone=living&look=embers')
    const sheet = page.getByRole('region', { name: 'Put a look on' })
    const zones = sheet.getByRole('group', { name: 'Where' }).getByRole('button')
    await expect(zones.first()).toBeVisible()
    for (const zone of await zones.all()) {
      expect((await box(zone)).height).toBe(LIVE_SPEC.phoneComposer.zonePx)
    }
    const thumb = await box(sheet.locator('[data-look="embers"] [data-thumb]'))
    expect([thumb.width, thumb.height]).toEqual([LIVE_SPEC.phoneComposer.thumb.width, LIVE_SPEC.phoneComposer.thumb.height])
  })

  // The category chips keep Phone-PutLookOn's face, drawn smaller than --touch-min, and `touch-target` grows
  // each one's hit area to a band that tall (CLAUDE.md), inside the row that scrolls them.
  test('a category chip answers a touch anywhere in a band --touch-min tall', async ({ page }) => {
    await open(page, '/next/live/put?zone=living&look=embers')
    const chip = page.getByRole('group', { name: 'Categories' }).getByRole('button', { name: 'Tempo' })
    const face = await box(chip)
    const hits = await page.evaluate(
      ({ x, middle }) => {
        // Half a pixel inside the band's top and bottom edges.
        const reach = parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--touch-min')) / 2 - 0.5
        return [middle - reach, middle + reach].map((y) => document.elementFromPoint(x, y)?.closest('button')?.textContent ?? null)
      },
      { x: face.x + face.width / 2, middle: face.y + face.height / 2 },
    )
    expect(hits).toEqual(['Tempo', 'Tempo'])
  })
})
```

- [ ] **Step 3: The transition list joins `OVERLAYS`**

The list portals out of `<main>`, so axe looks at the page with it open (CLAUDE.md, Gotchas). On the phone, axe's aria-hidden-focus rule flags Base UI's focus guards there, for the reason ruling 20 gives, so this entry leaves the guards out and says why:

In `web/e2e/shell.spec.ts`:

```diff
--- a/web/e2e/shell.spec.ts
+++ b/web/e2e/shell.spec.ts
@@ -47,9 +47,10 @@ async function openStill(page: Page, path: string) {
   if (!isPhone(page)) await expect(page.getByRole('banner').getByText('60 fps')).toBeVisible({ timeout: 10_000 })
 }
 
-/** axe's findings for the page as it stands, one line per rule. */
-async function axeViolations(page: Page): Promise<string[]> {
-  const { violations } = await new AxeBuilder({ page }).analyze()
+/** axe's findings for the page as it stands, one line per rule, leaving out what `exclude` selects. */
+async function axeViolations(page: Page, exclude?: string): Promise<string[]> {
+  const builder = new AxeBuilder({ page })
+  const { violations } = await (exclude === undefined ? builder : builder.exclude(exclude)).analyze()
   return violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)
 }
 
@@ -121,7 +122,15 @@ for (const path of ROUTES) {
 
 // Decision 12: /system is there to run axe over every primitive. Base UI mounts an overlay's popup
 // only while it's open, so each one is opened before axe looks.
-const OVERLAYS: { name: string; path?: string; desktop?: boolean; open: (page: Page) => Promise<void>; popup: (page: Page) => Locator }[] = [
+const OVERLAYS: {
+  name: string
+  path?: string
+  desktop?: boolean
+  open: (page: Page) => Promise<void>
+  popup: (page: Page) => Locator
+  /** What axe leaves out, and the entry says why. */
+  exclude?: string
+}[] = [
   {
     name: 'Tooltip',
     open: (page) => page.getByRole('button', { name: 'Fit', exact: true }).hover(),
@@ -167,6 +176,16 @@ const OVERLAYS: { name: string; path?: string; desktop?: boolean; open: (page: P
     open: (page) => page.getByRole('button', { name: 'Stop all', exact: true }).click(),
     popup: (page) => page.getByRole('alertdialog', { name: 'Stop all?', exact: true }),
   },
+  {
+    name: "composer's transition list",
+    path: '/next/live/put?zone=living&look=embers',
+    open: (page) => page.getByRole('combobox', { name: 'Transition', exact: true }).click(),
+    popup: (page) => page.getByRole('listbox'),
+    // Base UI's focus guards are tabbable and aria-hidden by design, and axe excuses them only while it
+    // takes the page for a modal one: a fixed layer at each of five points it samples. The list's
+    // backdrop has a hole over its trigger, and the phone's trigger sits on one of the points.
+    exclude: '[data-base-ui-focus-guard]',
+  },
   {
     name: 'tempo source popover',
     path: '/next/live',
@@ -182,7 +201,7 @@ for (const overlay of OVERLAYS) {
     await open(page, overlay.path ?? '/next/system')
     await overlay.open(page)
     await expect(overlay.popup(page)).toBeVisible()
-    expect(await axeViolations(page)).toEqual([])
+    expect(await axeViolations(page, overlay.exclude)).toEqual([])
   })
 }
 
```

- [ ] **Step 4: Run e2e, and compare each picture with its render**

Run: `(cd web && npm run e2e 2>&1 | tail -15)`
Expected: FAIL. 11 tests fail with "A snapshot doesn't exist", six on desktop and five on the phone, each writing its first picture into `e2e/compose.spec.ts-snapshots/`. 96 pass, and 63 are skipped.

Then look once at each new picture, and once at its render in the main checkout's `docs/design/web-app/reference/`:
- `preview`: `Live-PutLookOn.png` on desktop, and `Phone-PutLookOn.png` on the phone.
- The states no render draws: the same size's render, for everything but the state's own words and marks. Those are the consequence line, a tile's or a row's signal line, the zones a home look locks, and the empty grid's sentence.

Write down what differs. Where the app is wrong, fix the code in the task that owns it, and run again. These differences are deliberate, and stay:
- the zones come in the server's order, each with its note (rulings 4 and 5);
- the looks come in the server's order (ruling 18);
- the transition is each look's own, where Live-PutLookOn shows a dissolve chosen (ruling 11);
- the notes on a `control` fill are `text-2` (ruling 19);
- the thumbs are plain tiles until F5 (ruling 7);
- the phone's stage keeps Phone-Live's height, where Phone-PutLookOn draws it shorter (ruling 16);
- what runs where, and so every note and sentence that says it, is the mock hero's, where the renders' sample worlds differ from it;
- "Pick lights…" is drawn as the renders draw it, and does nothing (ruling 6).

When every picture matches its render but for those, record them, check the ports again, and run e2e once more:

```bash
(cd web && npm run e2e -- --update-snapshots 2>&1 | tail -3)
for i in $(seq 1 60); do [ "$(ss -ltn | grep -cE ':(4174|4175) ')" = 0 ] && break; sleep 10; done; ss -ltn | grep -cE ':(4174|4175) '
(cd web && npm run e2e 2>&1 | tail -3)
```

Expected: the port check prints `0`, then PASS: 107 passed and 63 skipped.

- [ ] **Step 5: The frame rate, on this machine's GPU**

The stage's frame writer now reads each light from the stream its entry names (Task 5), on every frame. Run Step 1's port check again, then:

Run: `(cd web && npm run e2e:perf 2>&1 | tail -6)`
Expected: PASS: `2 passed`, with each project's `fps`, `p95GapMs` and `busy` printed. Write them down for the PR. While this plan was checked, master and this task's tree measured the same, within a run's noise.

- [ ] **Step 6: Commit**

```bash
git add web/e2e
git commit -m "test(web): Put a look on's states on both sizes, its keyboard path, and axe with the transition list open"
```

---

### Task 11: Revise CLAUDE.md

CLAUDE.md gains the preview's new answer, the composer's modules, and the gotchas this branch found. No design values go in, because CLAUDE.md forbids restating them there.

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: the names Tasks 1 to 10 gave their modules, as their Interfaces blocks list them.
- Produces: nothing that code reads.

- [ ] **Step 1: Invoke `claude-md-management:revise-claude-md`**

Use it to review what this branch taught. The edits below are the minimum. Keep any other edit it proposes that also follows the no-design-values rule and the public-repo rule (Global Constraints).

- [ ] **Step 2: The engine**

Both are in the `src/dj_ledfx/` block of `## Architecture`.

In `CLAUDE.md`, replace:

```markdown
`zones/preview.py` (`PreviewManager`: one preview at a time)
```

with:

```markdown
`zones/preview.py` (`PreviewManager`: one preview at a time; `preview_lights()`, what each of a preview's lights would do if its look started, which `POST /preview` answers for the composer's consequence line)
```

In `CLAUDE.md`, replace:

```markdown
`transition_in()`, and `RunningZone.transition` with `durationS`; `web/errors.py`
```

with:

```markdown
`transition_in()`, and `RunningZone.transition` with `durationS`; `PreviewStarted.lights` (`PreviewLight`, outside the web spec's contract until a handoff adds it), where `preview_started()` answers for the PC as its most active part; `web/errors.py`
```

- [ ] **Step 3: The web app**

All of these are in the `web/` block of `## Architecture`.

In `CLAUDE.md`, replace:

```markdown
`failureText()` says what failed), `live.ts` (the app's singletons;
```

with:

```markdown
`failureText()` says what failed), `preview.ts` (`PreviewSession`, the composer's one preview: a choice made while another is on its way is asked for once that one is answered, so the last choice wins; the preview stream is watched while one is on, and it's asked for again after a resync; components read it through `usePreview()`, in `use-preview.ts`), `live.ts` (the app's singletons, the preview session among them;
```

In `CLAUDE.md`, replace:

```markdown
- `src/stage/` — the stage (§7), `live`, `frozen` and `focus` modes.
```

with:

```markdown
- `src/stage/` — the stage (§7), `live`, `frozen`, `focus` and `compose` modes.
```

In `CLAUDE.md`, replace:

```markdown
`overlays/` the SVG layer (with the outline of the zone a card hovers) and the HTML overlays (the tooltip, the zone tags)
```

with:

```markdown
`overlays/` the SVG layer (with the outline of the zone a card hovers, or of the composer's zone with the other rooms dimmed) and the HTML overlays (the tooltip, the zone tags, and the preview's card and tag)
```

In `CLAUDE.md`, replace:

```markdown
- `src/shell/` — rail, top bar, tab bar, phone header (with Back where the page asks for it); `AppShell` swaps desktop and phone chrome at the phone breakpoint without remounting the page, and draws preview only's tape frame round the window
```

with:

```markdown
- `src/compose/` — Put a look on (§8.2, §8.10), the composer at `/live/put?zone=&look=` (`composerPath()`): `model.ts` (the pure part: the zone chosen, the zones' notes, the categories and the looks shown, the inputs a look would wait for, the transitions offered), `consequence.ts` (the consequence line, from the preview's `lights` and what runs where), `last-zone.ts` (the zone a look last started on), `use-composer.ts` (`useComposer()`: the choice in the URL, the preview, Start and Cancel; `useStageCompose()`, the stage's part), `use-composer-view.ts` (what the desktop panel and the phone's sheet share: the category, the search, the transition and the arrow keys) and `use-composer-keys.ts` (L opens it from Live, Esc closes it); `ComposerPanel` with `ComposerWhere` draw it on desktop and `ComposerSheet` on the phone, from `ZonePicker`, `LookTile`, `LookRow` and `ConsequenceText`
- `src/looks/` — `LookThumb`, a look's thumb in the composer's tiles and rows: a plain tile until F5 draws each look's motif (F4 ruling 7)
- `src/shell/` — rail, top bar, tab bar, phone header (with Back where the page asks for it); `AppShell` swaps desktop and phone chrome at the phone breakpoint without remounting the page, draws preview only's tape frame round the window, and leaves the phone's header and tab bar out of a focused task (`PageMeta.focusedTask`)
```

In `CLAUDE.md`, replace:

```markdown
the Running panel beside it, or over it below the wide breakpoint; on the phone, the list or Zone detail under a stage that stays mounted)
```

with:

```markdown
the Running panel beside it, or over it below the wide breakpoint, and Put a look on in the panel's place; on the phone, the list, Zone detail or Put a look on's sheet under a stage that stays mounted)
```

In `CLAUDE.md`, replace:

```markdown
the swatch's colour maths that the stage shares (`light-colour.ts`), and the viewport
```

with:

```markdown
the swatch's colour maths that the stage shares (`light-colour.ts`), `browserStorage()` (`storage.ts`: localStorage, or null where reaching it throws), and the viewport
```

In `CLAUDE.md`, replace:

```markdown
- `e2e/` — Playwright specs (`live.spec.ts` screenshots each §9 Live state on both sizes, one scenario each), `helpers.ts` (`open()`, which waits for the attention button or for the locator it's given,
```

with:

```markdown
- `e2e/` — Playwright specs (`live.spec.ts` screenshots each §9 Live state on both sizes, one scenario each, and `compose.spec.ts` each of Put a look on's states, with its keyboard path), `helpers.ts` (`open()`, which waits for the attention button, or on the phone's Put a look on for its looks, or for the locator it's given,
```

- [ ] **Step 4: Gotchas**

In `CLAUDE.md`, replace:

```markdown
(`open()` in e2e/helpers.ts waits for the attention button, whatever it says, or for the locator passed as `ready` where the phone hides that button)
```

with:

```markdown
(`open()` in e2e/helpers.ts waits for the attention button, whatever it says, or for the composer's Looks group where a focused task has no header, or for the locator passed as `ready` where the phone hides that button)
```

In `CLAUDE.md`, replace:

```markdown
- Web app: on the phone `/live/zones/:zoneId` is a child of Live's route with no element, so the stage stays mounted from the list to a zone and only its `focus` changes; on desktop the same route outlines the zone and scrolls its card into view
```

with:

```markdown
- Web app: on the phone `/live/zones/:zoneId` is a child of Live's route with no element, so the stage stays mounted from the list to a zone and only its `focus` changes; on desktop the same route outlines the zone and scrolls its card into view
- Web app: `/live/put` (Put a look on) is a child of Live's route with no element too, so the stage stays mounted and goes into `compose` mode. On the phone it's a focused task (`PageMeta.focusedTask`): no header and no tab bar, so the sheet's title is the page's h1. Every choice in the composer replaces the URL, so Back leaves it, and leaving it ends the preview
```

In `CLAUDE.md`, replace:

```markdown
so a mock light that's on but dim is a darker colour, not a separate level
```

with:

```markdown
so a mock light that's on but dim is a darker colour, not a separate level
- Web app: Vitest's fake timers hang `userEvent`, whose calls wait on a `setTimeout` the fake clock holds, so a test on fake timers drives the page with `fireEvent`. Base UI's Select opens on a click, and picks an option only on a whole press: pointer and mouse down and up, then the click (`press()` in src/compose/composer.test.tsx)
- Web app: Base UI's lists (Select, Menu) stop Esc inside them, so a page-wide Esc listens on `window` and leaves a key already handled alone (`event.defaultPrevented`), as `useComposerKeys()` does; an input whose Esc does something of its own first (the composer's search clears) calls `preventDefault()`
- Web app: `text-3` meets §14's contrast on `bg` and `panel` but not on a `control` fill, where the renders draw it on the composer's zone chips and its chosen row: text on `control` is `text-2` or brighter (F4 ruling 19), and axe on every route fails a slip
- Web app: axe's aria-hidden-focus rule excuses Base UI's focus guards only while it takes the page for a modal one, which it decides by finding one fixed layer under five points it samples. An open list's backdrop leaves a hole over its trigger, so where a trigger sits on one of the points (the phone composer's Transition), the `OVERLAYS` entry in e2e/shell.spec.ts passes `exclude: '[data-base-ui-focus-guard]'` and says why
- Web app: a row that scrolls sideways (the phone composer's Where) stops wherever `scrollIntoView` leaves it as the fonts and the notes land, and its screenshots flaked: it snaps (`snap-x snap-proximity`, `snap-start` on each button), the chosen button leads it as the composer opens (`inline: 'start'`), and a later choice scrolls only as far as it must (`'nearest'`)
- Web app: the engine refuses a preview or a start of a whole-home look until M6 (400), while the mock allows both, as the hero runs one: the composer says the refusal where the consequence goes and keeps Start, which announces its own failure (F4 ruling 3)
```

- [ ] **Step 5: Check that no design values or private names slipped in**

```bash
git diff CLAUDE.md | grep -nE '^\+.*(#[0-9a-fA-F]{6}|[0-9.]+ ?(px|fps|ms|°|%)|[0-9]+ × [0-9]+)'
git diff CLAUDE.md | grep -E '^\+' | grep -nE '([0-9]{1,3}\.){3}[0-9]{1,3}|([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}'
```

Expected: no output from either.

- [ ] **Step 6: Check that every file CLAUDE.md now names exists**

```bash
for f in compose/model.ts compose/consequence.ts compose/last-zone.ts compose/use-composer.ts compose/use-composer-view.ts \
  compose/use-composer-keys.ts compose/composer-panel.tsx compose/composer-sheet.tsx compose/zone-picker.tsx \
  compose/look-tile.tsx compose/look-row.tsx compose/consequence-text.tsx compose/composer.test.tsx looks/look-thumb.tsx \
  api/preview.ts api/use-preview.ts lib/storage.ts; do test -f "web/src/$f" || echo "MISSING: $f"; done
for f in web/e2e/compose.spec.ts web/e2e/shell.spec.ts web/e2e/helpers.ts src/dj_ledfx/zones/preview.py src/dj_ledfx/web/contract.py; do
  test -f "$f" || echo "MISSING: $f"; done; echo "names checked"
```

Expected: "names checked" alone.

- [ ] **Step 7: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add the web app's Put a look on to CLAUDE.md"
```

---

### Task 12: Rebase over master, and open the PR

Engine M5 (particles) is planned beside this plan, and may merge first. Its plan changes nothing under `web/` and no API shape, but master may move in `web/src/api/generated/*`, `web/src/api/contract.ts` and the mocks before F4 lands, and this task settles that. This task brings the branch onto the latest `master`, runs every gate, and opens the PR. It never merges.

**Files:**
- Modify, only where the rebase asks: `web/src/api/contract.ts`, `web/src/api/mocks/fixtures.ts`, `web/src/api/mocks/mock-server.ts`, `web/src/api/mocks/mock-server.test.ts`, `web/src/api/mocks/scenarios.ts`, Task 1's Python files, `CLAUDE.md`
- Regenerate, where the rebase or master asks: `web/src/api/generated/*`, and `web/e2e/compose.spec.ts-snapshots/*.png` after a comparison by eye

**Interfaces:**
- Consumes: every task's commits; master as it is now.
- Produces: the pull request.

- [ ] **Step 1: Rebase onto master**

```bash
git fetch origin
git log --oneline d6f959e..origin/master
git rebase origin/master
```

The branch hasn't been pushed, so rebasing is safe. Read the log, and write down whether engine M5 had merged, for the PR. Where a commit conflicts:
- **`web/src/api/generated/*`** (Task 1): take master's side with `git checkout --ours web/src/api/generated` (in a rebase, "ours" is master's side). Then regenerate the types from the backend as the commit now has it, both sides' changes together, and stage them in the same commit, as CLAUDE.md asks of an API change:

  ```bash
  uv sync --extra web
  (cd web && npm run api:types)
  git add web/src/api/generated
  ```

- **`web/src/api/contract.ts`** (Task 1): keep both sides' aliases, each once, in the file's order.
- **`web/src/api/mocks/fixtures.ts`, `mock-server.ts`, `mock-server.test.ts` and `scenarios.ts`** (Task 1): keep both sides. Where both sides changed an import list, keep every name once, in the list's order.
- **`src/dj_ledfx/zones/preview.py`, `src/dj_ledfx/web/contract.py`, `src/dj_ledfx/web/router_preview.py` and their tests** (Task 1): keep both sides.
- **`CLAUDE.md`** (Task 11): keep both sides.
- **A baseline under `web/e2e/*-snapshots/`** (Task 10): keep F4's with `git checkout --theirs <file>` ("theirs" is the commit being replayed). Step 3 compares it again.
- **Anything else**: stop and tell the owner.

After each resolution, run `git add` on the resolved files, then `git rebase --continue`.

- [ ] **Step 2: The API types**

```bash
uv sync --extra web
(cd web && npm ci && npm run api:types && git status --short src/api/generated && npm run api:check)
```

Expected:
- `git status` lists nothing: every commit carries its own types.
- `api:check` passes.

If `git status` lists files, the committed types and the backend disagree. Commit the regenerated files, and say so in the PR:

```bash
git add web/src/api/generated
git commit -m "chore(web): regenerate the API types after the rebase"
```

- [ ] **Step 3: The whole web gate, from a clean install**

```bash
(cd web && npm ci && npm run api:check && npm test 2>&1 | tail -4 && npm run lint && npx tsc -b && npm run build 2>&1 | tail -1)
for i in $(seq 1 60); do [ "$(ss -ltn | grep -cE ':(4174|4175) ')" = 0 ] && break; sleep 10; done; ss -ltn | grep -cE ':(4174|4175) '
(cd web && npm run e2e 2>&1 | tail -3)
for i in $(seq 1 60); do [ "$(ss -ltn | grep -cE ':(4174|4175) ')" = 0 ] && break; sleep 10; done; ss -ltn | grep -cE ':(4174|4175) '
(cd web && npm run e2e:perf 2>&1 | tail -6)
```

Expected:
- Vitest passes: Task 10's count (799 tests in 100 files on `d6f959e`), plus whatever master added since.
  - `src/stage/design-numbers.node.test.ts` is among them. If it fails, a new handoff landed on master: stop and tell the owner, because the composer's numbers and the renders changed together, and Task 10's comparison has to be made again.
- Lint is clean, and `tsc -b` passes.
- `npm run build` ends with `…/web/dist: no mocks, <n> KB of gzipped JS`, within §14's budget (280.6 KB on `d6f959e`). Write `<n>` down for the PR.
- Each port check prints `0`.
- e2e passes with Task 10's counts (107 passed and 63 skipped on `d6f959e`), plus any master added.
  - If a composer screenshot fails because master changed what the mock serves or how the stage draws, compare it with its render by eye, as Task 10 did. Then re-record it (`npm run e2e -- --update-snapshots`, after the port check), run e2e again, and commit: `git add web/e2e && git commit -m "test(web): re-record Put a look on's screenshots over master"`.
  - If it fails because the composer changed, go back to the task that owns the code.
- `e2e:perf` prints `2 passed`. Write down each project's `fps`, `p95GapMs` and `busy` for the PR.

- [ ] **Step 4: The Python gate**

```bash
uv run pytest -q -p no:randomly 2>&1 | tail -1
uv run ruff check . && uv run ruff format --check . 2>&1 | tail -1
uv run mypy src/ 2>&1 | grep -E 'zones/preview\.py|web/contract\.py|web/router_preview\.py|^Found'
```

Expected:
- pytest passes: Task 1's count (`2031 passed, 1 skipped, 42 deselected` on `d6f959e`), plus whatever master added.
- ruff: `All checks passed!`, and every file already formatted.
- mypy prints only its `Found …` line, with no error in a file F4 changed: `Found 16 errors in 4 files` on `d6f959e`, master's own baseline.

- [ ] **Step 5: Scope and privacy checks**

```bash
git diff --stat origin/master...HEAD -- frontend/ docs/design/
git diff --stat origin/master...HEAD -- '*.py' pyproject.toml uv.lock | tail -1
for f in home.json looks.json; do cmp docs/design/web-app/$f web/src/api/mocks/$f || echo "DIFFERS: $f"; done
cmp docs/design/web-app/tokens.css web/src/styles/tokens.css && cmp docs/design/web-app/icons.ts web/src/design/icons.ts && echo "copies identical"
git status --short
```

Expected:
- No diff under `frontend/` or `docs/design/`.
- `5 files changed`: Task 1's three engine files and two test files, and no dependency change.
- No `DIFFERS`, then `copies identical`.
- A clean tree.

The repo is public. Check the branch's added lines, and its commit messages, for LAN addresses, MAC addresses, light names, light model names, deck model names, network interface names and AI model names. The names come from the mock's `home.json` and `looks.json`, so this plan never spells one out. For the same reason, the AI model check looks for a model id's shape (a parameter count such as `7b`, a quantisation, an `instruct` tag, a versioned model id) rather than for any name:

```bash
git diff origin/master...HEAD -- . ':!web/package-lock.json' | grep -E '^\+' | grep -nE '(192\.168|10\.[0-9]+\.[0-9]+\.[0-9]+|172\.(1[6-9]|2[0-9]|3[01])\.[0-9]+\.[0-9]+)|([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}'
git diff origin/master...HEAD -- . ':!web/src/api/mocks/home.json' | grep -E '^\+' | grep -nF -f <(node -e "for (const m of new Set(require('./web/src/api/mocks/home.json').lights.map((l) => l.model))) console.log(m)")
git diff origin/master...HEAD -- . ':!web/package-lock.json' | grep -E '^\+' | grep -niE '\b(XDJ|CDJ|DJM|DDJ)-?[0-9A-Z]|\b(enp[0-9]+s[0-9]+|eth[0-9]+|wlan[0-9]+|wlp[0-9]+s[0-9]+)\b|\b[0-9]+(\.[0-9]+)?b\b|instruct|gguf|\bawq\b|gptq|\bfp8\b|claude-[a-z]+-[0-9]'
git log --format=%B origin/master..HEAD | grep -nE '([0-9]{1,3}\.){3}[0-9]{1,3}|([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}'
node -e "
const home = require('./web/src/api/mocks/home.json'), looks = require('./web/src/api/mocks/looks.json')
const all = [...(home.rooms ?? []), ...(home.subZones ?? []), ...(home.lights ?? []), ...(looks.looks ?? looks)]
for (const name of new Set(all.map((each) => each.name))) console.log(name)
" > /tmp/f4-names.txt
git diff origin/master...HEAD -- . ':!web/src/api/mocks/*.json' ':!web/e2e/*-snapshots/*' ':!web/package-lock.json' | grep -E '^\+' | grep -nwF -f /tmp/f4-names.txt
git log --format=%B origin/master..HEAD | grep -nwF -f /tmp/f4-names.txt
```

Expected: no output from any of them, but for the lines that say "PC": that's the engine's own word for the computer's devices as one light, which master's CLAUDE.md and engine code already use. Look at any other match by eye:
- Take out a real address, MAC, name, model or interface name.
- Ignore a false alarm, such as a short model name inside another word.

- [ ] **Step 6: Push and open the PR**

Fill in:
- the test count and file count, the build's KB figure and the frame-rate numbers, from Step 3;
- the pytest count, from Step 4;
- whether engine M5 had merged, from Step 1.

```bash
git push -u origin feature/web-f4-put-a-look-on
gh pr create --base master --title "F4: web app Put a look on" --body-file - <<'EOF'
## Summary

Milestone F4 (the handoff's M4) of the web app rebuild, per docs/superpowers/plans/2026-10-07-f4-put-a-look-on.md.

- **The composer** (§8.2) at `/live/put?zone=&look=`, in the Running panel's place: Where (`ZonePicker`), What (the search, the categories and `LookTile`s) and How (the transition, the consequence line, Cancel and Start).
- **The preview:** choosing a look previews it on the stage at once, while the lights keep what they run until Start. `PreviewSession` asks for one preview at a time, so the last choice wins; it ends the preview when the composer goes, and asks for it again when the link comes back.
- **The stage's `compose` mode** (§7.6): the zone outlined and the other rooms dimmed, the zone's lights on the preview stream, a room click choosing its zone, and the PREVIEW ON SCREEN card on desktop and tag on the phone.
- **The consequence line** (§8.2, §11.3): what the look takes over, what stops, which lights would run their own effect or a streamed copy, and what it would wait for.
- **The keyboard** (§8.2): `L` opens the composer, the arrows preview as they move, Enter starts, and Esc closes.
- **The phone** (§8.10): a focused task, with the composer as a sheet under the stage.
- **The engine:** `POST /api/preview` also answers `lights`, what each of the zone's lights would do (`PreviewLight`). The types are regenerated, and the mock answers the same.
- Done when "Start a look in ≤ 3 clicks from Live; lights unchanged until Start (mock asserts)": `composer.test.tsx` starts a look with Put a look on, a tile and Start, and the mock's lights stay unchanged until the Start.
- CLAUDE.md: the composer's modules and gotchas.
- Engine M5: <merged before this, and its particle looks join the composer | not merged yet>.

## For the owner

The plan's decisions fill gaps in the spec. The ones to check:
- 1: `POST /api/preview` also answers `lights`, which the web spec's contract doesn't have yet; the contract model's docstring says so.
- 3: the engine refuses a whole-home look until M6. The composer says the refusal where the consequence goes and keeps Start, which says its own. The mock allows them.
- 4 and 5: each zone's note, and the zones in the server's order on both sizes.
- 6: "Pick lights…" is drawn, and does nothing yet.
- 7: `LookThumb` is a plain tile until F5.
- 11: the transitions on offer, with each look's own as the default.
- 16: the phone's stage keeps Phone-Live's height, and the composer is a focused task.
- 18: the looks in the server's order.
- 19: text on a control fill is text-2, where the renders draw text-3, for §14's contrast.

## Differences from the renders

- The zones' order and notes (decisions 4 and 5), and the looks' order (decision 18).
- The transition shown is each look's own, where Live-PutLookOn shows a dissolve chosen (decision 11).
- Notes on a control fill are text-2 (decision 19).
- Plain thumbs until F5 (decision 7).
- The phone's stage keeps Phone-Live's height (decision 16).
- What runs where is the mock hero's, where the renders' sample worlds differ from it.

## Test plan

- [x] `cd web && npm test`: <N> tests in <F> files: the model, the consequence's words, the preview session's races, compose mode, the tiles, rows and zone picker, and the composer's flows on both sizes
- [x] `cd web && npm run e2e`: each of the composer's states on both sizes, compared by eye with its render; the keyboard from Live to Start; §6.4's and §8.10's sizes; axe on `/live/put` and with the transition list open
- [x] `cd web && npm run e2e:perf`: desktop <fps> fps (p95 gap <p95> ms), main thread busy <busy>; phone <fps> fps, busy <busy>
- [x] `cd web && npm run build`: no mocks, <n> KB of gzipped JS, three.js's chunk aside
- [x] `uv run pytest`: <pytest count>; ruff clean; mypy at master's baseline
- [x] No LAN address, MAC, light name, light model or AI model name in the diff

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
```

Expected: `gh` prints the PR's URL. Don't merge it.

- [ ] **Step 7: The final review**

Run the final review of the whole branch now, the one the run's method ends with. Fix every finding it raises, Minor ones included: each fix goes in its own commit, after the gate of the task that owns the code. Push the fixes to the PR. Then stop: the owner merges.

---

## Hand-off

F4 builds Put a look on, on both sizes, and the stage's `compose` mode. The rest belongs to later milestones. Each item names the F4 piece it builds on.

**F5 (the Looks library)**
- **`LookThumb`'s motifs, and `live`** (§6.4). F4's `LookThumb({lookId, size})` draws a plain tile keyed by the look's `thumbnail` (F4 ruling 7). F5 adds each look's motif and `live` with no caller changing.
- **Nothing running's Start again** keeps its own plain tile (F3 decision 27). F5 swaps in `LookThumb`, motif and all (ruling 7).
- **Starring.** The composer's Starred chip shows the looks the server marks `starred`. Starring one is F5's.

**F8 (the look editor)**
- **The editor's preview** goes through `PreviewSession` (`src/api/preview.ts`). It sends an edited `look` where the composer sends a `lookId`, and each edit through `api.updatePreview`. The editor frames its zone with the stage's `focus` (F3's hand-off).

**F9 (phone layouts)**
- `PageMeta.focusedTask` gives any phone page the whole screen, with no header and no tab bar. §8.10's other focused tasks (Phone-Map's "No tab bar (a focused task)") use it.

**F10 (the doorbell, effects in space, reduced motion, the performance and accessibility pass)**
- **The performance pass.** `npm run e2e:perf` measures Live. A measure of `compose`, with the preview stream on the zone's lights, is F10's to add.

**Engine M5 (particles)**
- On the real engine, M5's particle looks join the composer's grid and rows in the server's order (ruling 18), under their category's chip. The mock already serves every look in `looks.json`, so F4's tests and screenshots don't change with M5.
- F4's code has no placeholder for M5: nothing in `web/src` hides, greys out or skips a look the engine doesn't serve yet. If M5 merges after F4, its own last task checks that again.

**Engine M6**
- **Whole-home looks start.** The engine stops refusing them, and ruling 3's gap closes with no change in the composer.
- **The sun.** Once the engine serves it, `missingInputs()` (`compose/model.ts`) judges it too, as ruling 8 judges music.

**Not yet in any milestone**
- **"Pick lights…"** (ruling 6) is drawn and inert: picking lights for a custom group has no render and no milestone. Whoever draws it replaces `ZonePicker`'s inert chip.

**Every backend change to the API**
- Run `cd web && npm run api:types` in the same commit. Otherwise `tests/web/test_openapi_types.py` fails.
- A new look category needs its chip in `CATEGORIES` (`compose/model.ts`). Nothing type-checks that every category has one, and until it's there, that category's looks show only in a search.

**Every new handoff**
- Run `cd web && npm run design:numbers`, and compare every composer screenshot with its new render by eye before re-recording it.

## Coverage

| §13.1 M4, and the sections F4 touches | Task |
|---|---|
| The preview's lights, from the engine's runtime, for the consequence line; the regenerated types; the mock (§8.2, §12; rulings 1 and 2) | 1 |
| The composer's numbers from the spec and the pinned renders | 2 |
| The preview session: one request at a time, the last choice wins, ended on leaving, asked again after a resync; `startLook()` (§12, §11.3) | 3 |
| The composer's model; the consequence line's words, with §14's "take-over consequence text" unit tests (§6.3, §8.2, §9.3, §10, §11.3) | 4 |
| "preview stream in `compose` mode": the zone outlined through `ZoneOutline`, the rest dimmed, the PREVIEW ON SCREEN card and tag, the phone's framing (§7.2, §7.6) | 5 |
| `LookTile` and `LookThumb` (§6.4); the phone's look rows (§8.10) | 6 |
| `ZonePicker` (§6.3) | 7 |
| "composer, … consequence line, transitions, Start / Cancel" on desktop; the URL (§4.3); the keyboard (§8.2); done when "Start a look in ≤ 3 clicks from Live; lights unchanged until Start (mock asserts)" (§13.1); §14's "composer flow" | 8 |
| §8.10's Put a look on, a focused task | 9 |
| Every state on both sizes, compared by eye; §14's keyboard path through Live → composer → Start; axe with the transition list open; §6.4's and §8.10's sizes | 10 |
| §14's performance: the first load within budget, the stage's frame rate | 8 to 10, 12 |
| Review Focus 1 to 5 | 3, 4, 8 |
| CLAUDE.md revised (CLAUDE.md's workflow) | 11 |
| Rebase over master and engine M5, every gate, the PR, the final review | 12 |
| `LookThumb`'s motifs, the editor's preview, Pick lights…, whole-home looks | Hand-off |
