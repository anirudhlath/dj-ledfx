# F5 Web App Looks Library Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/looks` becomes the Looks library of §8.4: a filter bar (search, category tabs with counts, "Only ready now", "New look"), a section per category, and a grid of §6.4 `LookCard`s, each with its `LookThumb` motif, its star, its running-zone or "From …" overlay, and Put on… / Edit on hover and focus. All 29 motifs come from `reference/Looks.html`, and the tempo and audio ones follow the live beat clock. Done when the mock's `library` scenario matches `Looks.png` side by side, and a beat thumb in the browser moves at the live tempo, holds under `?still`, and rests off screen (§13.1, row M5).

**Architecture:**
- **The handoff, generated.** `npm run design:numbers` already writes `LIVE_SPEC` and `LIVE_RENDER`. F5 adds the sentences of §6.4's `LookCard`, §8.4's grid and §5.4's stand-in tempo to `LIVE_SPEC`, and the card's thumb box to `LIVE_RENDER`. A new extractor, `scripts/looks-extract.ts`, reads `Looks.html`'s 29 motif SVGs and their `t_*` keyframes into `src/looks/looks-render.ts` and `src/looks/looks-render.css`, verbatim. It rewrites only the render's id prefixes, into a slot each thumb fills with its own. It also reads the library state the render draws (its stars, its two saved looks, its running pills, each card's input names), so the mock and the tests use the render's data and never retype it. A node test fails when either file is stale.
- **The thumbs.** `LookThumb` draws its look's motif as one inline `<svg class="tb">`, starting paused. `thumb-writer.ts` is one animation-frame loop, like `pip-writer.ts`. An ambient motif runs its own CSS loops while on screen. A beat motif (category tempo or audio) stays paused, and every frame the writer seeks its animations to the beat: the beats elapsed, read from `beatClock`, times one beat of the render's 121.8 BPM keyframes. `use-thumb-motion.ts` registers a thumb only while it intersects the viewport, motion isn't reduced, `live` isn't false and the clock isn't held.
- **The page.** `library-model.ts` is the pure part: tabs, counts, search, sections, input names, running zones, the empty line. `LookCard`, `LibraryFilters` and `LooksPage` draw it from `/api/looks`, `/api/zones`, the live store's `running` and `inputs`, and the URL's `?cat=&q=`. `setStarred()` in `actions.ts` stars a look optimistically, and the latest choice wins. `PageMeta` gains `Context`, a component, for the top bar's "29 looks · 3 running".

**Tech Stack:**
- Unchanged from F10: Vite 8, React 19, TypeScript 5.9 (strict), Tailwind CSS v4, Base UI, react-router 7, zustand 5, TanStack Query 5, MSW, Vitest (jsdom), Playwright with axe.
- The Web Animations API (`Element.getAnimations({ subtree: true })`, `Animation.currentTime`) seeks the beat motifs' CSS animations. `IntersectionObserver` pauses the thumbs off screen.
- No new dependencies. No backend change: everything §8.4's "Data" line asks for is derived on the client from `/api/looks`, `/api/zones`, `/api/running` and `/api/inputs`.

**Spec:**
- `docs/superpowers/specs/2026-09-23-web-app-rebuild-design.md`:
  - §13.1, row M5: "Looks library + all 29 `LookThumb` motifs, stars, filters, "Only ready now"". Done when it "Matches `Looks.png`; thumbs follow the beat clock".
  - §6.4 `LookThumb` and `LookCard`; §8.4 Looks; §4.3's `/looks` row (`?cat=&q=`); §5.4's beat-synced motion and reduced motion; §14 (the bundle budget, contrast).
- The renders, in the main checkout (`/home/anirudhlath/code/private/dj-ledfx/docs/design/web-app/reference/`): `Looks.png` and `Looks.html` (the page, its 31 cards, the hovered Aurora card's scrim). `Live-PutLookOn`, `Phone-PutLookOn`, `State-Nothing-Running` and `Phone-State-Nothing-Running` draw the same thumbs, which F5's motifs change. `Phone-Looks` is F9's (ruling 1).

**What exists** (master at `d5e4931`):
- `/looks` and `/looks/:lookId` are placeholders (`web/src/app/routes.tsx:68-69`, "F5" and "F8"). `LOOKS` is `{ title: 'Looks' }`. The comment at line 13 says the "29 looks · 3 running" line arrives with its data.
- `web/src/looks/look-thumb.tsx` is F4's `LookThumb({ lookId, size: 'tile' | 'row', className?, children? })`: the scene with no motif (F4 ruling 7). `LookTile`, `LookRow` and `NothingRunning` use it.
- `web/src/compose/model.ts` already has `missingInputs()`, `MISSING_SIGNAL`, `lookInputs()`, `CATEGORIES`, `composerLink()` and `locksToHome()`. `use-composer.ts` has `useRunning()` and a private `InputsRead` selector (lines 110-112, 155-158). `web/src/zones/zone-view.ts` has `INPUTS` and `chipsFor()`.
- `api.setStarred(id, starred)` exists (`web/src/api/rest.ts:118`). `MockServer` answers `PUT /api/looks/{look_id}/starred`. There is no action for it.
- `BeatClock` (`web/src/api/beat.ts`) has a private `held`, and `nearWay` and `withinBar` are module-private. The pip writer (`web/src/chrome/pip-writer.ts`) is the model for one frame loop.
- The engine serves the 22 handoff looks with layers, plus six `classic-*` tempo looks with no motif in the handoff (`src/dj_ledfx/looks/builtin.py`). No Home look until M6. It sends no `music` or `homeAssistant` input until M7, so "Only ready now" hides nothing on real data yet (ruling 12).

**Execution:** in a new worktree, `~/code/.worktrees/dj-ledfx/web-f5`, on branch `feature/web-f5-looks-library`, from `origin/master` (Before Task 1), by the method the owner picks.
- Tasks 1 to 12 run in order. Task 12 opens the PR and never merges it.
- No review runs beyond the one the owner's method runs. Every finding a review raises is fixed, Minor ones included.
- F5 has no real-light step. Engine M6 is planned beside it, and either may merge first (Task 12).

**How to read the code.**
- Steps give each function's signature, each test's name and assertions, and the values the spec or a render pins. The bodies are the builder's.
- Three kinds of file are never written by hand: `web/src/design/live-numbers.ts`, `web/src/looks/looks-render.ts` and `web/src/looks/looks-render.css`, which `npm run design:numbers` writes; and the screenshot baselines under `web/e2e/*-snapshots/`, which Playwright records after a comparison by eye (Task 10).

---

## Global Constraints

Every task's requirements include this section. Quotes are the spec's or CLAUDE.md's own words.

**Source of truth**
- CLAUDE.md, "Web App Design": "The Claude Design handoff is the only source of design truth." "Behaviour, structure, data contract and copy: the web app spec. Look and layout: the reference renders." "Use `tokens.css`, `icons.ts`, `looks.json` and `home.json` as they are … Never retype a token, colour, size, icon path or look description, and never restate design values in docs or in this file."
- "Before each web app task, re-read the spec sections and look at the renders that the task names." Each task's Step 1 names them. View each PNG once per task and write down what you see. Where the picture can't settle something, read the HTML beside it.
- A design value is a token utility first, a Tailwind spacing class second, a generated number (`LIVE_SPEC`, `LIVE_RENDER`) third. Only then is it an arbitrary value, with a comment naming the render it comes from (as F4's `text-[11.5px]` does).
- `web/src/design/live-numbers.ts`, `web/src/looks/looks-render.ts` and `.css` are generated (`npm run design:numbers`). They are never hand-edited.

**Public repo**
- No LAN addresses, MACs, light names or models, room names from this home, SSIDs, AI model names, or this home's location, in code, tests, commits or the PR. Tests use 127.0.0.1, `test-lamp`, and the demo home (`home.json`) by its ids. Names come from the fixtures, never typed.

**Tooling**
- uv only (`uv run …`, `uv sync --extra web`); npm in `web/`.
- TDD: each test is written first and seen to fail, for the reason the step names.
- During a task, run only that task's test files: `cd web && npx vitest run <files>`. Run the whole gate once, in Task 12.
- Never start, stop or rebuild `dj-ledfx-app-1`, and never run the real engine. `--demo` is not lamp-safe.

**Web app rules (CLAUDE.md, Code Style and Gotchas)**
- A `.tsx` file exports only components; hooks and helpers live in `.ts` files. The React Compiler lint rules apply.
- `cx()` joins classes and doesn't merge them: never pass two classes that set one property.
- A control calls `actions.ts`, never `api.*`. A failure is said aloud with `failureText(action, error)` through `useAnnounce()`.
- §5.4: "Beat-synced motion must follow the real beat clock, never a CSS timer." "Look thumbnails animate continuously … Pause thumbnails that are off screen." "`prefers-reduced-motion`: stop … thumbnail loops and live-dot pulses."
- §7.5's "No React state per frame": the thumb writer writes the DOM, and React never redraws for a beat.

---

## Decisions already made

Each is a gap the spec leaves that a builder could settle. The owner checks them in review. **[owner]** marks a ruling written around the recommendation in the report's owner questions, and **[owner's answer, 2026-11-11]** one the owner has since answered.

1. **The phone is reflowed, not Phone-Looks.** **[owner]** Below the phone breakpoint, the page is the desktop page in two columns, with the filter bar wrapping and no header context. `Phone-Looks.png` ("Starred first, 2-column grid", §4.3) is F9's, since §13.1's M9 row is "phone layouts for every screen". *Why:* it keeps F5 to Looks.png. *Cost:* the phone's Looks is plain until F9.
2. **The motifs are generated, not hand-ported.** §6.4 says to "port them as small canvas or SVG components keyed by `looks.json` `thumbnail` ids". F5 ports them as one SVG component that draws each motif's markup verbatim from `looks-render.ts`, keyed by `thumbnail`. *Why:* the handoff is used verbatim, and a node test catches a stale copy. *Cost:* about 10 KB of gzipped JS in the first load (measured in Task 10, within §14's budget).
3. **Ids are per thumb.** Looks.html prefixes each motif's ids with `lk<n>` (built-in) or `mn<n>` (saved). The extractor replaces the prefix after `id="`, `url(#` and `href="#` with `MOTIF_SLOT`. Each `LookThumb` fills the slot with its own `useId()`, so two thumbs of one look never share a gradient.
4. **Which motifs follow the beat.** A motif follows the beat when its look's category in `looks.json` is `tempo` or `audio` ("Tempo and audio motifs must follow the live beat clock"). The writer keeps their CSS animations paused and seeks each to `beatMs(τ)`, where τ is the beats elapsed and `beatMs(b) = b × 60000 / LIVE_SPEC.mockBpm`. That is §5.4's "The mocks use CSS keyframes at 121.8 BPM only as a stand-in": a keyframe one beat long at 121.8 lasts one beat at any tempo. τ starts at the clock's place in the bar when the loop starts, and adds the beats each frame moves (`nearWay`, so a re-anchor never runs the motif backwards a bar). Durations are not snapped: Drop's and Tide's are not whole beats, and they keep the render's proportion to the beat.
5. **Ambient, home and firmware motifs run their CSS loops** while on screen. §5.4 forbids a CSS timer only for beat-synced motion.
6. **A held, stopped or stale clock holds the beat thumbs.** Under `?still` (`beatClock.held`), no thumb is registered, so every thumb stays paused at its authored moment and a screenshot is the same every run. A stopped or stale beat moves τ no further, as the pips rest (F3 decision 4).
7. **A look with no motif is the bare scene.** **[owner's answer, 2026-11-11]** The six classics (`classic-*`) and any thumbnail id the handoff doesn't have draw F4's scene with no motif, and never register with the writer.
8. **`live?: boolean`, default true** (§6.4's interface). `live={false}` keeps the motif at its authored moment. No caller passes it yet. A real preview is a later milestone's.
9. **Counts are the render's.** Looks.png's tabs read "All 29 … Mine 2" over 31 cards. So All, and the header's "N looks", count the built-in looks. Each category tab counts its built-ins, Starred counts every starred look (saved ones included), and Mine counts the saved ones (`builtIn === false`). Counts ignore the search and the switch. The header's "M running" is the number of zones in `/api/running`.
10. **Sections.** The tab, the search and the switch filter the looks. What's left is grouped into `looks.json`'s categories, in its order, then Mine, and a section with nothing in it is left out. Starred keeps the category sections. A category tab is its one section. A saved look shows only in Mine, whatever its category. A `cat` the app doesn't know (`?cat=calm`) is All, and so is no `cat`.
11. **Search** (§8.4 "looks, layers, inputs") matches, ignoring case, a look's name, its layers' names and its inputs' names (the card's and `INPUTS`' labels). It doesn't match the description. It searches within the chosen tab.
12. **"Only ready now"** hides a look whose `missingInputs()` isn't empty (F4 ruling 8: only what the server serves is judged). On today's engine it hides nothing, until M7 serves music and Home Assistant. It lives in the page's state, not the URL (§4.3 names only `cat` and `q`).
13. **The running pill.** One zone shows "● {zone}", as Looks.html draws it. Two or more show "● {first} +{n}", and the words a screen reader hears name them all ("Running on A and B"). The zones are those in `/api/running` whose `lookId` is the look, named from `/api/zones`, in running's order. A zone that `/api/zones` doesn't name is left out. A look in an M6 overlay gets no pill: Live's overlay card is M6's.
14. **"From …"** is the parent's name (`derivedFrom`), in the same pill without the dot. A parent that's gone shows no pill.
15. **The card's ways in.** The name is a link to `/looks/:id`, stretched over the card ("Clicking a card opens the editor"; F8's placeholder for now). The scrim shows on `group-hover` and `group-focus-within`. Put on… is `composerLink(null, look.id)`, so a home look locks to Whole home in the composer (F4). Edit links to `/looks/:id` with `tabIndex={-1}`, since the name link is its keyboard path. The star is its own button above the stretched link.
16. **Stars.** The star is labelled "Star {name}" or "Unstar {name}", with `aria-pressed`, as Looks.html labels it. `setStarred()` writes the choice into the `['looks']` cache at once, then the server's answer. The latest choice for a look wins: an earlier request's answer, or its failure, never overwrites a later choice. A failure puts the look back and is said aloud with `failureText('star {name}' | 'unstar {name}', error)`.
17. **New look** is a secondary button linking to `/looks/new`, which F8's placeholder route already catches.
18. **Input names are Looks.html's.** A card lists each input as `INPUTS`' icon and label, except Home Assistant, which Looks.html writes "HA". A look with none says "No input". A missing input is in `signal`. A test pins every built-in look's names to the render's.
19. **The mock gets a `library` scenario:** the hero, plus Looks.html's six stars and two saved looks, read from `LIBRARY`. The hero is unchanged, so F4's composer baselines and tests (which rely on "No starred looks yet.") hold.
20. **The grid.** On desktop the grid is `repeat(auto-fill, minmax(LIVE_SPEC.lookCard.px px, 1fr))`. At the 1288 px content width that is §8.4's 6 columns (6 × 201 + 5 × 16 ≤ 1288), and fewer between the breakpoints. The gaps are `gap-y-7 gap-x-4`, pinned to §8.4's 28/16 by a test. Firmware and Mine share the last row as Looks.html draws it: side by side, `gap-12`, fixed-width cards, no count, wrapping when they don't fit.
21. **The empty line**, in this order: a search with no match says `No looks match “{q}”.` (the composer's words). The switch hiding everything says `No looks are ready now.` Otherwise: `No starred looks yet.`, `No saved looks yet.`, `No {category} looks yet.` or `No looks yet.` Looks that fail to load show `EmptyState` with `failureText('load the looks', error)` and Try again. The page adds no `role="status"`: `hold.test.tsx` finds the announcer by that role.
22. **The header context is desktop-only.** `PageMeta.Context`, a component, wins over `context` on the desktop top bar. The phone keeps its plain title until F9.
23. **The thumbs change three screens.** The composer's tiles and rows, and Nothing running's recent looks, use `LookThumb`. Their baselines are re-recorded in Task 10, each compared by eye with its render first.

---

## Review Focus

1. **A `cat` the app doesn't know, or none** (`?cat=calm` from an old link, `?cat=`, no `cat`): the page shows All with All pressed, and a tab click replaces the bad value. Tests: Task 5 (`readTab`), Task 9 (the page at `/next/looks?cat=calm&q=fire`).
2. **A look running on several zones, or on a zone `/api/zones` doesn't name:** the pill reads "● {first} +{n}", a screen reader hears every name, and an unnamed zone is left out rather than drawn as an id. Tests: Task 5 (`runningOn`, `runningPill`), Task 7 (the card).
3. **A star that fails, or two quick toggles answered out of order:** the card ends at the last choice, an earlier answer never overwrites it, a failure puts back only a look nobody has touched since, and the failure is announced. Tests: Task 7 (`setStarred` in `actions.test.ts`, and the card's announcement).
4. **A look with no motif** (a `classic-*` look, an unknown thumbnail, `thumbnail: null`): the bare scene, no throw, never registered with the writer. Tests: Task 3, Task 4.
5. **Thumbs off screen, under reduced motion, or with the clock held, stopped or stale:** nothing is written, ambient thumbs stay paused, and beat thumbs hold. A thumb coming back on screen goes on from the shared τ without a jump. Tests: Task 4, Task 10 (in the browser).

---

## File Structure

| File | Task | Responsibility |
|---|---|---|
| `web/scripts/design-extract.ts` | 1, 2 | `LIVE_ENTRIES` `lookCard`, `looksPage`, `mockBpm`. `LIVE_RENDERS` gains `reference/Looks.html`, so its pin is checked. `LIVE_RENDER.lookCard`. `Handoff.looks` (looks.json's text) |
| `web/scripts/looks-extract.ts` | 2 | Create. Reads Looks.html's motifs, keyframes and library state, and checks them against looks.json and the PutLookOn renders |
| `web/scripts/design-numbers.ts` | 2 | Also writes `src/looks/looks-render.ts` and `.css` |
| `web/src/design/live-numbers.ts` | 1 | Generated |
| `web/src/looks/looks-render.ts`, `looks-render.css` | 2 | Generated: `MOTIF_SLOT`, `MOTIFS`, `LOOK_CATEGORIES`, `LIBRARY`; the `.tb` rules and `t_*` keyframes |
| `web/src/looks/motif.ts` | 3 | Create. `motifFor()`, `instanceMarkup()` |
| `web/src/looks/look-thumb.tsx` | 3, 4 | Draws the motif; `'card'` size; `live` |
| `web/src/styles/app.css` | 3 | `.tb[data-paused] * { animation-play-state: paused }` |
| `web/src/api/beat.ts` | 4 | `get held()`, `export const nearWay` |
| `web/src/looks/thumb-writer.ts` | 4 | Create. One frame loop over the registered thumbs |
| `web/src/looks/use-thumb-motion.ts` | 4 | Create. Registers a thumb while it may move |
| `web/src/test/intersection.ts`, `web/src/test/setup.ts` | 4 | Create a fake `IntersectionObserver`, installed and reset for every test |
| `web/src/looks/library-model.ts` | 5 | Create. The pure part of the page |
| `web/src/api/mocks/scenarios.ts` | 6 | The `library` scenario |
| `web/src/api/actions.ts` | 7 | `setStarred()` |
| `web/src/looks/look-card.tsx` | 7 | Create. §6.4 `LookCard` |
| `web/src/looks/library-filters.tsx` | 8 | Create. §8.4's filter bar |
| `web/src/compose/use-composer.ts` | 9 | Exports `useInputsRead()` and `InputsRead` |
| `web/src/pages/looks.tsx` | 9 | Create. `LooksPage`, `LooksContext` |
| `web/src/app/page-meta.ts`, `web/src/app/routes.tsx`, `web/src/shell/app-shell.tsx` | 9 | `PageMeta.Context`; `/looks` is the page |
| `web/e2e/looks.spec.ts` | 10 | Create. The screenshot against Looks.png, the beat in the browser, axe |
| `CLAUDE.md` | 11 | What F5 adds |

---

## Before Task 1

- [ ] **Step 1: Make the worktree**

```bash
git -C /home/anirudhlath/code/private/dj-ledfx fetch origin
git -C /home/anirudhlath/code/private/dj-ledfx worktree add -b feature/web-f5-looks-library /home/anirudhlath/code/.worktrees/dj-ledfx/web-f5 origin/master
W=/home/anirudhlath/code/.worktrees/dj-ledfx/web-f5; cd "$W"
grep -q 'milestone="F5"' web/src/app/routes.tsx && echo "F5 isn't here"
git log --oneline -3
```

Expected: "F5 isn't here". The log's newest commit is master's.

- [ ] **Step 2: Install, and check the pins**

```bash
uv sync --extra web
(cd web && npm ci)
(cd /home/anirudhlath/code/private/dj-ledfx/docs/design/web-app && sha256sum -c HANDOFF.sha256 2>/dev/null \
  | grep -E 'reference/(Looks|Phone-Looks|Live-PutLookOn|Phone-PutLookOn|State-Nothing-Running|Phone-State-Nothing-Running)\.(html|png): ' | grep -v ': OK$'; echo "renders checked")
```

Expected: "renders checked" with no line before it. A render that fails its pin stops the plan: tell the owner.

- [ ] **Step 3: Record the baselines**

```bash
(cd web && npm test 2>&1 | grep -E 'Test Files|Tests ' && npm run lint && npx tsc -b && echo "tsc ok" && npm run build 2>&1 | tail -1)
for i in $(seq 1 60); do [ "$(ss -ltn | grep -cE ':(4174|4175) ')" = 0 ] && break; sleep 10; done; ss -ltn | grep -cE ':(4174|4175) '
(cd web && npx playwright install chromium && npm run e2e 2>&1 | tail -3)
```

Expected: everything passes. Write down the Vitest counts, the build's `…/web/dist: no mocks, <n> KB of gzipped JS`, and the e2e counts. The port check prints `0`.

---

### Task 1: The Looks page's numbers, from the spec and Looks.html

**Files:**
- Modify: `web/scripts/design-extract.ts` (`LIVE_ENTRIES`, `LIVE_RENDERS`, `extractLiveRender`)
- Regenerate: `web/src/design/live-numbers.ts`
- Test: `web/src/stage/design-numbers.node.test.ts`

**Interfaces:**
- Consumes: `extract()`, `same()`, `n()` and the `edited()` test helper, as they are.
- Produces:
  - `LIVE_SPEC.lookCard: { px: number; columns: number; radiusPx: number; namePx: number; descriptionPx: number }`
  - `LIVE_SPEC.looksPage: { sectionNamePx: number; columns: number; rowGapPx: number; columnGapPx: number }`
  - `LIVE_SPEC.mockBpm: number`
  - `LIVE_RENDER.lookCard: { thumb: { width: number; height: number } }`

- [ ] **Step 1: Read** §6.4 (`LookThumb`, `LookCard`), §8.4 and §5.4. View `Looks.png` once and write down what you see. In `Looks.html`, read one `<article>`: the thumb box's `<div>`, the `<svg class="tb ">` and the name row.

- [ ] **Step 2: Write the failing tests**

```ts
const tokenPx = (name: string) => new RegExp(`${name}:\\s*([\\d.]+)px`).exec(handoff.tokens)?.[1]

// §6.4: "LookCard (grid, 201 px at 6 columns): thumb (radius 10, line border), serif 20 name …, two-line description (12 text-3)";
// §8.4: "6-column grid of LookCards, 28/16 px gaps". The card draws them with tokens.css's own sizes.
it("read §6.4's LookCard and §8.4's grid, in tokens.css's own sizes", () => {
  expect(LIVE_SPEC.lookCard.columns).toBe(LIVE_SPEC.looksPage.columns)
  expect(String(LIVE_SPEC.lookCard.radiusPx)).toBe(tokenPx('--radius-tile'))
  expect(String(LIVE_SPEC.lookCard.namePx)).toBe(tokenPx('--text-display-xs'))
  expect(String(LIVE_SPEC.lookCard.descriptionPx)).toBe(tokenPx('--text-meta'))
})
```

In `'name the sentence that moved'` (the existing `extractLive` failure test), add:

```ts
expect(() => extractLive(handoff.spec.replace('**`LookCard`** (grid', '**`LookCard`** (list'))).toThrow(/§6\.4 LookCard/)
expect(() => extractLive(handoff.spec.replace('Sections per category: serif', 'Sections per category: sans'))).toThrow(/§8\.4 Looks/)
expect(() => extractLive(handoff.spec.replace('CSS keyframes at', 'CSS keyframes near'))).toThrow(/§5\.4/)
```

And beside `'name the render whose thumb moved'`:

```ts
it.runIf(handoff.read !== null)("name the render whose card's thumb box moved", () => {
  // One card's box a pixel taller: the 31 cards no longer agree.
  const taller = (html: string) => html.replace(/(height: )(\d+)(px; border-radius: \d+px; overflow: hidden; border: 1px solid)/, (_, a: string, h: string, b: string) => `${a}${Number(h) + 1}${b}`)
  expect(() => extractLiveRender(edited('Looks', taller))).toThrow(/Looks\.html's card thumb draws it two ways/)
  // Every card's box clipped another way: none reads.
  const clipped = (html: string) => html.replaceAll('overflow: hidden; border: 1px solid', 'overflow: clip; border: 1px solid')
  expect(() => extractLiveRender(edited('Looks', clipped))).toThrow(/Looks\.html's card thumb no longer reads/)
})
```

Extend `'name the renders that draw a thumb two ways'` so `Looks.html`'s `<svg class="tb ">` is a third render of the one scene: `taller` applied to `Looks` throws `/Live-PutLookOn\.html's thumb and Looks\.html's thumb draw the scene two ways/`.

- [ ] **Step 3: Run them to see them fail**

Run: `cd web && npx vitest run src/stage/design-numbers.node.test.ts`
Expected: FAIL. `LIVE_SPEC.lookCard` is undefined, and the edited renders don't throw.

- [ ] **Step 4: Add the entries and the render read**

In `LIVE_ENTRIES`:
- `lookCard`: `where: '§6.4 LookCard'`, `/\*\*`LookCard`\*\* \(grid, (\d+) px at (\d+) columns\): thumb \(radius (\d+), line border\), serif (\d+) name \+ star toggle, two-line description \((\d+) text-3\)/`.
- `looksPage`: `where: '§8.4 Looks'`, `/Sections per category: serif (\d+) name, count, one-line blurb \(`looks\.json` `categories`\)\. (\d+)-column grid of `LookCard`s, (\d+)\/(\d+) px gaps/`.
- `mockBpm`: `where: '§5.4'`, `/The mocks use CSS keyframes at ([\d.]+) BPM only as a stand-in/`.

Add `'reference/Looks.html'` to `LIVE_RENDERS`. In `extractLiveRender`, read the card's thumb box with `same(looks, { where: "Looks.html's card thumb", pattern: /<div style="position: relative; width: (\d+)px; height: (\d+)px; border-radius: \d+px; overflow: hidden; border: 1px solid #[0-9a-f]{6}; box-sizing: border-box">/ })` into `lookCard.thumb`. Check Looks.html's `thumbPattern` scene against the other two, as they are checked against each other.

- [ ] **Step 5: Regenerate, and run the tests**

Run: `cd web && npm run design:numbers && npx vitest run src/stage/design-numbers.node.test.ts`
Expected: it writes both files, and every test passes. `git diff --stat` shows `live-numbers.ts` gained `lookCard`, `looksPage` and `mockBpm` in `LIVE_SPEC`, and `lookCard` in `LIVE_RENDER`. Nothing else moved.

- [ ] **Step 6: Commit**

```bash
git add web/scripts/design-extract.ts web/src/design/live-numbers.ts web/src/stage/design-numbers.node.test.ts
git commit -m "feat(web): read the Looks page's numbers from the spec and Looks.html"
```

---

### Task 2: The 29 motifs, read from Looks.html

**Files:**
- Create: `web/scripts/looks-extract.ts`
- Modify: `web/scripts/design-extract.ts` (`Handoff.looks`), `web/scripts/design-numbers.ts`
- Generate: `web/src/looks/looks-render.ts`, `web/src/looks/looks-render.css`
- Test: `web/src/looks/looks-render.node.test.ts` (Create)

**Interfaces:**
- Consumes: `ReadText`, `readHandoff()`, Task 1's `LIVE_SPEC.mockBpm`.
- Produces, in the generated `web/src/looks/looks-render.ts` (no imports, `as const`):
  - `MOTIF_SLOT: '@@'`, the placeholder for a thumb's id prefix.
  - `MOTIFS: Record<thumbnail id, { markup: string; beat: boolean }>`, the inner markup of each `<svg class="tb ">`.
  - `LOOK_CATEGORIES`: `looks.json`'s `categories`, verbatim (`{ id, name, blurb }[]`).
  - `LIBRARY: { counts: Record<tab label, number>; starred: string[]; running: Record<look id, string>; inputs: Record<look id, string[]>; mine: { name: string; from: string; description: string }[]; mineBlurb: string; hovered: string }`. All ids are looks.json's. `from` is the parent's id, `running` maps a look to the zone name its pill draws, `inputs` lists each built-in card's input names (`[]` for "No input"), and `hovered` is the card whose scrim is drawn.
- In `web/scripts/looks-extract.ts`:
  - `export interface LooksRender { motifs: Record<string, { markup: string; beat: boolean }>; categories: unknown[]; library: Library; css: string }`
  - `export function extractLooksRender(read: ReadText, looksJson: string): LooksRender`
  - `export function looksRenderSource(render: LooksRender): string` and `export function looksRenderCss(render: LooksRender): string`

- [ ] **Step 1: Read** §6.4 `LookThumb` and §8.4. In `Looks.html`, read the `<style>`'s `.tb` rules and `@keyframes t_*`, two `<article>`s (one tempo, one saved), the tab pills, and the Firmware and Mine headers.

- [ ] **Step 2: Write the failing tests** (`// @vitest-environment node`, `handoff` and `edited()` as in `design-numbers.node.test.ts`)

```ts
describe('the looks render', () => {
  // If this fails, the handoff changed: run `npm run design:numbers` in web/ and commit what it writes.
  it.runIf(handoff.read !== null)('is what Looks.html draws', () => {
    const render = extractLooksRender(handoff.read!, handoff.looks)
    expect({ MOTIFS, LOOK_CATEGORIES, LIBRARY }).toEqual({ MOTIFS: render.motifs, LOOK_CATEGORIES: render.categories, LIBRARY: render.library })
    expect(readFileSync(resolve(import.meta.dirname, 'looks-render.css'), 'utf8')).toBe(looksRenderCss(render))
  })

  it("has looks.json's categories as they are", () => {
    expect(LOOK_CATEGORIES).toEqual(JSON.parse(handoff.looks).categories)
  })

  it('has a motif for every thumbnail in looks.json, and no other', () => {
    const thumbnails = JSON.parse(handoff.looks).looks.map((look: { thumbnail: string }) => look.thumbnail)
    expect(Object.keys(MOTIFS).sort()).toEqual([...thumbnails].sort())
  })

  it("marks the tempo and audio looks' motifs as the beat's, and only those", () => {
    for (const look of JSON.parse(handoff.looks).looks) expect(MOTIFS[look.thumbnail].beat).toBe(['tempo', 'audio'].includes(look.category))
  })

  it("leaves none of the render's ids in a motif: every id, url(#…) and href=\"#…\" starts with the slot", () => {
    for (const { markup } of Object.values(MOTIFS)) {
      expect(markup).not.toMatch(/\b(lk|mn)\d+[a-z]/)
      for (const [, ref] of markup.matchAll(/(?:id="|url\(#|href="#)([^")]*)/g)) expect(ref.startsWith(MOTIF_SLOT)).toBe(true)
    }
  })

  // §5.4: "The mocks use CSS keyframes at 121.8 BPM only as a stand-in." The writer's beatMs() rests on it.
  it("draws the beat motifs at §5.4's stand-in tempo", () => {
    const durations = Object.values(MOTIFS).filter((m) => m.beat).flatMap((m) => [...m.markup.matchAll(/animation: t_\w+ ([\d.]+)s/g)].map((d) => Number(d[1])))
    expect(durations.some((s) => Math.abs(s - 60 / LIVE_SPEC.mockBpm) < 5e-4)).toBe(true)
  })

  it("reads the library Looks.html holds, and its tabs' counts agree with its cards", () => {
    const ids = new Set(JSON.parse(handoff.looks).looks.map((look: { id: string }) => look.id))
    expect(LIBRARY.counts.Starred).toBe(LIBRARY.starred.length) // Looks.html stars no saved look
    expect(LIBRARY.counts.Mine).toBe(LIBRARY.mine.length)
    expect(LIBRARY.counts.All).toBe(ids.size)
    for (const id of [...LIBRARY.starred, ...LIBRARY.mine.map((m) => m.from), ...Object.keys(LIBRARY.running), LIBRARY.hovered]) expect(ids.has(id)).toBe(true)
  })

  it.runIf(handoff.read !== null)('names the look whose ids no longer read', () => {
    const renamed = (html: string) => html.replace('id="lk6', 'id="zz6')
    expect(() => extractLooksRender(edited('Looks', renamed), handoff.looks)).toThrow(/Looks\.html's motif for aurora/)
  })

  it.runIf(handoff.read !== null)('names the render that draws a motif two ways', () => {
    const moved = (html: string) => html.replace(/(<svg class="tb "[^>]*>[\s\S]*?<circle cx=")([\d.]+)/, (_, head: string, x: string) => `${head}${Number(x) + 9}`)
    expect(() => extractLooksRender(edited('Live-PutLookOn', moved), handoff.looks)).toThrow(/Live-PutLookOn\.html draws the motif for \w+ unlike Looks\.html/)
    expect(() => extractLooksRender(edited('Phone-PutLookOn', moved), handoff.looks)).toThrow(/Phone-PutLookOn\.html draws the motif for \w+ unlike Looks\.html/)
  })

  it.runIf(handoff.read !== null)('names the saved look drawn unlike the look it came from', () => {
    const moved = (html: string) => html.replace(/(id="mn1[a-z]+"[\s\S]*?<circle cx=")([\d.]+)/, (_, head: string, x: string) => `${head}${Number(x) + 9}`)
    expect(() => extractLooksRender(edited('Looks', moved), handoff.looks)).toThrow(/Looks\.html's saved look .+ is drawn unlike \w+/)
  })
})
```

- [ ] **Step 3: Run them to see them fail**

Run: `cd web && npx vitest run src/looks/looks-render.node.test.ts`
Expected: FAIL. `./looks-render` and `looks-extract.ts` don't exist.

- [ ] **Step 4: Write the extractor**

`Handoff` gains `looks: string`, looks.json's text, read in `readHandoff()` beside `tokens`.

`extractLooksRender(read, looksJson)` reads `reference/Looks.html`, `reference/Live-PutLookOn.html` and `reference/Phone-PutLookOn.html`. Each failure throws `design numbers: …` and names the render and the look.
- **Cards.** Each `<article>` is a card. Its `<h3>` is its name. A name in looks.json is that look. A card inside the section whose `<h2>` is "Mine" is a saved look. Any other name throws.
- **Motifs.** A card's `<svg class="tb ">` inner markup, verbatim, with its id prefix `(lk|mn)\d+` (the token before the motif's own suffix, which starts with a letter) replaced by `MOTIF_SLOT` after `id="`, `url(#` and `href="#`. If any `(lk|mn)\d+[a-z]` remains, it throws `Looks.html's motif for <id> no longer reads`. Keyed by the look's `thumbnail`. `beat` is the look's category, `tempo` or `audio`.
- **Saved looks.** A saved card's markup, normalised, must equal its parent's (the look its "From …" pill names), or it throws `Looks.html's saved look <name> is drawn unlike <parent id>`.
- **The other renders.** In each PutLookOn render, every tile or row with a `<svg class="tb ">` is matched to its look by its name. Its ids and the Looks.html motif's are both normalised by replacing each svg's longest common id prefix (those renders use other prefixes), and the two must be equal, or it throws `<render> draws the motif for <id> unlike Looks.html`.
- **Library.** `counts`: each tab pill's label and its `<span>` number. `starred`: the cards whose star `aria-pressed="true"`. `running`: each card's pill drawn with the 6 px `livedot` span, keyed by look, holding the pill's text. `inputs`: each built-in card's input names (the spans after its description; "No input" is `[]`). `mine`: each saved card's name, its pill's "From X" parent as an id, and its description. `mineBlurb`: the Mine header's blurb. `hovered`: the card holding the `linear-gradient(to top` scrim.
- **CSS.** The `<style>`'s `.tb …{…}` rules and every `@keyframes t_\w+{…}`, verbatim, in the file's order.

`looksRenderSource()` writes the module with a header saying it's generated by `npm run design:numbers`, and `as const` literals. `looksRenderCss()` writes the same header as a CSS comment, then the rules. `design-numbers.ts` writes both files beside the two it writes.

- [ ] **Step 5: Generate, and run the tests**

Run: `cd web && npm run design:numbers && npx vitest run src/looks/looks-render.node.test.ts src/stage/design-numbers.node.test.ts`
Expected: four files written, and every test passes. `wc -c web/src/looks/looks-render.ts` is about 100 KB. Write it down for Task 10's budget check.

- [ ] **Step 6: Commit**

```bash
git add web/scripts web/src/looks/looks-render.ts web/src/looks/looks-render.css web/src/looks/looks-render.node.test.ts
git commit -m "feat(web): read the 29 look motifs and the library Looks.html draws"
```

---

### Task 3: LookThumb draws its look's motif

**Files:**
- Create: `web/src/looks/motif.ts`, `web/src/looks/motif.test.ts`
- Modify: `web/src/looks/look-thumb.tsx`, `web/src/looks/look-thumb.test.tsx`, `web/src/styles/app.css`

**Interfaces:**
- Consumes: Task 1's `LIVE_RENDER.lookCard.thumb`; Task 2's `MOTIFS`, `MOTIF_SLOT`.
- Produces:
  - `export function motifFor(thumbnail: string | null | undefined): Motif | undefined` and `export function instanceMarkup(motif: Motif, prefix: string): string` (`motif.ts`). `Motif` is `(typeof MOTIFS)[string]`.
  - `ThumbSize = 'tile' | 'row' | 'card'`. `'card'` is `w-full rounded-tile border border-line` at `LIVE_RENDER.lookCard.thumb`'s aspect ratio.
  - `LookThumbProps` gains `live?: boolean` (default `true`). The svg is `<svg class="tb" data-paused data-beat?>`, absolutely filling the scene, with `viewBox` from `LIVE_RENDER.lookThumb`, `preserveAspectRatio="xMidYMid slice"`, and `aria-hidden`.

- [ ] **Step 1: Read** §6.4 `LookThumb`. Look at `Looks.html`'s `<svg class="tb ">` tag and the `.tb` rules.

- [ ] **Step 2: Write the failing tests**

`motif.test.ts`:

```ts
it('fills the slot with the prefix, and leaves no slot behind', () => {
  const markup = instanceMarkup(MOTIFS.aurora, 'tbX')
  expect(markup).not.toContain(MOTIF_SLOT)
  expect(markup).toContain('url(#tbX')
})
it("finds no motif for a thumbnail the handoff doesn't have, or none", () => {
  expect(motifFor('classic-pulse')).toBeUndefined()
  expect(motifFor(null)).toBeUndefined()
  expect(motifFor('aurora')).toBe(MOTIFS.aurora)
})
```

`look-thumb.test.tsx` (`seedRest('hero')` and the `QueryClientProvider` wrapper, as the existing test has them):

```ts
it("draws each looks.json look's motif, paused, and says nothing to a screen reader", () => {
  for (const look of seedRest('hero').looks) {
    const { container, unmount } = renderThumb(look.id, 'card')
    const svg = container.querySelector('svg.tb')!
    expect(svg).toHaveAttribute('data-paused')
    expect(svg.hasAttribute('data-beat')).toBe(MOTIFS[look.thumbnail!].beat)
    expect(svg.closest('[aria-hidden="true"]')).not.toBeNull()
    expect(svg.childElementCount).toBe(new DOMParser().parseFromString(`<svg xmlns="http://www.w3.org/2000/svg">${MOTIFS[look.thumbnail!].markup}</svg>`, 'image/svg+xml').documentElement.childElementCount)
    unmount()
  }
})

// Review Focus 4.
it("draws the bare scene for a look with no motif: a classic, a thumbnail the handoff doesn't have, or none", () => {
  for (const thumbnail of ['classic-pulse', 'not-a-motif', null]) {
    queryClient.setQueryData(queries.looks().queryKey, [{ ...seedRest('hero').looks[0], id: 'x', thumbnail }])
    const { container, unmount } = renderThumb('x', 'tile')
    expect(container.querySelector('svg.tb')).toBeNull()
    expect(container.querySelector('[data-thumb]')).toHaveStyle({ background: LIVE_RENDER.lookThumb.background })
    unmount()
  }
})

it('gives each thumb its own ids, so two of one look share no gradient', () => {
  const { container } = render(wrap(<><LookThumb lookId="aurora" size="card" /><LookThumb lookId="aurora" size="card" /></>))
  const svgs = [...container.querySelectorAll('svg.tb')]
  const ids = svgs.flatMap((svg) => [...svg.querySelectorAll('[id]')].map((el) => el.id))
  expect(new Set(ids).size).toBe(ids.length)
  for (const svg of svgs) for (const [, ref] of svg.innerHTML.matchAll(/url\(#([^)]+)\)/g)) expect(svg.querySelector(`[id="${ref}"]`)).not.toBeNull()
})

it("draws a card's thumb at Looks.html's proportions", () => {
  const { container } = renderThumb('aurora', 'card')
  const { width, height } = LIVE_RENDER.lookCard.thumb
  expect(container.querySelector<HTMLElement>('[data-thumb]')!.style.aspectRatio).toBe(`${width} / ${height}`)
})
```

`renderThumb(lookId, size)` and `wrap(ui)` are local helpers over the existing wrapper. The existing test's comment changes from "until F5 ports them" to F5's.

- [ ] **Step 3: Run them to see them fail**

Run: `cd web && npx vitest run src/looks/motif.test.ts src/looks/look-thumb.test.tsx`
Expected: FAIL. `./motif` doesn't exist and no `svg.tb` is drawn.

- [ ] **Step 4: Draw the motif**

`LookThumb` imports `./looks-render.css`. It reads its look's `thumbnail` as now. With a motif, it draws the svg before `children`, with `dangerouslySetInnerHTML={{ __html: instanceMarkup(motif, prefix) }}`, where `prefix` is `` `tb${useId().replace(/[^\w-]/g, '')}` ``, as `Icon` draws its handoff markup. `app.css` gains, with a comment naming §5.4 and F5 ruling 6:

```css
.tb[data-paused] * { animation-play-state: paused; }
```

Update the file's header comment: the motifs are here, and `live` is §6.4's.

- [ ] **Step 5: Run the tests, and the callers'**

Run: `cd web && npx vitest run src/looks src/compose src/live/nothing-running`
Expected: PASS. The composer's and Nothing running's tests don't look inside a thumb.

- [ ] **Step 6: Commit**

```bash
git add web/src/looks web/src/styles/app.css
git commit -m "feat(web): LookThumb draws its look's motif from Looks.html"
```

---

### Task 4: The thumbs follow the beat clock, on screen only

**Files:**
- Create: `web/src/looks/thumb-writer.ts`, `web/src/looks/thumb-writer.test.ts`, `web/src/looks/use-thumb-motion.ts`, `web/src/test/intersection.ts`
- Modify: `web/src/api/beat.ts`, `web/src/api/beat.test.ts`, `web/src/test/setup.ts`, `web/src/looks/look-thumb.tsx`, `web/src/looks/look-thumb.test.tsx`

**Interfaces:**
- Consumes: `beatClock` (`@/api/live`), `clientNow()`, `liveStore` (its `beat.stale`), `useReducedMotion()` (`@/lib/use-media-query`), Task 1's `LIVE_SPEC.mockBpm`, Task 3's svg.
- Produces:
  - `BeatClock.held: boolean` (a getter), and `export const nearWay` from `beat.ts`.
  - `export interface ThumbMotion { svg: SVGSVGElement; beat: boolean }`, `export function registerThumb(thumb: ThumbMotion): () => void` and `export const beatMs = (beats: number): number` (`thumb-writer.ts`).
  - `export function useThumbMotion(svg: RefObject<SVGSVGElement | null>, beat: boolean | undefined, live: boolean): void` (`use-thumb-motion.ts`). `beat` is `undefined` with no motif.
  - `installIntersectionObserver()`, `intersect(element: Element, visible: boolean)`, `resetIntersectionObservers()` (`src/test/intersection.ts`), as `src/test/resize.ts` does for `ResizeObserver`.

- [ ] **Step 1: Read** §5.4 and §6.4 `LookThumb`. Read `pip-writer.ts` and its test: the frame loop, `seedLive()` and the fake timers.

- [ ] **Step 2: Write the failing tests**

`beat.test.ts`:

```ts
it('says whether it holds the beat (?still)', () => {
  const clock = new BeatClock()
  expect(clock.held).toBe(false)
  clock.hold()
  expect(clock.held).toBe(true)
})
```

`thumb-writer.test.ts` (`vi.useFakeTimers()`, `seedLive()`). `beatSvg()` and `ambientSvg()` build an `<svg>` whose `getAnimations` is stubbed to return two `{ currentTime: number | null }` objects:

```ts
it("seeks a beat thumb to the beat: the hero's, a quarter into beat 2, is 1.25 beats in", () => {
  seedLive('hero')
  const svg = beatSvg()
  registerThumb({ svg, beat: true })
  vi.advanceTimersByTime(20)
  for (const animation of svg.getAnimations({ subtree: true })) expect(animation.currentTime).toBeCloseTo(beatMs(1.25), -1)
})

it("moves a beat thumb at the live tempo: 1000 ms at 60.9 BPM is 500 ms of the render's 121.8", () => {
  seedLive('hero')
  // beatClock.receive() a running beat at LIVE_SPEC.mockBpm / 2, as seedLive() feeds the hero's (src/test/live.ts)
  const svg = beatSvg()
  registerThumb({ svg, beat: true })
  vi.advanceTimersByTime(20)
  const before = svg.getAnimations({ subtree: true })[0].currentTime as number
  vi.advanceTimersByTime(1000)
  expect((svg.getAnimations({ subtree: true })[0].currentTime as number) - before).toBeCloseTo(500, -1)
})

// Review Focus 5.
it('holds a beat thumb while the beat stops or goes stale, and goes on from there', () => {
  // stopped: a beat message with playing false; stale: liveStore's beat.stale true. currentTime stays put over 1000 ms,
  // and once the beat runs again it moves on from that value, without a jump.
})

it('lets an ambient thumb run while it is registered, and pauses it again when it goes', () => {
  const svg = ambientSvg()
  const off = registerThumb({ svg, beat: false })
  expect(svg.hasAttribute('data-paused')).toBe(false)
  off()
  expect(svg.hasAttribute('data-paused')).toBe(true)
})

it('samples the clock once a frame for every thumb, and stops asking for frames when the last one goes', () => {
  const sample = vi.spyOn(beatClock, 'sample')
  const offs = [beatSvg(), beatSvg(), beatSvg()].map((svg) => registerThumb({ svg, beat: true }))
  vi.advanceTimersByTime(17)
  expect(sample).toHaveBeenCalledTimes(1)
  offs.forEach((off) => off())
  const frame = vi.spyOn(window, 'requestAnimationFrame')
  vi.advanceTimersByTime(100)
  expect(frame).not.toHaveBeenCalled()
})
```

`look-thumb.test.tsx` (through `useThumbMotion`):

```ts
it('runs a thumb only while it is on screen', () => {
  const svg = renderThumb('aurora', 'card').container.querySelector('svg.tb')!
  expect(svg).toHaveAttribute('data-paused')
  act(() => intersect(svg, true))
  expect(svg).not.toHaveAttribute('data-paused')
  act(() => intersect(svg, false))
  expect(svg).toHaveAttribute('data-paused')
})

it('keeps every thumb still under reduced motion, with the beat held (?still), and with live={false}', () => {
  // Three renders, each on screen (intersect true): setReducedMotion(true); beatClock.hold(); <LookThumb live={false} />.
  // Each svg keeps data-paused, and a stubbed getAnimations' currentTime stays null after 500 ms.
})

it('registers nothing for a look with no motif', () => {
  // A classic: no svg, so nothing to observe; IntersectionObserver.observe is never called.
})
```

`setup.ts` calls `installIntersectionObserver()` beside `installResizeObserver()`, and `resetIntersectionObservers()` after each test. `BeatClock`'s `held` is reset by `resetDataLayer()`, or by the test that holds it, whichever the existing reset does for the clock (read `resetDataLayer()` and say which in the commit).

- [ ] **Step 3: Run them to see them fail**

Run: `cd web && npx vitest run src/api/beat.test.ts src/looks/thumb-writer.test.ts src/looks/look-thumb.test.tsx`
Expected: FAIL. `held` is undefined, `./thumb-writer` doesn't exist, and the thumbs never lose `data-paused`.

- [ ] **Step 4: Write the writer and the hook**

`thumb-writer.ts`, with a header comment naming §5.4 and rulings 4 to 6: a module-level set of thumbs, and one `requestAnimationFrame` loop that runs while the set isn't empty.
- On the first frame of a run, τ is the place in the bar, `sample.beatInBar + sample.beatPhase`.
- On each frame, sample `beatClock` once at `clientNow()`. If the sample is running and `liveStore.getState().beat?.stale` isn't true, add `nearWay(now − last)` of the place in the bar to τ.
- Write `beatMs(τ)` to the `currentTime` of every animation of every beat thumb. `getAnimations({ subtree: true })` is read once when a thumb registers. Leave `data-paused` on a beat thumb: CSS keeps it paused and the writer seeks it.
- An ambient thumb has `data-paused` removed when it registers and put back when it goes.
- `beatMs(beats)` is `beats * 60000 / LIVE_SPEC.mockBpm`.

`useThumbMotion` is a `useLayoutEffect` with an `IntersectionObserver` on the svg. It calls `registerThumb` while the svg intersects, and only when `beat !== undefined && live && !reducedMotion && !beatClock.held`. Cleanup unregisters and disconnects. `LookThumb` calls it with a ref on its svg.

- [ ] **Step 5: Run the tests**

Run: `cd web && npx vitest run src/api/beat.test.ts src/looks src/chrome/pip-writer.test.ts src/compose src/live`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/src/api/beat.ts web/src/api/beat.test.ts web/src/looks web/src/test
git commit -m "feat(web): the look thumbs follow the beat clock, and rest off screen"
```

---

### Task 5: The library's model

**Files:**
- Create: `web/src/looks/library-model.ts`, `web/src/looks/library-model.test.ts`

**Interfaces:**
- Consumes: `Look`, `RunningZone`, `Zone`, `Inputs`, `Id`, `InputKind` (`@/api/contract`); `missingInputs()`, `MissingInput` (`@/compose/model`); `INPUTS` (`@/zones/zone-view`); Task 2's `LOOK_CATEGORIES`, `LIBRARY`.
- Produces:
  - `export type LibraryTab = 'all' | 'starred' | Look['category'] | 'mine'`
  - `export const LIBRARY_TABS: readonly { id: LibraryTab; label: string }[]`: All, Starred, then `LOOK_CATEGORIES`' names, then Mine.
  - `export function readTab(cat: string | null): LibraryTab`
  - `export function tabCounts(looks: readonly Look[]): Record<LibraryTab, number>` (ruling 9)
  - `export function searchLooks(looks: readonly Look[], query: string): Look[]` (ruling 11)
  - `export interface LibraryFilter { tab: LibraryTab; query: string; readyOnly: boolean; inputs: Pick<Inputs, 'music' | 'homeAssistant'> | null }`
  - `export interface LibrarySection { id: Look['category'] | 'mine'; name: string; blurb: string; looks: Look[]; counted: boolean; lastRow: boolean }`
  - `export function librarySections(looks: readonly Look[], filter: LibraryFilter): LibrarySection[]` (ruling 10). `counted` and `lastRow` are false and true for Firmware and Mine. Mine's blurb is `LIBRARY.mineBlurb`.
  - `export interface CardInput { kind: InputKind; name: string; icon: IconName; missing: boolean }` and `export function cardInputs(look: Look, missing: readonly MissingInput[]): CardInput[]` (ruling 18)
  - `export function runningOn(lookId: Id, running: readonly RunningZone[], zones: readonly Zone[]): string[]` and `export function runningPill(names: readonly string[]): { shown: string; spoken: string } | null` (ruling 13)
  - `export function parentName(look: Look, looks: readonly Look[]): string | null` (ruling 14)
  - `export function emptyText(filter: Pick<LibraryFilter, 'tab' | 'query' | 'readyOnly'>): string` (ruling 21)
  - `export function looksContext(looks: readonly Look[], running: readonly RunningZone[]): string`: "{All's count} looks · {zones} running".

- [ ] **Step 1: Read** §8.4 and §6.4 `LookCard`. In `Looks.html`, read the tab pills and one card's inputs.

- [ ] **Step 2: Write the failing tests.** Looks come from `buildScenario('library')` once Task 6 lands. Until then, use `seedRest('hero').looks` with a star and a saved look made in the test from a fixture (`{ ...fixture, id: 'mine-1', builtIn: false, derivedFrom: fixture.id }`). Task 6 switches them.

```ts
// Review Focus 1.
it("reads a cat it doesn't know, or none, as All", () => {
  expect(readTab(null)).toBe('all')
  expect(readTab('')).toBe('all')
  expect(readTab('calm')).toBe('all')
  for (const { id } of LIBRARY_TABS) expect(readTab(id)).toBe(id)
})

it('counts as Looks.png does: All the built-ins, Mine the saved ones, Starred every star', () => {
  const counts = tabCounts(looks)
  expect(counts.all).toBe(looks.filter((l) => l.builtIn).length)
  expect(counts.mine).toBe(looks.filter((l) => !l.builtIn).length)
  expect(counts.starred).toBe(looks.filter((l) => l.starred).length)
  for (const { id } of LOOK_CATEGORIES) expect(counts[id]).toBe(looks.filter((l) => l.builtIn && l.category === id).length)
})

it("finds a look by its name, a layer's name or an input's, in any case, and not by its description", () => {
  const [look] = looks.filter((l) => (l.layers ?? []).length > 0)
  expect(searchLooks(looks, look.name.toUpperCase())).toContain(look)
  expect(searchLooks(looks, look.layers![0].name)).toContain(look)
  expect(searchLooks(looks, 'HA').every((l) => (l.uses ?? []).includes('home-assistant'))).toBe(true)
  expect(searchLooks(looks, look.description!.split(' ').slice(2, 5).join(' '))).not.toContain(look)
})

it("groups the looks into looks.json's categories in its order, then Mine, leaving out an empty section", () => {
  const sections = librarySections(looks, { tab: 'all', query: '', readyOnly: false, inputs: null })
  expect(sections.map((s) => s.id)).toEqual([...LOOK_CATEGORIES.map((c) => c.id).filter((id) => looks.some((l) => l.builtIn && l.category === id)), 'mine'])
  expect(sections.filter((s) => s.lastRow).map((s) => s.id)).toEqual(['firmware', 'mine'])
  expect(sections.filter((s) => !s.counted).map((s) => s.id)).toEqual(['firmware', 'mine'])
  expect(sections.find((s) => s.id === 'mine')!.looks.every((l) => !l.builtIn)).toBe(true)
})

it('keeps the category sections on Starred, and one section on a category tab', () => { /* … */ })

it("hides the looks waiting for an input with Only ready now: inputs-down's music and Home Assistant", () => {
  const { inputs } = buildScenario('inputs-down')
  const shown = librarySections(looks, { tab: 'all', query: '', readyOnly: true, inputs }).flatMap((s) => s.looks)
  expect(shown).toEqual(looks.filter((l) => missingInputs(l, inputs).length === 0))
  expect(shown.length).toBeLessThan(looks.length)
})

it("names each look's inputs as Looks.html does, with no input as none", () => {
  for (const look of looks.filter((l) => l.builtIn)) expect(cardInputs(look, []).map((i) => i.name)).toEqual(LIBRARY.inputs[look.id])
})

it('marks a missing input', () => {
  const [look] = looks.filter((l) => (l.needs ?? []).includes('music'))
  expect(cardInputs(look, ['music']).find((i) => i.kind === 'music')!.missing).toBe(true)
})

// Review Focus 2.
it('names every zone a look runs on, in running order, leaving out a zone it can\'t name', () => {
  const zones = [{ id: 'a', name: 'Alpha' }, { id: 'b', name: 'Beta' }] as Zone[]
  const running = ['a', 'gone', 'b'].map((zoneId) => ({ zoneId, lookId: 'x' }) as RunningZone)
  expect(runningOn('x', running, zones)).toEqual(['Alpha', 'Beta'])
  expect(runningPill(['Alpha'])).toEqual({ shown: 'Alpha', spoken: 'Running on Alpha' })
  expect(runningPill(['Alpha', 'Beta', 'Gamma'])).toEqual({ shown: 'Alpha +2', spoken: 'Running on Alpha, Beta and Gamma' })
  expect(runningPill([])).toBeNull()
})

it("names a saved look's parent, and none when it's gone", () => { /* parentName */ })

it('says why the grid is empty: the search first, then the switch, then the tab', () => {
  expect(emptyText({ tab: 'starred', query: 'zz', readyOnly: true })).toBe('No looks match “zz”.')
  expect(emptyText({ tab: 'starred', query: '', readyOnly: true })).toBe('No looks are ready now.')
  expect(emptyText({ tab: 'starred', query: '', readyOnly: false })).toBe('No starred looks yet.')
  expect(emptyText({ tab: 'mine', query: '', readyOnly: false })).toBe('No saved looks yet.')
  expect(emptyText({ tab: 'home', query: '', readyOnly: false })).toBe('No home looks yet.')
  expect(emptyText({ tab: 'all', query: '', readyOnly: false })).toBe('No looks yet.')
})

it('says how many looks there are and how many zones run', () => {
  expect(looksContext(looks, running)).toBe(`${tabCounts(looks).all} looks · ${running.length} running`)
})
```

`runningPill`'s words join the names with `formatList()` (`src/lib/format.ts:92`, §10's lists). If it joins them otherwise than "A, B and C", the test takes its form.

- [ ] **Step 3: Run them to see them fail**

Run: `cd web && npx vitest run src/looks/library-model.test.ts`
Expected: FAIL. `./library-model` doesn't exist.

- [ ] **Step 4: Write `library-model.ts`**, with a header comment naming §8.4 and rulings 9 to 14, 18 and 21. `cardInputs` maps `look.uses` in `INPUTS`' order to `INPUTS[kind]`, with the name `'HA'` for `home-assistant` (Looks.html's; the test pins it).

- [ ] **Step 5: Run the tests**

Run: `cd web && npx vitest run src/looks/library-model.test.ts`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/src/looks/library-model.ts web/src/looks/library-model.test.ts
git commit -m "feat(web): the Looks library's model: tabs, counts, search, sections"
```

---

### Task 6: The mock's library, as Looks.html draws it

**Files:**
- Modify: `web/src/api/mocks/scenarios.ts`, `web/src/api/mocks/scenarios.test.ts`, `web/src/looks/library-model.test.ts`

**Interfaces:**
- Consumes: Task 2's `LIBRARY`; `hero()`, `BUILD`, `SCENARIOS`, `lookName()`.
- Produces: `'library'` in `SCENARIOS`. Its state is the hero's, with `LIBRARY.starred`'s looks starred, and `LIBRARY.mine` appended as `{ ...structuredClone(parent), id: `mine-${i + 1}`, name, description, builtIn: false, derivedFrom: parent.id, starred: false }`. `?scenario=library` serves it.

- [ ] **Step 1: Read** §12.5 (the scenarios) and the hero's `BUILD` entry.

- [ ] **Step 2: Write the failing tests** (`scenarios.test.ts`)

```ts
describe('the library', () => {
  it("is the hero, with Looks.html's stars and saved looks", () => {
    const library = buildScenario('library', HERO_NOW)
    const hero = buildScenario('hero', HERO_NOW)
    expect(library.running).toEqual(hero.running)
    expect(library.looks.filter((l) => l.starred).map((l) => l.id)).toEqual(LIBRARY.starred)
    const saved = library.looks.filter((l) => !l.builtIn)
    expect(saved.map(({ name, description, derivedFrom }) => ({ name, description, from: derivedFrom }))).toEqual(LIBRARY.mine)
    for (const look of saved) expect(look.thumbnail).toBe(library.looks.find((l) => l.id === look.derivedFrom)!.thumbnail)
  })

  it('runs the looks Looks.html marks running, on the zones it names', () => {
    const { running, zones } = buildScenario('library', HERO_NOW)
    for (const [lookId, zoneName] of Object.entries(LIBRARY.running)) {
      expect(running.some((z) => z.lookId === lookId && zones.find((zone) => zone.id === z.zoneId)?.name === zoneName)).toBe(true)
    }
  })

  // F4's composer baselines rest on it (ruling 19).
  it('leaves the hero with no star and no saved look', () => {
    expect(buildScenario('hero', HERO_NOW).looks.every((l) => l.builtIn && !l.starred)).toBe(true)
  })
})
```

- [ ] **Step 3: Run them to see them fail**

Run: `cd web && npx vitest run src/api/mocks/scenarios.test.ts`
Expected: FAIL. `'library'` isn't a scenario name.

- [ ] **Step 4: Add the scenario.** If the second test fails because the hero runs a different look on a zone than Looks.html's pills draw, stop and tell the owner: the hero is shared with the Live renders, and F5 must not change it.

- [ ] **Step 5: Switch Task 5's tests to the scenario**

`library-model.test.ts`'s `looks` is `buildScenario('library', HERO_NOW).looks`, and its hand-made star and saved look go.
Run: `cd web && npx vitest run src/api/mocks src/looks/library-model.test.ts src/compose`
Expected: PASS. The "every scenario" tests take the new name in.

- [ ] **Step 6: Commit**

```bash
git add web/src/api/mocks web/src/looks/library-model.test.ts
git commit -m "feat(web): the mock's library scenario, as Looks.html draws it"
```

---

### Task 7: LookCard, and starring a look

**Files:**
- Modify: `web/src/api/actions.ts`, `web/src/api/actions.test.ts`
- Create: `web/src/looks/look-card.tsx`, `web/src/looks/look-card.test.tsx`

**Interfaces:**
- Consumes: Task 3's `LookThumb` (`size="card"`); Task 5's `cardInputs`, `runningPill`, `MissingInput`; `composerLink()`, `ButtonLink`, `Icon`, `useAnnounce()` (`@/design/announce`), `failureText()`, `LIVE_SPEC.lookCard`.
- Produces:
  - `export async function setStarred(lookId: Id, starred: boolean): Promise<void>` (`actions.ts`)
  - `export interface LookCardProps { look: Look; running: readonly string[]; parent: string | null; missing: readonly MissingInput[] }` and `export function LookCard(props: LookCardProps)`. The root is an `<article>` labelled by its `<h3>`, with `data-look={look.id}`.

- [ ] **Step 1: Read** §6.4 `LookCard`, §5.4 (the live dot) and §14 (contrast). View `Looks.png`'s hovered card and a starred one. In `Looks.html`, read a card: the 22 px pill with its 6 px dot, the star button in both states, the description's clamp, the input row, and the scrim with Put on… and Edit.

- [ ] **Step 2: Write the failing tests**

`actions.test.ts` (Review Focus 3; `api.setStarred` mocked with deferred promises, `seedRest('library')`):

```ts
describe('setStarred', () => {
  it("shows the star at once, then keeps the server's look", async () => { /* cache starred before the answer; equals the answer after */ })

  it('lets the latest choice win when two answers come back out of order', async () => {
    // star (A pending), unstar (B pending); resolve B with starred false, then A with starred true: the cache ends false.
  })

  it('puts the look back when the latest choice fails, and rejects with the ApiError', async () => {
    // one pending call rejects ApiError(500): the cache is back to the look before it, and the promise rejects with that error.
  })

  it("doesn't put back over a later choice when an earlier one fails", async () => {
    // star (A), unstar (B); A rejects, then B resolves false: the cache ends false, and A still rejects.
  })
})
```

`look-card.test.tsx` (`renderAt('/looks', …)` from `src/test/router.tsx`, its `<LookCard … />` inside `QueryClientProvider client={queryClient}` and `Announcer` (`src/design/announcer.tsx`), which `renderAt` doesn't give; the cache seeded by `seedRest('library')`):

```ts
it("draws the look's name in serif at §6.4's size, its description, and its inputs", () => {
  const card = screen.getByRole('article', { name: look.name })
  expect(within(card).getByRole('heading', { level: 3, name: look.name })).toHaveStyle({ fontSize: `${LIVE_SPEC.lookCard.namePx}px` })
  expect(within(card).getByText(look.description!)).toBeInTheDocument()
  for (const name of LIBRARY.inputs[look.id]) expect(within(card).getByText(name)).toBeInTheDocument()
})

it('says "No input" for a look with none, and draws a missing input in signal', () => { /* … toHaveClass('text-signal') */ })

it('opens the editor from its name, and puts the look on from Put on…', () => {
  expect(within(card).getByRole('link', { name: look.name })).toHaveAttribute('href', `/next/looks/${look.id}`)
  expect(within(card).getByRole('link', { name: 'Put on…' })).toHaveAttribute('href', `/next${composerLink(null, look.id).to}`)
  expect(within(card).getByText('Edit').closest('a')).toHaveAttribute('tabindex', '-1')
})

it('stars and unstars the look, saying so with aria-pressed and its label', async () => {
  await user.click(within(card).getByRole('button', { name: `Star ${look.name}` }))
  expect(within(card).getByRole('button', { name: `Unstar ${look.name}` })).toHaveAttribute('aria-pressed', 'true')
})

// Review Focus 3.
it('says a failed star aloud, and shows the look as it was', async () => {
  vi.spyOn(api, 'setStarred').mockRejectedValue(new ApiError(500, 'Internal Server Error'))
  await user.click(within(card).getByRole('button', { name: `Star ${look.name}` }))
  expect(screen.getByRole('status')).toHaveTextContent(`Couldn't star ${look.name}. Internal Server Error`)
  expect(within(card).getByRole('button', { name: `Star ${look.name}` })).toHaveAttribute('aria-pressed', 'false')
})

// Review Focus 2.
it('names the zone it runs on, and every zone in words when there are more', () => {
  // running=['Alpha']: the pill shows "Alpha" with the dot; running=['Alpha','Beta']: "Alpha +1", and the card holds "Running on Alpha and Beta" (sr-only).
})

it('says which look a saved look came from', () => {
  // parent='Fireflies'-like name from the fixtures: the pill reads `From ${parent}`, with no dot.
})
```

Build the `ApiError` as `rest.ts:11` constructs one.

- [ ] **Step 3: Run them to see them fail**

Run: `cd web && npx vitest run src/api/actions.test.ts src/looks/look-card.test.tsx`
Expected: FAIL. `setStarred` and `./look-card` don't exist.

- [ ] **Step 4: Write `setStarred` and `LookCard`**

`setStarred` (header comment: §8.4, ruling 16): a module-level `Map<Id, number>` of each look's latest request. It writes `{ starred }` into `queries.looks()`'s cache, calls `api.setStarred`, and writes the answer only if its request is still the latest. On failure, it writes the look as it was before the request, only if still the latest, then rethrows.

`LookCard` (header comment naming §6.4, rulings 13 to 16 and 18, and Looks.html for each arbitrary value):
- `<article className="group relative flex min-w-0 flex-col gap-2">`.
- A `relative` box holding `LookThumb size="card"`, whose border turns `border-text` on `group-hover` and `group-focus-within` (§6.4 "white border").
  - The pill sits top-left at 8 px (`top-2 left-2`): `h-5.5 rounded-pill border border-line bg-bg/82 px-2 text-label font-semibold`, Looks.html's "rgba(13,12,11,.82)". The dot is `size-1.5 rounded-full bg-text animate-[livedot_2s_ease-in-out_infinite]`, as `connection-indicator.tsx` draws its own.
  - The scrim: `absolute inset-0 flex items-end justify-center gap-2 p-2.5 opacity-0 group-hover:opacity-100 group-focus-within:opacity-100`, with `bg-linear-to-t from-bg/85 to-bg/0 to-70%` (Looks.html's gradient). It holds `ButtonLink variant="primary" size="sm" icon="play"` Put on… and `ButtonLink size="sm" icon="sliders" tabIndex={-1}` Edit.
- The name row: `flex items-center justify-between gap-1 pl-0.5`. The `<h3>` is `font-serif text-display-xs`, with `style={{ fontSize: LIVE_SPEC.lookCard.namePx }}` as `LookTile` does. It holds the `Link`, stretched over the card with `after:absolute after:inset-0`. The star button sits above the link (`relative z-1`): `size-7 rounded-chip`, `text-text-3`, or `text-text` and a `fill-current` icon when pressed, the icon 15 px, `max-md:touch-target`.
- The description: `-mt-1 pl-0.5 text-meta text-text-3 line-clamp-2`, two lines high (`h-[35px]`, Looks.html).
- The inputs: `flex gap-2.5 pl-0.5`, each an `Icon` and a name at `text-[11.5px]` (Looks.html, as `LookTile`'s signal line), `text-text-3`, or `text-signal` when missing. "No input" for none.
- The star's failure goes to `useAnnounce()` as `failureText(`${starred ? 'unstar' : 'star'} ${look.name}`, error)`.

- [ ] **Step 5: Run the tests**

Run: `cd web && npx vitest run src/api/actions.test.ts src/looks`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/src/api/actions.ts web/src/api/actions.test.ts web/src/looks/look-card.tsx web/src/looks/look-card.test.tsx
git commit -m "feat(web): LookCard, with its star, its overlays and Put on… / Edit"
```

---

### Task 8: The filter bar

**Files:**
- Create: `web/src/looks/library-filters.tsx`, `web/src/looks/library-filters.test.tsx`

**Interfaces:**
- Consumes: Task 5's `LIBRARY_TABS`, `LibraryTab`; `Switch` (`@/design/switch`), `ButtonLink`, `Icon`.
- Produces: `export interface LibraryFiltersProps { tab: LibraryTab; counts: Record<LibraryTab, number>; query: string; readyOnly: boolean; onTab: (tab: LibraryTab) => void; onQuery: (query: string) => void; onReadyOnly: (on: boolean) => void }` and `export function LibraryFilters(props: LibraryFiltersProps)`.

- [ ] **Step 1: Read** §8.4's filter bar line. View `Looks.png`'s bar. In `Looks.html`, read the search box (`box-sizing: border-box`, its size), the pills, the switch and New look.

- [ ] **Step 2: Write the failing tests**

```ts
it("searches looks, layers and inputs, and Esc clears it", async () => {
  const box = screen.getByRole('searchbox', { name: 'Search looks' })
  expect(box).toHaveAttribute('placeholder', 'Search looks, layers, inputs')
  await user.type(box, 'fi')
  expect(onQuery).toHaveBeenLastCalledWith('fi')
  await user.keyboard('{Escape}')
  expect(onQuery).toHaveBeenLastCalledWith('')
})

it('draws a tab for All, Starred, each category and Mine, each with its count, the chosen one pressed', () => {
  const group = screen.getByRole('group', { name: 'Categories' })
  expect(within(group).getAllByRole('button').map((b) => b.textContent)).toEqual(LIBRARY_TABS.map((t) => `${t.label}${counts[t.id]}`))
  expect(within(group).getByRole('button', { name: /^All/ })).toHaveAttribute('aria-pressed', 'true')
})

it('turns Only ready now on and off', async () => {
  await user.click(screen.getByRole('switch', { name: 'Only ready now' }))
  expect(onReadyOnly).toHaveBeenCalledWith(true)
})

it('offers New look, which goes to the editor', () => {
  expect(screen.getByRole('link', { name: 'New look' })).toHaveAttribute('href', '/next/looks/new')
})
```

- [ ] **Step 3: Run them to see them fail**

Run: `cd web && npx vitest run src/looks/library-filters.test.tsx`
Expected: FAIL. `./library-filters` doesn't exist.

- [ ] **Step 4: Write `LibraryFilters`**: `flex flex-wrap items-center justify-between gap-4`.
- The left group holds the search and the tabs. The search label is `h-9 w-70 rounded-control border border-line bg-control px-3` with `Icon search` and an sr-only "Search looks", like the composer's search. Esc clears it.
- The tabs are `role="group" aria-label="Categories"` buttons: `h-8 rounded-pill border px-3 text-size-control font-semibold`, with the count `font-mono text-label text-text-3`. The chosen one is `border-text bg-control-hover`, the others `border-line`.
- The right group holds `Switch label="Only ready now"` and `ButtonLink icon="plus"` New look to `/looks/new`.
- On the phone, the bar wraps and the search takes the full width (ruling 1).

- [ ] **Step 5: Run the tests**

Run: `cd web && npx vitest run src/looks/library-filters.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/src/looks/library-filters.tsx web/src/looks/library-filters.test.tsx
git commit -m "feat(web): the Looks library's filter bar"
```

---

### Task 9: The Looks page

**Files:**
- Create: `web/src/pages/looks.tsx`, `web/src/pages/looks.test.tsx`
- Modify: `web/src/app/page-meta.ts`, `web/src/app/routes.tsx`, `web/src/shell/app-shell.tsx`, `web/src/shell/shell.test.tsx`, `web/src/compose/use-composer.ts`

**Interfaces:**
- Consumes: Tasks 5, 7 and 8; `useRunning()`; `queries.looks()`, `queries.zones()`; `EmptyState`; `LIVE_SPEC.lookCard`, `LIVE_SPEC.looksPage`.
- Produces:
  - `export type InputsRead` and `export function useInputsRead(): InputsRead` (`use-composer.ts`, the selector `useComposer` already uses, moved out unchanged).
  - `PageMeta.Context?: ComponentType`, drawn on the desktop top bar in place of `context`.
  - `export function LooksPage()` and `export function LooksContext()` (`pages/looks.tsx`). `LOOKS` is `{ title: 'Looks', Context: LooksContext }`, and the `looks` route's element is `<LooksPage />`.

- [ ] **Step 1: Read** §8.4, §4.3's `/looks` row and §4.4. View `Looks.png` whole: the header's context, the sections, the last row.

- [ ] **Step 2: Write the failing tests**

`shell.test.tsx`, under `TopBar` or `AppShell`:

```ts
it("draws a page's context component where it has one", () => {
  // a route handle { title: 'X', Context: () => <>seven</>, context: () => 'never' }: the banner holds "seven", not "never".
})
```

`pages/looks.test.tsx` (`renderApp`, `seedRest('library')`, `seedLive('library')`):

```ts
it('says how many looks there are and how many zones run', async () => {
  renderApp('/next/looks')
  expect(await within(screen.getByRole('banner')).findByText(looksContext(looks, running))).toBeInTheDocument()
})

it("draws a section per category with its name at §8.4's size, its count and its blurb, then Firmware and Mine", async () => {
  renderApp('/next/looks')
  const headings = await screen.findAllByRole('heading', { level: 2 })
  expect(headings.map((h) => h.textContent)).toEqual(librarySections(looks, ALL).map((s) => s.name))
  expect(headings[0]).toHaveStyle({ fontSize: `${LIVE_SPEC.looksPage.sectionNamePx}px` })
  expect(screen.getByText(LOOK_CATEGORIES[0].blurb)).toBeInTheDocument()
  expect(screen.getByText(LIBRARY.mineBlurb)).toBeInTheDocument()
})

it("lays the cards on §8.4's gaps", async () => {
  // the first section's grid has gap-y-7 and gap-x-4, and LIVE_SPEC.looksPage's rowGapPx and columnGapPx are 4 × 7 and 4 × 4.
})

it('keeps the tab and the search in the URL, and replaces a cat it doesn\'t know (Review Focus 1)', async () => {
  const router = renderApp('/next/looks?cat=calm&q=fire')
  expect(await screen.findByRole('button', { name: /^All/ })).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByRole('searchbox', { name: 'Search looks' })).toHaveValue('fire')
  await user.click(screen.getByRole('button', { name: /^Tempo/ }))
  expect(router.state.location.search).toBe('?cat=tempo&q=fire')
})

it('shows only the looks ready now with the switch on: inputs-down hides those waiting for music or Home Assistant', async () => { /* … */ })

it('says why there is nothing to show', async () => {
  // ?q=zzzz: "No looks match “zzzz”."; the hero's ?cat=starred: "No starred looks yet."
})

it("says when the looks didn't load, and tries again", async () => {
  // api.looks rejects ApiError(500): EmptyState with "Couldn't load the looks. Internal Server Error"; Try again refetches.
})

it('puts the running zones and the parents on the cards', async () => {
  for (const [lookId, zone] of Object.entries(LIBRARY.running)) {
    expect(within(card(lookId)).getByText(zone)).toBeInTheDocument()
  }
  for (const mine of LIBRARY.mine) expect(within(screen.getByRole('article', { name: mine.name })).getByText(`From ${lookName(mine.from)}`)).toBeInTheDocument()
})

it('stars a look on the page, and the composer sees it', async () => { /* click Star; queries.looks() cache holds starred */ })
```

`card(lookId)` finds the article by `data-look`. `ALL` is `{ tab: 'all', query: '', readyOnly: false, inputs }`.

- [ ] **Step 3: Run them to see them fail**

Run: `cd web && npx vitest run src/pages/looks.test.tsx src/shell/shell.test.tsx`
Expected: FAIL. `@/pages/looks` doesn't exist, and the shell ignores `Context`.

- [ ] **Step 4: Write the page**

- `LooksPage` reads `cat` and `q` with `useSearchParams`. A tab click sets `cat` (All deletes it) and keeps `q`. Typing sets `q` with `{ replace: true }`. `readyOnly` is `useState(false)`.
- It draws `LibraryFilters`, then the sections, inside `flex flex-col gap-10 py-6` (Looks.html's main: 40 gap, 24 top padding). The page doesn't set its own width: the shell's content width is `--content-max-w`.
- Each section: `flex flex-col gap-4`. Its header is `flex items-baseline gap-3`:
  - `<h2 className="font-serif" style={{ fontSize: LIVE_SPEC.looksPage.sectionNamePx }}>`;
  - the count in `font-mono text-meta text-text-3` when `counted`;
  - the blurb in `text-size-control text-text-3`.
- The grid is `grid grid-cols-2 gap-x-4 gap-y-7 md:grid-cols-[repeat(auto-fill,minmax(var(--card-min),1fr))]` with `style={{ '--card-min': `${LIVE_SPEC.lookCard.px}px` }}`.
- The `lastRow` sections sit in one `flex flex-wrap gap-12` row. Each holds `flex flex-wrap gap-x-4 gap-y-7` of cards `w-(--card-min)`. Below `md` they fall back into the two-column grid.
- Each card gets `runningOn(look.id, running, zones)`, `parentName(look, looks)` and `missingInputs(look, inputs)`.
- `LooksContext` draws `looksContext(looks, running)` once both have loaded, and nothing before.
- `AppShell`: `const { Context, PhoneTitle } = meta`. The desktop `TopBar`'s context is `Context ? <Context /> : meta.context && <PageContext get={meta.context} />`.

- [ ] **Step 5: Run the tests, and those that open /looks**

Run: `cd web && npx vitest run src/pages src/shell src/app src/chrome/hold.test.tsx src/compose src/looks`
Expected: PASS. `app.test.tsx`'s "shows the tempo strip on Live only" and `hold.test.tsx` open `/next/looks` and now meet the real page. If `hold.test.tsx` finds two `status` roles, the page added one: take it out (ruling 21).

- [ ] **Step 6: Commit**

```bash
git add web/src/pages/looks.tsx web/src/pages/looks.test.tsx web/src/app web/src/shell web/src/compose/use-composer.ts
git commit -m "feat(web): the Looks library page at /looks"
```

---

### Task 10: In the browser: Looks.png, the beat, and the baselines the motifs change

**Files:**
- Create: `web/e2e/looks.spec.ts`
- Re-record: `web/e2e/compose.spec.ts-snapshots/*`, `web/e2e/live.spec.ts-snapshots/nothing-running-*`, and any other baseline whose thumbs changed, after a comparison by eye
- Record: `web/e2e/looks.spec.ts-snapshots/library-desktop-linux.png`

**Interfaces:**
- Consumes: everything before. `open()` from `e2e/helpers.ts`. `LIBRARY` from `../src/looks/looks-render`, as e2e imports `live-numbers`.
- Produces: the screenshot baseline and the browser checks.

- [ ] **Step 1: Read** §13.1's M5 row and §5.4. View `Looks.png`, `Live-PutLookOn.png`, `Phone-PutLookOn.png`, `State-Nothing-Running.png` and `Phone-State-Nothing-Running.png`, once each, and write down what each thumb draws.

- [ ] **Step 2: Write the specs**

```ts
test.describe('Looks', () => {
  test('matches Looks.png, with its hovered card', async ({ page }, info) => {
    test.skip(info.project.name !== 'desktop')
    await page.clock.setFixedTime(HERO_TIME) // as shell.spec.ts sets it
    await open(page, '/next/looks?scenario=library&still')
    // The viewport grows to the page's whole height, as Looks.png draws it.
    await page.setViewportSize({ width: 1440, height: await page.evaluate(() => document.documentElement.scrollHeight + (document.querySelector('main')!.scrollHeight - document.querySelector('main')!.clientHeight)) })
    await page.locator(`[data-look="${LIBRARY.hovered}"]`).hover()
    await expect(page).toHaveScreenshot('library.png')
  })

  test('moves a beat thumb at the live tempo, with its CSS paused', async ({ page }, info) => {
    test.skip(info.project.name !== 'desktop')
    await open(page, '/next/looks?scenario=inputs-down') // Internal at 118 BPM
    const read = () => page.evaluate(() => {
      const svg = document.querySelector('svg.tb[data-beat]')!
      const [animation] = svg.getAnimations({ subtree: true })
      return { at: performance.now(), time: Number(animation.currentTime), state: animation.playState }
    })
    const first = await read()
    await page.waitForTimeout(3000)
    const second = await read()
    expect(second.state).toBe('paused')
    expect((second.time - first.time) / (second.at - first.at)).toBeGreaterThan(0.94) // 118 / 121.8 = 0.969
    expect((second.time - first.time) / (second.at - first.at)).toBeLessThan(0.99)
  })

  test('holds every thumb under ?still', async ({ page }) => { /* two reads 1 s apart: equal currentTime, data-paused on every svg.tb */ })

  // Review Focus 5.
  test('runs a thumb on screen and rests it off screen', async ({ page }, info) => {
    test.skip(info.project.name !== 'desktop')
    // /next/looks?scenario=library: the Firmware card's svg has data-paused; after scrolling it into view it hasn't; scrolled back out, it has again.
  })

  test('has no axe violations, hovered or not', async ({ page }) => { /* axe on /next/looks?scenario=library&still, then with LIBRARY.hovered hovered */ })
})
```

Copy `HERO_TIME` and the axe builder as `shell.spec.ts` has them (both are local to it). If `main` doesn't scroll, the extra height term is 0.

- [ ] **Step 3: Run the new spec to record it, and compare it by eye**

```bash
for i in $(seq 1 60); do [ "$(ss -ltn | grep -cE ':(4174|4175) ')" = 0 ] && break; sleep 10; done; ss -ltn | grep -cE ':(4174|4175) '
(cd web && npx playwright test e2e/looks.spec.ts --update-snapshots 2>&1 | tail -3)
```

View `web/e2e/looks.spec.ts-snapshots/library-desktop-linux.png` once, beside your notes on `Looks.png`. Check:
- the bar;
- the five category sections, and Firmware and Mine on the last row;
- six columns;
- the stars, the running pills and the From pills where Looks.png has them;
- the hovered card's scrim and white border;
- each thumb's motif, as the render draws it.

Fix any difference the renders don't explain before going on, and list the ones they do under "Differences from the renders". Then run the spec again without `--update-snapshots`: every test passes.

- [ ] **Step 4: Re-record the baselines the thumbs changed**

```bash
(cd web && npm run e2e 2>&1 | tail -5)
```

Expected: only screenshots holding a `LookThumb` fail: the composer's states, Nothing running, and the phone's rows. View each failing actual once beside its render (Step 1's notes). Each thumb should now draw the render's motif, and nothing else should move. Then re-record those alone:

```bash
(cd web && npx playwright test e2e/compose.spec.ts e2e/live.spec.ts --update-snapshots 2>&1 | tail -3 && npm run e2e 2>&1 | tail -3)
```

Expected: e2e passes, with Before Task 1's counts plus the new spec's.

- [ ] **Step 5: The budget**

Run: `cd web && npm run build 2>&1 | tail -1`
Expected: `…/web/dist: no mocks, <n> KB of gzipped JS`, under `check-dist.ts`'s budget. Write down `<n>` minus Before Task 1's figure for the PR. If it's over the budget, stop and tell the owner: the motifs would then need a lazy chunk of their own.

- [ ] **Step 6: Commit**

```bash
git add web/e2e
git commit -m "test(web): Looks.png, the beat in the thumbs, and the baselines the motifs change"
```

---

### Task 11: Revise CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: every task.
- Produces: the repo's notes on F5.

- [ ] **Step 1: Edit, with one batched set of edits:**
  - Line 160 (`src/looks/`) becomes: `LookThumb`, which draws each look's motif from the generated `looks-render.ts`/`.css` with its own id prefix. `thumb-writer.ts` runs every thumb from one frame loop: the ambient motifs' CSS loops while on screen, and the tempo and audio motifs seeked to the beat (`beatMs()`, at §5.4's stand-in tempo). `use-thumb-motion.ts` registers a thumb only on screen, with motion allowed, `live` and the clock not held. Then `library-model.ts` (tabs, counts, search, sections), `LookCard` and `LibraryFilters`.
  - `src/pages/`: add `looks.tsx` (the library at `/looks?cat=&q=`, and `LooksContext`, the top bar's count).
  - `scripts/design-numbers.ts`: add `looks-extract.ts`, which writes `src/looks/looks-render.ts` and `.css` from the pinned `Looks.html` (checked against the PutLookOn renders), with `src/looks/looks-render.node.test.ts` failing when they're stale.
  - `src/app/`: `PageMeta.Context`, a component for a context line that counts data.
  - `src/api/`: `actions.ts`'s `setStarred()`, where the latest choice for a look wins.
  - `e2e/`: `looks.spec.ts`.
  - Gotchas: the six `classic-*` looks have no motif and draw the bare scene; "Only ready now" hides nothing until the engine serves music and Home Assistant (M7); a thumb test needs `intersect()` from `src/test/intersection.ts` to put it on screen.

- [ ] **Step 2: Check, and commit**

Run: `grep -n "until F5" CLAUDE.md web/src -r`
Expected: nothing.

```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md for the Looks library (F5)"
```

---

### Task 12: Rebase over master, and open the PR

Engine M6 is planned beside this plan, and either may merge first. M6 adds Home sunset, Wisp and Goodnight to `/api/looks` and changes no file under `web/` that F5 changes, but both change `CLAUDE.md`. This task never merges.

**Files:**
- Modify, only where the rebase asks: `CLAUDE.md`, and any `web/` file master changed beside this branch.

**Interfaces:**
- Consumes: every task's commits; master as it is now.
- Produces: the pull request.

- [ ] **Step 1: Rebase onto master**

```bash
git fetch origin
git log --oneline d5e4931..origin/master
git rebase origin/master
```

Write down whether engine M6 had merged, for the PR. Where a commit conflicts:
- **`CLAUDE.md`:** keep both sides.
- **A baseline:** keep F5's (`git checkout --theirs <file>`), and Step 2 compares it again.
- **Anything else:** stop and tell the owner.

- [ ] **Step 2: The whole web gate, from a clean install**

```bash
uv sync --extra web
(cd web && npm ci && npm run api:check && npm test 2>&1 | grep -E 'Test Files|Tests ' && npm run lint && npx tsc -b && echo "tsc ok" && npm run build 2>&1 | tail -1)
for i in $(seq 1 60); do [ "$(ss -ltn | grep -cE ':(4174|4175) ')" = 0 ] && break; sleep 10; done; ss -ltn | grep -cE ':(4174|4175) '
(cd web && npm run e2e 2>&1 | tail -3)
```

Expected:
- `api:check` passes, since F5 changes no API.
- Vitest passes, with the node tests among them. If `looks-render.node.test.ts` or `design-numbers.node.test.ts` fails, a new handoff landed: stop and tell the owner.
- Lint and `tsc -b` are clean.
- The build is within budget.
- The port check prints `0`, and e2e passes. A screenshot that master's changes moved is compared by eye and re-recorded, as Task 10 did.

- [ ] **Step 3: Scope and privacy checks**

Run F10's Task 10 Step 3 checks (`docs/superpowers/plans/2026-10-14-f10-effects-in-space.md`, "Scope and privacy checks"), with `f5` in place of `f10` in the scratch file's name. Expected: no diff outside `web/`, `CLAUDE.md` and this plan's own docs; the copies identical; and no output from the privacy greps. `web/src/looks/looks-render.ts` holds the demo home's zone names in `LIBRARY.running`, copied from the render, as `home.json` does: those matches are expected. Check by eye that nothing else matches.

- [ ] **Step 4: Push and open the PR**

```bash
git push -u origin feature/web-f5-looks-library
gh pr create --base master --title "F5: the Looks library" --body-file - <<'EOF'
## Summary

Milestone F5 (the handoff's M5) of the web app rebuild, per docs/superpowers/plans/2026-11-09-f5-looks-library.md: `/looks` is §8.4's library, with the filter bar, a section per category and §6.4's LookCards, and all 29 LookThumb motifs from Looks.html.

- **Motifs:** generated from the pinned Looks.html by `npm run design:numbers` (`looks-render.ts`/`.css`), each thumb with its own ids; the tempo and audio motifs are seeked to the live beat every frame, and the others run their own loops; every thumb rests off screen, under reduced motion and under `?still`.
- **The page:** tabs with the render's counts, search over names, layers and inputs, Only ready now, stars (the latest choice wins), running and From pills, Put on… / Edit, and the top bar's "N looks · M running".
- **The mock:** a `library` scenario, the hero with Looks.html's stars and saved looks; the hero is unchanged.
- **Baselines:** the composer's and Nothing running's screenshots re-recorded, as their thumbs now draw motifs (compared by eye with their renders).

## For the owner

- Rulings to check: the plan's "Decisions already made", 1 to 23; 1 was the open question (7 the owner answered on 2026-11-11).
- Engine M6 <had / hadn't> merged when this was rebased.
- Bundle: +<n> KB of gzipped JS.

## Differences from the renders

<Task 10's list>

## Test plan

- [x] `npm test` (<count> tests in <files> files), lint, `tsc -b`, `api:check`, build
- [x] `npm run e2e`, with `looks.spec.ts`
- [ ] The owner opens /next/looks on the deployed app after the merge

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
```

Fill in the placeholders from Steps 1 and 2 and Task 10 before sending.

---

## Differences from the renders

Known before the build. Task 10 adds what the screenshot shows.
- **Phone:** two columns of the desktop card, the bar wrapping, and no header context. `Phone-Looks.png` is F9's (ruling 1).
- **Columns between the breakpoints:** auto-fill at 201 px or wider. Six at the render's 1288 px content width, fewer below it (ruling 20).
- **Thumbs in motion:** the render's CSS loops run at 121.8 BPM, while the app's tempo and audio motifs run at the live tempo (ruling 4). Under `?still` every thumb stands at its authored moment, so the screenshot's thumbs are those of the render's first frame, not of whatever moment Looks.png caught.
- **Several running zones:** "● {first} +{n}"; Looks.png draws only single zones (ruling 13).
- **Real data, not the render's:** today's engine serves no Home looks, only Speaker waves in Audio, and six classics without motifs in Tempo (ruling 7). M6 adds three Home looks, and M7 the Doorbell and the Audio looks.

---

## Test plan

- **Unit (Vitest):** `design-numbers.node.test.ts` and `looks-render.node.test.ts` (the handoff), `motif.test.ts`, `look-thumb.test.tsx`, `thumb-writer.test.ts`, `beat.test.ts`, `library-model.test.ts`, `scenarios.test.ts`, `actions.test.ts`, `look-card.test.tsx`, `library-filters.test.tsx`, `pages/looks.test.tsx`, `shell.test.tsx`. `app.test.tsx` and `hold.test.tsx` now open the real page.
- **Browser (Playwright):** `looks.spec.ts`: the screenshot against Looks.png, the beat at 118 BPM, `?still`, on and off screen, axe. `shell.spec.ts`'s axe already covers `/next/looks?cat=calm&q=fire`. The composer's and Nothing running's re-recorded baselines.
- **By eye:** Task 10's side-by-side with Looks.png and the four thumb renders.

---

## Hand-off

- **Engine M6:** Home sunset, Wisp and Goodnight appear in Home with their motifs as soon as `/api/looks` serves them with looks.json's ids and thumbnails. F5 has no code for them. An M6 overlay gets no running pill (ruling 13).
- **Engine M7:** "Only ready now" starts hiding looks once the engine sends `music` and `homeAssistant` inputs. The Doorbell and the Audio looks appear in their sections.
- **F8:** the editor at `/looks/:id`, which the card's name, Edit and New look (`/looks/new`) already open.
- **F9:** `Phone-Looks.png` (Starred first, its own layout).
- **Later:** a real preview in `LookThumb` behind `live` (§6.4's "Later"), and motifs for the six classics if the owner wants them (ruling 7).

---

## Coverage

| Spec | Task |
|---|---|
| §8.4 filter bar: search (looks, layers, inputs) | 5 (`searchLooks`), 8, 9 |
| §8.4 category tabs with counts | 5 (`tabCounts`), 8 |
| §8.4 "Only ready now" | 5, 8, 9 |
| §8.4 "New look" | 8 (ruling 17) |
| §8.4 sections: serif 32 name, count, blurb from looks.json | 1, 2 (`LOOK_CATEGORIES`), 5, 9 |
| §8.4 6-column grid, 28/16 gaps; Firmware and Mine share the last row | 1, 9 (ruling 20) |
| §8.4 clicking a card opens the editor; hover shows Put on… / Edit | 7 |
| §8.4 data: starred, running zones, missing inputs, inputs availability | 5, 7, 9 |
| §6.4 LookCard: thumb, name and star, description, inputs, overlays, hover and focus | 7 |
| §6.4 LookThumb: 29 motifs from Looks.html keyed by thumbnail; `(lookId, size, live?)` | 2, 3 |
| §6.4 / §5.4: tempo and audio motifs follow the beat clock | 4, 10 |
| §5.4: thumbs animate continuously, pause off screen, stop under reduced motion | 4, 10 |
| §4.3 `/looks?cat=&q=` | 5, 9 |
| §13.1 M5 "Matches Looks.png; thumbs follow the beat clock" | 10 |
| §14 bundle budget | 10, 12 |
| Stars | 7 (`setStarred`), 9 |
