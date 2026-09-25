# F1 Web App Data Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the new web app its typed, isolated data layer in `web/src/api/`: types generated from the backend's OpenAPI schema (with a drift check), a REST client, a WebSocket client with reconnect, backoff and resync, a frame decoder for protocols v1 and v2, a beat clock, zustand stores, and MSW mocks with a mock socket that play every §12.5 scenario. Then put F0's chrome on those stores, one slice at a time.

**Architecture:** Everything the app knows about the server goes through `src/api/`, and components never call `fetch` or touch the socket (spec §12). The backend's own schema is dumped by a Python script and turned into `schema.d.ts` by openapi-typescript. A pytest test and `npm run api:check` fail when the committed files drift from the backend, and `--url` compares a running server's schema. Types engine M2 doesn't serve yet (home map, previews, frame v2) and the ones later milestones add (decks, inputs, signals) are written by hand from §12 in `contract.ts`, and a type test fails the day the backend serves one of them. A `LiveClient` owns the one socket. It writes JSON channels into a zustand store and binary frames into a `FrameStore` of reused typed arrays that React never subscribes to, so 60 fps of LED data costs no renders. A `BeatClock` extrapolates the beat between messages. A `MockServer` plays a scenario: the REST API, the socket's channels and animated frames. In dev it runs behind MSW with `?scenario=`, and in a separate mock build that Playwright tests. The production bundle carries none of it.

**Tech Stack:**
- The F0 app: Vite 8, React 19, TypeScript 5.9 (strict), react-router 7, Vitest 5 (jsdom) with Testing Library, and Playwright with @axe-core/playwright.
- New dependencies: zustand 5 and @tanstack/react-query 5.
- New dev dependencies: msw 2 (its `ws` API for the socket) and openapi-typescript 7.
- FastAPI's OpenAPI output on the Python side.

**Spec:**
- `docs/superpowers/specs/2026-09-23-web-app-rebuild-design.md`, the Claude Design handoff. F1 is its M1 row in §13.1. Read §9 (states), §12 (data contract) and §14 (quality bar) closely, and §5.4 (beat-synced motion) and §11.3–11.5 (take-over, persistence, tempo).
- `docs/superpowers/specs/2026-09-23-home-effects-engine-design.md` §10, on how the two tracks meet.
- The renders in `/home/anirudhlath/code/private/dj-ledfx/docs/design/web-app/reference/` are not in git. The mock scenarios are built from their sample content.
- The engine M2 plan, `docs/superpowers/plans/2026-09-24-m2-3d-fields.md`, planned in parallel. This plan's decisions answer four of its Spec Rulings:
  - Ruling 3, the v2 handshake: decision 1.
  - Ruling 4, the PC's parts: decision 6.
  - Ruling 16, what a placement request answers: decision 6.
  - Ruling 9, a preview nobody watches ends by itself: Task 7 subscribes to the live stream only.

## Global Constraints

Every task's requirements include this section. Quotes are the spec's or CLAUDE.md's own words, with their sections.

**Source of truth**
- CLAUDE.md, "Web App Design": "The Claude Design handoff is the only source of design truth. Don't work from memory, a summary or an earlier conversation."
- CLAUDE.md: "Use `tokens.css`, `icons.ts`, `looks.json` and `home.json` as they are: import them, or copy them byte for byte with a test that fails when the copy differs. Never retype a token, colour, size, icon path or look description, and never restate design values in docs or in this file." The mocks read rooms, lights and looks from byte copies of `home.json` and `looks.json` (Task 8). No room name, light name, position or look name or description is typed into code.
- CLAUDE.md: "Before each web app task, re-read the spec sections and look at the renders that the task names." Each task's first step names them.
- The byte copies (`web/src/styles/tokens.css`, `web/src/design/icons.ts`, and from Task 8 `web/src/api/mocks/home.json` and `looks.json`) change only by `cp` from `docs/design/web-app/`. Never run a search-and-replace that can reach them.

**The data contract** (spec §12)
- §12: "Build the UI against a typed, isolated data layer (`src/api/`): generated OpenAPI types, a REST client, a WebSocket client and a frame decoder, plus MSW mocks that serve the 19:14 scenario. Components never call `fetch` or touch the socket directly."
- §12.4: "**Binary frame v2:** `[1B stream: 0x01 live | 0x02 preview][2B id_len LE][id UTF-8 (stable id)][4B seq LE][RGB × leds]`. Keep v1 behind a version handshake until the old UI is deleted."
- §12.4: "Beat extrapolation: client computes `phase(t) = beat_phase + (t − server_time − offset) · bpm / 60`, … snap softly (< 5 ms) or hard (≥ 5 ms), mirroring `BeatClock` drift correction."
- §12.5: "MSW handlers and a mock WS in `src/api/mocks/` serve fixtures built from `home.json`, `looks.json` and the scenarios in the reference renders: **hero** …, **doorbell**, **transition**, **problems**, **firmware**, **inputs-down**, **nothing-running**, **no-lights**, **reconnecting**, **dj-playing**. A `?scenario=` query switches fixtures in dev. The mock frame generator animates simple versions of the looks so the stage is alive without the engine."
- §9.4 Reconnecting: "Exponential backoff 1, 2, 4, 8 s, max 10 s. Resync everything on reconnect".
- §9.5: attention is "Server-derived so desktop and phone agree … Ordered by severity then time."
- §5.4: "**Beat-synced motion must follow the real beat clock**, never a CSS timer."
- §10: "Names from the backend verbatim (light names, entity ids, track titles)." "BPM (one decimal …)".

**What the backend serves today, and what it doesn't** (engine spec §10)
- Engine M1, merged on `master`, serves §12's looks, zones, running, lights and attention endpoints, and the socket's `running`, `lights`, `attention`, `stats`, `status` and `transport` channels, the v1 `beat` and binary frame v1.
- Engine M2 (home map, preview runtimes, frame protocol v2) is planned in parallel and may merge before or after F1. F1 must not wait for it. What M2 adds is typed and mocked from §12, and the rest is generated from the backend's own schema.
- Engine spec §10: "every F milestone merges to `master` on its own, with no stacked branches."

**Owner's constraints for F1** (from F0's PR review)
1. Once the chrome is live it reads the stores one slice at a time, through selectors, "so a beat doesn't re-render all of the chrome."
2. The chrome never shows "All good" before the server's first data arrives. The same goes for the tempo module and "Live": nothing claims to know what it hasn't heard.
3. Any slider added later sends throttled updates. F1 adds none; the Hand-off section carries the rule to F3 and F4.

**Quality** (§13.1, §14)
- M1 is done when "Stores update from the mock at 60 fps without React re-renders (React profiler)".
- §14 Unit: "frame decoder v1/v2, beat extrapolation, … attention ordering".
- §14 Resilience: "kill the server during a session → Reconnecting state within 2 s, full resync on return, no duplicate subscriptions."
- §14 Performance: "first load < 400 KB gzipped JS excluding three.js". The mocks and MSW never reach `web/dist` (Task 11 checks it on every build).

**Public repo and live system**
- The repo is public. No LAN IP address, MAC address or light model name goes into code, tests, fixtures, commits or the PR. The renders contain all three; the fixtures take addresses from the documentation range `192.0.2.0/24` (RFC 5737), carry no MACs, and read `model` from `home.json` rather than from a render. DJ players are "Player 1" to "Player 4".
- The deployed `dj-ledfx-app-1` is never touched. The only contact is optional and read-only: `npm run api:check -- --url http://127.0.0.1:8080` GETs its `/openapi.json` (Task 1, Task 15).

**Workflow** (CLAUDE.md)
- Use `uv` for Python. Ruff line length is 99 and mypy is strict. "Web tests: `uv sync --extra web` required in worktrees — web tests skip silently without it".
- Never run `uv run ruff format .` over the repo. Format only the files a task touches, and use `--check` for the repo.
- Gates, per task, before its commit:
  - Web: `(cd web && npm test && npm run lint && npx tsc -b)` all pass.
  - Python, in Tasks 1 and 15: `uv run pytest -q -p no:randomly` passes, `uv run ruff check .` is clean, and `uv run ruff format --check .` and `uv run mypy src/` are no worse than the Before Task 1 baseline.
  - During a task, run only its own test files; run the gate once, before the commit.
- `npm run e2e` builds and serves on :4174 with `strictPort`, so only one worktree can run it at a time (CLAUDE.md Gotchas).
- CLAUDE.md: "Use context7 to check latest docs and for external dependencies." This plan has no code-architect or /simplify task. They run once on the PR after it opens (CLAUDE.md).

## Decisions already made

These fill gaps in the spec. The owner sees them in the plan's report. Reviewers: don't reverse one without asking.

1. **The v2 handshake.** §12.4 names a handshake but doesn't define it.
   - `subscribe_frames` carries `"protocol": 2`. The server's ack echoes `"protocol": 2` when it switches the session to v2. This is the engine M2 plan's Spec Ruling 3, so the two sides agree.
   - Any other ack means v1, capped at 30 fps. M2 sends `"protocol": 1` for a v1 session, and M1 sends no `protocol` at all.
   - An `fps` in the ack would cap the measured frame rate. M2's ack sends none, so v2's cap is 60.
   - Binary messages that arrive before the ack are dropped.
2. **The clock offset.** §12.4 estimates it "from ping round-trips", but there is no ping command. The client takes the smallest `receivedAt − server_time` over the last 64 beat messages, the least-delayed one. `server_time` is seconds since the Unix epoch, as a float, and `beat_in_bar` counts 1–4 like v1's `beat_pos`. Engine M3, which adds them, should say so.
3. **The measured frame rate.** "Live 60 fps" is the most frames any one light received in the last second, averaged with the second before, and capped at the rate the server granted. With no frames flowing it is `null`, and the indicator shows "Live" alone.
4. **Home map names.** §12.2 has no types for walls, columns, furniture, the outdoor areas, `size` or `wallCutHeight`. They take `home.json`'s names and shapes, which M2 also keeps (its Spec Ruling 7).
5. **Envelopes and cases.** §12.4 lists payloads without their keys. `decks` arrives as `{ decks: [...] }`, `signals` as `{ values: {...} }` and `inputs` as `{ inputs: {...} }`. `inputs` uses the contract's camelCase like the other pushed snapshots (`updated_at` becomes `updatedAt`). The beat and stats stay snake_case as today. `fx` is typed but ignored until F10.
6. **Pending types are provisional.** Everything M2 and later milestones add is written in `contract.ts`, from §12 and, where it rules, from the engine M2 plan.
   - `PlacementState` is the answer to a placement request, from M2's Spec Ruling 16.
   - `Inputs` and `Signal` are shaped from §12.3–12.4 and the Inputs renders.
   - M2's Spec Ruling 4 gives the PC's parts an `id`. The mock's fixtures give each part `${light}-part-N` now, and the generated `Light` carries the field once M2 serves it.
   - The milestone that serves a type owns its final shape. When the backend serves a schema or path with the same name, `contract.test.ts` fails `tsc -b` until the pending type is swapped for the generated one. That swap is Task 15's, or M2's last task's if F1 merges first.
7. **Attention order is the server's.** §9.5: severity, then newest first, as M1's feed sorts. The State-Problems render lists its items in another order; the mock follows §9.5, and the render's order isn't reproduced.
8. **Scenarios.**
   - An eleventh one, `preview-only`, is the hero with preview only on (the State-Preview-Only render).
   - Times are relative to now, so a clock fixed at 19:14 shows the renders' times.
   - `?still` holds the beat (one beat message, then none) for screenshots and the render counts.
   - The mock serves the handoff's 29 looks, with `needs` taken from each look's `inputs`, as M1 maps its built-ins.
   - Zone names come from `home.json`. Its room `corridor` is named "Corridor", while §12.5 and the renders say "Entrance". The mock keeps "Corridor", because that is what M2 will seed; a new handoff can rename the room.
   - Attention titles and details copy M1's `zones/attention.py` for the kinds M1 raises. The two input items, which M1 can't raise yet, use the render's words.
   - State-Nothing-Running's "Start again" list has no endpoint in §12.3. F3 raises it with the engine track; the mock doesn't invent one.
9. **Today's beat.** M1's v1 beat has no source, bar or server time. It reads as source Pro DJ Link, with no bar (the module hides "bar N"), and its pips stop while `is_playing` is false. With no DJ, M1 sends bpm 0, which shows as "0.0" until M3's internal clock.
10. **The chrome's other values stay on the fixture** until the milestone that owns them. That is preview only (F3), the server's name in the rail (F6) and today's sunset in the phone's Live line (F6). F1 moves only the connection, the tempo and the attention to the stores, as the owner asked.
11. **Mocks run in dev only with `?scenario=`, and always in the mock build.** `npm run dev` talks to the real backend through the proxy unless a scenario is asked for. `npm run build:mock` builds `web/dist-mock`, which always mocks (hero by default), and it is what Playwright serves. `npm run build` checks that `web/dist` has no trace of MSW.
12. **The schema comes from the code.** `scripts/dump_openapi.py` builds the app over stand-ins and prints its schema, so generation needs no running server. `--url` compares a running server's schema with the committed one and only reads it. The old UI's catch-all `/{full_path}` leaves the schema (`include_in_schema=False`), so a deployed server and the code agree.
13. **REST URLs are absolute** (`new URL(path, location.origin)`). Node's `fetch`, which Vitest and MSW's Node server use, rejects relative URLs.

## Review Focus

These are the five failure modes the spec implies that are most likely to bite someone using the app, most likely first. Each has a test in the task that owns the code.

1. **The link drops, or the server restarts, mid-session.**
   - Expected: "Reconnecting" at once on a close event, within 4 s if the link just goes silent.
   - Retries follow 1, 2, 4, 8, 10, 10 s, with one socket at a time and each subscription sent once per connection. Late messages from a dead socket are ignored.
   - On return, the stores and REST data resync, and frame seqs that restart at 1 are accepted.
   - Pinned in Task 7:
     - "drops to Reconnecting at once on a close, then retries after 1, 2, 4, 8, 10 and 10 s"
     - "drops a link that has gone silent for 3 s"
     - "keeps one socket: Try now opens one, and a dead socket's late messages are ignored"
     - "resyncs on reconnect: seqs restart, the beat clock re-anchors and REST refetches"
   - Pinned in Task 13, in the browser: "says Reconnecting within 2 s of a drop, and counts the retries".
2. **First load, before the server has said anything, or with the server down.**
   - The chrome must not claim "All good", show a tempo or say "Live" until it knows. With the server down it says "Reconnecting".
   - Pinned in Task 12:
     - "shows no tempo, no All good and no Live before the server speaks"
     - "says Reconnecting, not All good, when the server is down from the start"
3. **Today's backend (engine M1), before M2 and M3 land.**
   - It sends v1 frames, a v1 beat with no source, bar or server time, an ack with no protocol, and bpm 0 with no DJ. All of it must work, without a crash.
   - Pinned in:
     - Task 5: "reads today's v1 beat as Pro DJ Link with no bar"
     - Task 7: "falls back to v1 frames at 30 fps when the ack has no protocol"
     - Task 10: "speaks today's protocol to a LiveClient over MSW"
     - Task 12: "holds the pips still when no DJ plays"
4. **The beat across a bar line, and a server clock that disagrees with the browser's.**
   - The phase wraps from ~1 to ~0 without a backwards jump. The beat in the bar goes 4 to 1, and the bar number counts up.
   - A server clock seconds away, or jittery delivery, neither snaps the clock around nor makes it drift.
   - Pinned in Task 5:
     - "wraps the beat and the bar without a jump"
     - "corrects a v1 beat across the bar line forwards, not back"
     - "follows a server clock 2 s ahead through jittery delivery"
5. **Malformed or truncated input.**
   - The inputs: a short frame, an id length past the end, a ragged RGB tail, an unknown stream byte, a non-UTF-8 id, bad JSON, or a snapshot missing its list.
   - Each is dropped and counted, and every other light's buffer is untouched.
   - A light whose LED count changes, or that has none, gets a new buffer.
   - Pinned in:
     - Task 4: "drops and counts %s, and leaves the other lights alone"
     - Task 4: "reallocates when the LED count changes, and takes a light with no LEDs"
     - Task 7: "drops bad JSON and counts it, and the next message still lands"

---

## File Structure

```
scripts/dump_openapi.py                  prints the backend's OpenAPI schema (no server needed)
src/dj_ledfx/web/app.py                  the old UI's catch-all leaves the schema
tests/web/test_openapi_types.py          the committed schema is the backend's
web/
  package.json                           + zustand, @tanstack/react-query, msw, openapi-typescript;
                                         scripts api:types, api:check, build:mock; "msw" worker dir
  vite.config.ts                         a function of the mode: dist-mock, no public dir in production
  playwright.config.ts                   serves the mock build
  tsconfig.app.json                      + resolveJsonModule
  tsconfig.node.json                     + scripts/
  eslint.config.js, .gitignore           + dist-mock, the generated types
  public/mockServiceWorker.js            MSW's worker (npx msw init); copied into the mock build only
  scripts/
    generate-types.ts                    openapi-typescript over a schema's text; describeDrift()
    api-types.ts                         write, --check, --url
    check-dist.ts                        fails if MSW reached a build, or its JS passes 400 KB gzipped
  src/api/
    generated/openapi.json, schema.d.ts  generated, committed
    generated/schema.node.test.ts        schema.d.ts is what openapi.json generates
    contract.ts                          §12.2 types: generated aliases + pending ones (M2, M3, M6/M7)
    ws-messages.ts                       §12.4 server messages and client commands; parseMessage()
    rest.ts                              api.*, ApiError, apiPath()
    frames.ts                            FrameStore, decodeFrame(), encodeFrame(), IdTable
    beat.ts                              Beat, normaliseBeat(), ClockOffset, BeatClock, clientNow()
    live-store.ts                        LiveState, liveStore, applyMessage(), useLive(), Connection
    live-client.ts                       LiveClient (one socket, backoff, watchdog, resync, fps)
    queries.ts                           queryClient, queries.*, resync()
    live.ts                              the app's singletons; startDataLayer()
    mocks/
      home.json, looks.json              byte copies of docs/design/web-app/
      fixtures.ts                        home, lights, looks and zones from the copies
      scenarios.ts                       the eleven scenarios; orderAttention()
      frame-generator.ts                 motifFor(), paint(): simple animated looks
      mock-server.ts                     MockServer: REST, channels, frames; snapshotMessages()
      in-memory-socket.ts                a LiveSocket wired straight to a MockServer
      handlers.ts                        MSW handlers over a MockServer
      choice.ts                          mockChoice(): which mock the URL asks for (no MSW import)
      browser.ts                         startMocks(): MSW's worker over a MockServer
  src/chrome/
    state.ts                             types and the hero fixture (useChrome() goes)
    hooks.ts                             useTempo(), useConnection(), useAttentionCounts(), …
    live.tsx                             ChromeTempo, ChromeTempoStrip, ChromeAttention, …
    live.test.tsx                        render counts: a beat redraws the tempo module alone
    tempo-module.tsx, connection-indicator.tsx   a missing bar, a missing fps, 'connecting'
  src/shell/                             top bar, phone header, rail, tab bar, nav dot and
                                         AppShell read slices, not a ChromeState
  src/app/page-meta.ts, routes.tsx       MetaContext carries the sunset, not the chrome
  src/app/live-performance.test.tsx      done when: 60 fps from the mock, no React commits
  src/main.tsx                           mocks (dev with ?scenario=, mock build), data layer, query client
  src/test/                              fake-socket.ts (a scriptable socket), live.ts (seedLive()),
                                         app.tsx (renderApp()), count-renders.ts
  e2e/shell.spec.ts, e2e/live.spec.ts    wait for data; the reconnecting scenario
CLAUDE.md                                Commands, Architecture, Gotchas
```

Tests sit beside the code they test. A `*.node.test.ts` file runs in Node and is type-checked by `tsconfig.node.json`. A test that needs Node's globals but imports app code (with the `@/` alias) is a plain `*.test.ts` whose first line is `// @vitest-environment node`.

## Before Task 1

- [ ] **Step 1: Create the worktree from `master`**

```bash
git -C /home/anirudhlath/code/private/dj-ledfx fetch origin
git -C /home/anirudhlath/code/private/dj-ledfx worktree add -b feature/web-f1-data-layer /home/anirudhlath/code/.worktrees/dj-ledfx/web-f1 origin/master
W=/home/anirudhlath/code/.worktrees/dj-ledfx/web-f1
cd "$W"
test -f docs/superpowers/plans/2026-09-24-f1-data-layer.md && test -f web/src/chrome/state.ts && echo "plan and F0 present"
test -f src/dj_ledfx/web/contract.py && test -f src/dj_ledfx/zones/attention.py && echo "M1 present"
test -f src/dj_ledfx/web/router_home.py && echo "M2 merged" || echo "M2 not merged yet"
```

Expected: `plan and F0 present` and `M1 present`. If either is missing, stop and tell the owner. Either M2 line is fine. If M2 has merged, Task 1 generates its types too, and Task 2's type test flags the pending types it replaced. Swap them as Task 15 Step 3 describes, in Task 2, before going on. Every command runs from `$W`; commands for the app run in a subshell, `(cd web && …)`.

- [ ] **Step 2: Install**

```bash
uv sync --extra web
node --version
(cd web && npm ci)
(cd docs/design/web-app && sha256sum -c --ignore-missing HANDOFF.sha256)
```

Expected: Node is v22.22.2+, v24.15+ or v26+ (Node runs the `scripts/*.ts` files directly, by type stripping). Every design file prints `OK`. Without the `web` extra, the web tests skip silently.

- [ ] **Step 3: Record the baselines**

```bash
uv run pytest -q -p no:randomly 2>&1 | tail -1
uv run ruff check . && uv run ruff format --check . 2>&1 | tail -1
uv run mypy src/ 2>&1 | tee /tmp/f1-baseline-mypy.txt | tail -1
(cd web && npm test 2>&1 | tail -4 && npm run lint && npx tsc -b && echo "tsc ok")
```

Expected on `master` at `6425b11` (2026-09-24):
- pytest: `957 passed, 1 skipped, 7 deselected`.
- `ruff check` is clean, and `ruff format --check` finds nothing to change.
- mypy: `Found 17 errors in 5 files`, all pre-existing.
- Vitest: 80 tests in 14 files, all passing; lint clean; `tsc ok`.

Write the results down. F1 must not add a mypy error or a format finding. If `master` has moved, record what it says now.

- [ ] **Step 4: Record the Playwright baseline**

```bash
(cd web && npx playwright install chromium && npm run e2e 2>&1 | tail -3)
```

Expected: `56 passed`, `16 skipped`. The three committed screenshots must still match after Task 12 without being re-recorded: F1 changes where the chrome's data comes from, not how it looks.

---

### Task 1: Types from the backend, and a check that they haven't drifted

Implements spec §12 ("generated OpenAPI types"), §3.3 (openapi-typescript) and the owner's drift check: a check that fails when the generated types drift from the backend's schema. Decision 12. No renders.

**Files:**
- Modify: `src/dj_ledfx/web/app.py:191` (the old UI's catch-all)
- Create: `scripts/dump_openapi.py`
- Test: `tests/web/test_openapi_types.py`
- Create: `web/scripts/generate-types.ts`, `web/scripts/api-types.ts`
- Create (generated, committed): `web/src/api/generated/openapi.json`, `web/src/api/generated/schema.d.ts`
- Test: `web/src/api/generated/schema.node.test.ts`
- Modify: `web/package.json`, `web/package-lock.json` (npm writes it), `web/tsconfig.node.json`, `web/eslint.config.js`

**Interfaces:**
- Consumes: `create_app(...)` from `src/dj_ledfx/web/app.py`, and `static_client()` and `write_dist()` from `tests/web/conftest.py`.
- Produces:
  - `scripts/dump_openapi.py`, which prints the schema to stdout with sorted keys and a two-space indent. It exposes `openapi_schema() -> dict[str, Any]` and `schema_text(schema) -> str`.
  - `web/src/api/generated/schema.d.ts`, openapi-typescript's output. It exports `paths` (keys like `'/api/zones/{zone_id}/start'`) and `components` (`components['schemas']['Look']`, …).
  - `generateTypes(schemaText: string): Promise<string>` and `describeDrift(committed: unknown, other: unknown): string[]` in `web/scripts/generate-types.ts`.
  - npm scripts `api:types` (write) and `api:check` (`--check`, optionally `--url <server>`).

- [ ] **Step 1: Read the spec and the library**

Re-read spec §12's opening paragraph, §12.1 and §3.3. With context7, check openapi-typescript 7's Node API: `openapiTS(schemaObject)` returns the AST, and `astToString(ast)` prints it. The CLI adds its own banner, and the Node API adds none. This plan uses the Node API, so `generateTypes()` owns the banner.

- [ ] **Step 2: Write the failing Python test**

`tests/web/test_openapi_types.py`:

```python
"""The web app's generated API types follow the backend's schema (web/src/api/generated/)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tests.web.conftest import static_client, write_dist

REPO = Path(__file__).resolve().parents[2]
COMMITTED = REPO / "web" / "src" / "api" / "generated" / "openapi.json"
FIX = "the API changed: run `cd web && npm run api:types` and commit web/src/api/generated/"


def dumped_schema() -> str:
    result = subprocess.run(
        [sys.executable, "scripts/dump_openapi.py"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def test_the_committed_schema_is_the_backends() -> None:
    assert COMMITTED.read_text(encoding="utf-8") == dumped_schema(), FIX


def test_the_old_ui_catch_all_stays_out_of_the_schema(tmp_path: Path) -> None:
    # A deployed server has the old UI's dist, so its catch-all route is registered there and
    # would make the served schema differ from the code's (npm run api:check -- --url).
    write_dist(tmp_path, "<html>old</html>")
    paths = static_client(tmp_path).get("/openapi.json").json()["paths"]
    assert "/{full_path}" not in paths
    assert "/api/running" in paths
```

- [ ] **Step 3: Run it to see it fail**

Run: `uv run pytest tests/web/test_openapi_types.py -v`
Expected: both FAIL. The first fails with `FileNotFoundError`, since nothing is committed yet, and the second with `assert '/{full_path}' not in {…}`.

- [ ] **Step 4: Take the catch-all out of the schema, and write the dump script**

In `src/dj_ledfx/web/app.py`, change the decorator at line 191:

```python
        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str) -> FileResponse:
```

Create `scripts/dump_openapi.py`:

```python
"""Print the web API's OpenAPI schema, as web/src/api/generated/openapi.json holds it.

The web app's types are generated from this (cd web && npm run api:types). Nothing runs: the app
is built over stand-ins and only its schema is read, so no server or device is needed.
"""

from __future__ import annotations

import json
import sys
from typing import Any
from unittest.mock import MagicMock

from dj_ledfx.web.app import create_app


def openapi_schema() -> dict[str, Any]:
    """The schema FastAPI serves at /openapi.json."""
    app = create_app(
        beat_clock=MagicMock(),
        effect_engine=MagicMock(),
        device_manager=MagicMock(),
        scheduler=MagicMock(),
        preset_store=MagicMock(),
        scene_model=None,
        compositor=None,
        config=MagicMock(web=MagicMock(cors_origins=["*"], static_dir=None)),
        config_path=None,
    )
    return app.openapi()


def schema_text(schema: dict[str, Any]) -> str:
    """The committed file's text: sorted keys, a two-space indent and one trailing newline."""
    return json.dumps(schema, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    sys.stdout.write(schema_text(openapi_schema()))
```

Run: `uv run python scripts/dump_openapi.py | head -5`
Expected: JSON starting with `{`, then `"components": {`.

- [ ] **Step 5: Install the generator**

```bash
(cd web && npm install -D openapi-typescript@^7.13.0)
```

- [ ] **Step 6: Write the failing web test**

`web/src/api/generated/schema.node.test.ts`:

```ts
// @vitest-environment node
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { describeDrift, generateTypes } from '../../../scripts/generate-types.ts'

// If the first test fails, openapi.json and schema.d.ts disagree, or openapi-typescript changed its
// output: run `npm run api:types` in web/ and commit both files.
const read = (name: string) => readFileSync(resolve(import.meta.dirname, name), 'utf8')

describe('generated API types', () => {
  it('schema.d.ts is what openapi.json generates', async () => {
    expect(await generateTypes(read('openapi.json'))).toBe(read('schema.d.ts'))
  })

  it('opens with a banner that names the command', async () => {
    const empty = '{"openapi":"3.1.0","info":{"title":"t","version":"0"},"paths":{}}'
    expect(await generateTypes(empty)).toMatch(/^\/\/ Generated by `npm run api:types`/)
  })
})

describe('describeDrift', () => {
  const doc = (paths: string[], schemas: string[]) => ({
    paths: Object.fromEntries(paths.map((path) => [path, {}])),
    components: { schemas: Object.fromEntries(schemas.map((name) => [name, {}])) },
  })

  it('finds nothing when the schemas are the same', () => {
    expect(describeDrift(doc(['/api/looks'], ['Look']), doc(['/api/looks'], ['Look']))).toEqual([])
  })

  it('names the paths and schemas only one side has', () => {
    const committed = doc(['/api/looks', '/{full_path}'], ['Look'])
    const backend = doc(['/api/looks', '/api/home'], ['Look', 'Home'])
    expect(describeDrift(committed, backend)).toEqual([
      'paths /api/home: only the backend has it',
      'paths /{full_path}: only the committed schema has it',
      'schemas Home: only the backend has it',
    ])
  })

  it('says the details differ when the names match', () => {
    const changed = doc(['/api/looks'], ['Look'])
    changed.components.schemas.Look = { type: 'object' }
    expect(describeDrift(doc(['/api/looks'], ['Look']), changed)).toEqual([
      'same paths and schemas, but their details differ',
    ])
  })
})
```

Run: `(cd web && npx vitest run src/api/generated)`
Expected: FAIL, with `Failed to load url ../../../scripts/generate-types.ts`.

- [ ] **Step 7: Write the generator and the script**

`web/scripts/generate-types.ts`:

```ts
import { isDeepStrictEqual } from 'node:util'
import openapiTS, { astToString } from 'openapi-typescript'

const BANNER = `// Generated by \`npm run api:types\` from the backend's OpenAPI schema (openapi.json beside it).
// Don't edit it: change the backend, then run the command again.
`

/** schema.d.ts's text for an OpenAPI document's text. */
export async function generateTypes(schemaText: string): Promise<string> {
  const ast = await openapiTS(JSON.parse(schemaText))
  return BANNER + astToString(ast)
}

type Document = { paths?: object; components?: { schemas?: object } }

function names(document: unknown, part: 'paths' | 'schemas'): Set<string> {
  const doc = document as Document
  return new Set(Object.keys((part === 'paths' ? doc.paths : doc.components?.schemas) ?? {}))
}

/** How two schemas differ, one line per path or schema only one of them has; [] if they're equal. */
export function describeDrift(committed: unknown, other: unknown): string[] {
  if (isDeepStrictEqual(committed, other)) return []
  const lines: string[] = []
  for (const part of ['paths', 'schemas'] as const) {
    const ours = names(committed, part)
    const theirs = names(other, part)
    for (const name of theirs) if (!ours.has(name)) lines.push(`${part} ${name}: only the backend has it`)
    for (const name of ours) if (!theirs.has(name)) lines.push(`${part} ${name}: only the committed schema has it`)
  }
  return lines.length > 0 ? lines : ['same paths and schemas, but their details differ']
}
```

`web/scripts/api-types.ts`:

```ts
// Writes, or checks, web/src/api/generated/: the backend's OpenAPI schema and the TypeScript types
// openapi-typescript makes from it (spec §12, "generated OpenAPI types").
//   npm run api:types                       write both files from the backend's code
//   npm run api:check                       fail if the committed files aren't what the code makes
//   npm run api:check -- --url <server>     also fail if a running server's schema differs (GET only)
import { execFileSync } from 'node:child_process'
import { readFileSync, writeFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { parseArgs } from 'node:util'
import { describeDrift, generateTypes } from './generate-types.ts'

const WEB = resolve(import.meta.dirname, '..')
const SCHEMA = resolve(WEB, 'src/api/generated/openapi.json')
const TYPES = resolve(WEB, 'src/api/generated/schema.d.ts')

const { values } = parseArgs({
  options: { check: { type: 'boolean', default: false }, url: { type: 'string' } },
})

/** The schema the backend's code serves, as scripts/dump_openapi.py prints it. */
function backendSchema(): string {
  return execFileSync('uv', ['run', 'python', 'scripts/dump_openapi.py'], {
    cwd: resolve(WEB, '..'),
    encoding: 'utf8',
  })
}

if (!values.check && values.url === undefined) {
  const schema = backendSchema()
  writeFileSync(SCHEMA, schema)
  writeFileSync(TYPES, await generateTypes(schema))
  console.log('api types: wrote src/api/generated/openapi.json and schema.d.ts')
} else {
  const problems: string[] = []
  const committed = readFileSync(SCHEMA, 'utf8')
  if (values.check) {
    const schema = backendSchema()
    if (schema !== committed) {
      const drift = describeDrift(JSON.parse(committed), JSON.parse(schema))
      problems.push(...(drift.length > 0 ? drift : ['openapi.json is formatted differently']).map((line) => `code: ${line}`))
    }
    if (readFileSync(TYPES, 'utf8') !== (await generateTypes(committed))) {
      problems.push('schema.d.ts is not what openapi.json generates')
    }
  }
  if (values.url !== undefined) {
    const served: unknown = await (await fetch(new URL('/openapi.json', values.url))).json()
    problems.push(...describeDrift(JSON.parse(committed), served).map((line) => `${values.url}: ${line}`))
  }
  if (problems.length > 0) {
    console.error(['api types drifted:', ...problems.map((line) => `  ${line}`), 'Run: cd web && npm run api:types'].join('\n'))
    process.exit(1)
  }
  console.log('api types match')
}
```

In `web/package.json`, add to `"scripts"`:

```json
    "api:types": "node scripts/api-types.ts",
    "api:check": "node scripts/api-types.ts --check",
```

In `web/tsconfig.node.json`, add `scripts` to `include`:

```json
  "include": ["vite.config.ts", "playwright.config.ts", "e2e", "scripts", "src/**/*.node.test.ts"]
```

In `web/eslint.config.js`, ignore the generated declarations:

```js
  globalIgnores(['dist', 'playwright-report', 'test-results', 'src/api/generated/schema.d.ts']),
```

- [ ] **Step 8: Generate the types**

```bash
(cd web && npm run api:types)
grep -c '"/api/' web/src/api/generated/openapi.json
grep -c 'full_path' web/src/api/generated/openapi.json
grep -n 'status: "streaming"' web/src/api/generated/schema.d.ts
```

Expected:
- `api types: wrote …`.
- The first count is 37 on `6425b11`, or more if M2 has merged.
- The second count is `0`.
- The last line shows `Light.status`'s union, which includes `"idle"` (M1's addition to §12.2).

- [ ] **Step 9: Run the tests**

```bash
uv run pytest tests/web/test_openapi_types.py -v
(cd web && npx vitest run src/api/generated && npm run api:check)
```

Expected: 2 passed; 5 passed; `api types match`.

- [ ] **Step 10: Compare with the deployed server (optional, read-only)**

```bash
(cd web && npm run api:check -- --url http://127.0.0.1:8080)
```

This only GETs `/openapi.json`. Expected, until this branch is deployed: exit 1 with one line, `http://127.0.0.1:8080: paths /{full_path}: only the backend has it`. The deployed server still registers the old UI's catch-all in its schema, and that difference shows the check works. Any other line means the deployed server runs different code from this branch's `master`; write it down for the PR. If nothing answers on 8080, skip this step. Never restart or reconfigure the container.

- [ ] **Step 11: Gate and commit**

Run the Python gate (Global Constraints) and the web gate. Then:

```bash
uv run ruff format scripts/dump_openapi.py tests/web/test_openapi_types.py src/dj_ledfx/web/app.py
git add scripts/dump_openapi.py tests/web/test_openapi_types.py src/dj_ledfx/web/app.py web/package.json web/package-lock.json web/tsconfig.node.json web/eslint.config.js web/scripts web/src/api/generated
git commit -m "feat(web): generate API types from the backend's OpenAPI schema, with a drift check"
```

---

### Task 2: The contract's types and the socket's messages

Implements spec §12.2 (domain types) and §12.4 (channels and commands), and decisions 1, 2, 4, 5 and 6. No renders.

**Files:**
- Create: `web/src/api/contract.ts`, `web/src/api/ws-messages.ts`
- Test: `web/src/api/contract.test.ts`, `web/src/api/ws-messages.test.ts`

**Interfaces:**
- Consumes: `components` and `paths` from `web/src/api/generated/schema.d.ts` (Task 1).
- Produces, from `contract.ts`:
  - Served today (generated aliases): `Id`, `ApiPath`, `Look`, `Layer`, `LookModifiers`, `Transition`, `Zone`, `CreateGroup`, `UpdateGroup`, `RunningZone`, `Overlay`, `Running`, `StartRequest`, `StartResponse`, `TakeOver`, `AttentionItem`, `InputKind`, `LightStatus`, `Light` (with `shape: LightShape | null`), `LightUpdate`.
  - Pending on engine M2: `Vec2`, `Vec3`, `Room`, `SubZone`, `Anchor`, `AnchorInput`, `SubZoneInput`, `Wall`, `Box2`, `Furniture`, `Outdoor`, `Location`, `Home`, `HomeUpdate`, `LightShape`, `Placement`, `PlacementState`, `PreviewRequest`, `PreviewResponse`, `FrameStream`.
  - Pending on M3: `TempoSource`, `TempoLock`, `Deck`.
  - Pending on M6/M7: `InputState`, `TempoInput`, `ProDjLinkInput`, `MusicInput`, `HomeAssistantEntity`, `HomeAssistantInput`, `SunInput`, `Inputs`, `SignalValue`, `Signal`.
  - `PendingSchema` and `PendingPath`, string unions of the pending names.
- Produces, from `ws-messages.ts`:
  - `BeatV1`, `BeatV2`, `BeatMessage`, `DecksMessage`, `RunningMessage`, `LightsMessage`, `AttentionMessage`, `TransportMessage`, `DeviceStat`, `StatsMessage`, `StatusMessage`, `AckMessage`, `ErrorMessage`, `InputsMessage`, `SignalsMessage`, `FxMessage` and `ServerMessage`, their union.
  - `ClientCommand`, and `Command` (a command without its `id`).
  - `parseMessage(text: string): ServerMessage | null`.

- [ ] **Step 1: Read the spec**

Re-read §12.2, §12.3 and §12.4, and decisions 1, 2, 4, 5 and 6. Open `docs/design/web-app/home.json` for the names decision 4 takes. Read engine M2's Spec Rulings 3, 4 and 7 in `docs/superpowers/plans/2026-09-24-m2-3d-fields.md`.

- [ ] **Step 2: Write the failing tests**

`web/src/api/contract.test.ts` is checked by `tsc -b`, not at run time: an `expectTypeOf` that doesn't hold is a type error.

```ts
import { describe, expectTypeOf, it } from 'vitest'
import type { components, paths } from './generated/schema'
import type { ApiPath, InputKind, Light, LightShape, LightStatus, PendingPath, PendingSchema, RunningZone } from './contract'

describe('the contract', () => {
  // When the backend starts serving one of these, this fails tsc -b: swap the hand-written type
  // for the generated one in contract.ts (plan Task 15, Step 3).
  it('has no pending type the backend already serves', () => {
    expectTypeOf<Extract<PendingSchema, keyof components['schemas']>>().toEqualTypeOf<never>()
    expectTypeOf<Extract<PendingPath, keyof paths>>().toEqualTypeOf<never>()
  })

  it("carries §12.2's unions from the generated types", () => {
    expectTypeOf<RunningZone['state']>().toEqualTypeOf<'running' | 'slow' | 'crashed' | 'waiting' | 'transition'>()
    expectTypeOf<LightStatus>().toEqualTypeOf<
      'streaming' | 'own-effect' | 'streamed-copy' | 'offline' | 'switched-off' | 'reconnecting' | 'idle'
    >()
    expectTypeOf<InputKind>().toEqualTypeOf<'tempo' | 'music' | 'home-assistant' | 'sun'>()
    expectTypeOf<ApiPath>().toExtend<string>()
  })

  it("types a light's shape as §12.2 does", () => {
    expectTypeOf<Light['shape']>().toEqualTypeOf<LightShape | null | undefined>()
  })
})
```

`web/src/api/ws-messages.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { parseMessage } from './ws-messages'

describe('parseMessage', () => {
  it('reads a channel message', () => {
    expect(parseMessage('{"channel":"transport","state":"simulating"}')).toEqual({ channel: 'transport', state: 'simulating' })
  })

  it.each([
    ['bad JSON', '{"channel":'],
    ['a message with no channel', '{"state":"playing"}'],
    ['a channel that is not a string', '{"channel":7}'],
    ['JSON that is not an object', '[1,2]'],
    ['a running snapshot without its zones', '{"channel":"running","overlays":[]}'],
    ['a lights snapshot whose lights are not a list', '{"channel":"lights","lights":{}}'],
    ['an attention snapshot without its items', '{"channel":"attention"}'],
    ['stats without devices', '{"channel":"stats"}'],
    ['a beat without a bpm', '{"channel":"beat","beat_phase":0.5}'],
  ])('returns null for %s', (_, text) => {
    expect(parseMessage(text)).toBeNull()
  })

  it('passes a channel it does not know, for the caller to ignore', () => {
    expect(parseMessage('{"channel":"later","x":1}')).toEqual({ channel: 'later', x: 1 })
  })
})
```

- [ ] **Step 3: Run them to see them fail**

```bash
(cd web && npx vitest run src/api/ws-messages.test.ts; npx tsc -b)
```

Expected: Vitest fails with `Failed to load url ./ws-messages`. `tsc -b` fails with `Cannot find module './contract'`.

- [ ] **Step 4: Write `contract.ts`**

```ts
// The data contract (spec §12.2). What the backend serves is generated from its OpenAPI schema
// (generated/schema.d.ts, `npm run api:types`). What it doesn't serve yet is written here from §12,
// marked with the engine milestone that brings it, and mocked until then (src/api/mocks/).
// contract.test.ts fails once the backend serves a pending name: swap in the generated type then.
import type { components, paths } from './generated/schema'

type Schemas = components['schemas']

export type Id = string
/** Every REST path the backend serves today. */
export type ApiPath = keyof paths

// ── Served today (engine M1) ──────────────────────────────────────────────────────────────
export type Look = Schemas['Look']
export type Layer = Schemas['Layer']
export type LookModifiers = Schemas['LookModifiers']
export type Transition = Schemas['Transition']
export type Zone = Schemas['Zone']
export type CreateGroup = Schemas['CreateGroup']
export type UpdateGroup = Schemas['UpdateGroup']
export type RunningZone = Schemas['RunningZone']
export type Overlay = Schemas['Overlay']
export type Running = Schemas['Running']
export type StartRequest = Schemas['StartRequest']
export type StartResponse = Schemas['StartResponse']
export type TakeOver = Schemas['TakeOver']
export type AttentionItem = Schemas['AttentionItem']
export type InputKind = NonNullable<Look['needs']>[number]
export type LightStatus = Schemas['Light']['status']
/** A light (§12.2). The backend types `shape` loosely until engine M2 serves the home map. */
export type Light = Omit<Schemas['Light'], 'shape'> & { shape?: LightShape | null }
/** One light on the socket's `lights` channel. */
export type LightUpdate = Pick<Light, 'id' | 'status' | 'statusSince' | 'ownEffect' | 'power' | 'colour'>

// ── Pending: engine M2 (home map, preview runtimes, frame protocol v2) ────────────────────
// §12.2's Home, Room, SubZone, Anchor and LightShape; home.json's names for what §12.2 leaves out
// (decision 4).
export type Vec2 = [number, number]
export type Vec3 = [number, number, number]
export interface Room { id: Id; name: string; polygon: Vec2[]; labelAt: Vec2; hasLights: boolean }
export interface SubZone { id: Id; name: string; room: Id; polygon: Vec2[] }
export interface Anchor { id: Id; name: string; position: Vec3; points?: Vec3[]; confirmed: boolean }
export interface Wall {
  a: Vec2
  b: Vec2
  kind: 'wall' | 'window' | 'glass-door'
  westFacing: boolean
  exterior: boolean
  thickness: number
}
export interface Box2 { min: Vec2; max: Vec2 }
export interface Furniture {
  id: Id
  name: string
  height: number
  z0: number
  confirmed: boolean
  /** [x0, y0, x1, y1] on the plan. */
  box: [number, number, number, number]
}
export interface Outdoor { courtyard: Vec2[]; balcony: Vec2[]; courtyardOpensTo: string; balconyOffRoom: Id }
export interface Location { name: string; lat: number; lon: number; confirmed: boolean }
export interface Home {
  outline: Vec2[]
  rooms: Room[]
  subZones: SubZone[]
  walls: Wall[]
  columns: Box2[]
  furniture: Furniture[]
  anchors: Anchor[]
  ceiling: number
  beams: number
  northOffsetDeg: number
  location: Location
  size: { eastWest: number; northSouth: number }
  wallCutHeight: number
  outdoor: Outdoor
}
/** PUT /home: "north, ceiling, beams, location" (§12.3). */
export type HomeUpdate = Partial<Pick<Home, 'northOffsetDeg' | 'ceiling' | 'beams' | 'location'>>
export type AnchorInput = Omit<Anchor, 'id' | 'confirmed'>
export type SubZoneInput = Omit<SubZone, 'id'>
export type LightShape =
  | { kind: 'point'; position: Vec3 }
  | { kind: 'line'; path: [Vec3, Vec3] }
  | { kind: 'bent-line'; path: Vec3[] }
  | { kind: 'cylinder'; base: Vec3; height: number; radius: number }
  | { kind: 'grid'; center: Vec3; width: number; depth: number; rotation: Vec3 }
/** PUT /lights/{id}/placement: "shape, position, rotation, size, ledOrder" (§12.3). */
export interface Placement { shape: LightShape; ledOrder?: string }
/** What a placement request answers: the placement (engine M2 plan, Spec Ruling 16). */
export interface PlacementState { shape: LightShape | null; ledOrder: string | null; confirmed: boolean; confirmedAt: string | null }
export interface PreviewRequest { zoneId: Id; lookId?: Id; look?: Look }
export interface PreviewResponse { previewId: Id }
/** The binary frame's stream byte (§12.4): 0x01 live, 0x02 preview. */
export type FrameStream = 'live' | 'preview'

// ── Pending: engine M3 (the tempo source chain) ───────────────────────────────────────────
export type TempoSource = 'prodjlink' | 'music' | 'internal'
export type TempoLock = 'auto' | TempoSource
/** One player on the socket's `decks` channel (§12.4, snake_case like the beat). */
export interface Deck {
  number: number
  player: string
  state: 'empty' | 'cued' | 'playing'
  bpm: number | null
  pitch_percent: number
  master: boolean
}

// ── Pending: engine M6/M7 (Music Assistant, Home Assistant, the sun, signals) ─────────────
// Shaped from §12.3–12.4, §9.3 and the Inputs renders; the milestone that serves them owns the
// final shape (decision 6).
export type InputState = 'connected' | 'stale' | 'disconnected' | 'idle'
export interface TempoInput { source: TempoSource; lock: TempoLock; bpm: number; stale: boolean }
export interface ProDjLinkInput { state: InputState; interface: string; lastSet: { from: string; to: string } | null }
export interface MusicInput {
  state: InputState
  track: { title: string; artist: string } | null
  group: string[]
  loudness: number
  lufs: number
  /** 32 bands, 0–1. */
  spectrum: number[]
  onsets: { kick: number; snare: number; hihat: number }
  updatedAt: string
}
export interface HomeAssistantEntity { id: string; state: string; since: string }
export interface HomeAssistantInput {
  state: InputState
  url: string
  since: string
  /** Seconds between retries while disconnected. */
  retryS: number | null
  entities: HomeAssistantEntity[]
}
export interface SunInput { elevation: number; azimuth: number; sunrise: string; sunset: string }
export interface Inputs {
  tempo: TempoInput
  prodjlink: ProDjLinkInput
  music: MusicInput
  homeAssistant: HomeAssistantInput
  sun: SunInput
}
export type SignalValue = number | string | boolean
export interface Signal { name: string; value: SignalValue; unit?: string; usedBy: Id[] }

/** The pending types' names, as the backend's schema would name them. */
export type PendingSchema =
  | 'Home' | 'Room' | 'SubZone' | 'Anchor' | 'Wall' | 'Furniture' | 'LightShape' | 'Placement'
  | 'PreviewRequest' | 'PreviewResponse' | 'Deck' | 'Inputs' | 'Signal'
/** The pending REST paths (§12.3), with FastAPI's parameter names. */
export type PendingPath =
  | '/api/home'
  | '/api/home/anchors'
  | '/api/home/anchors/{anchor_id}'
  | '/api/home/subzones'
  | '/api/home/subzones/{subzone_id}'
  | '/api/lights/{light_id}/placement'
  | '/api/lights/{light_id}/placement/confirm'
  | '/api/lights/placement/guess'
  | '/api/preview'
  | '/api/preview/{preview_id}'
  | '/api/inputs'
  | '/api/signals'
```

- [ ] **Step 5: Write `ws-messages.ts`**

```ts
// The /ws protocol (spec §12.4): what the server sends and what the client asks for. The beat,
// decks and stats are snake_case on the wire, as today; the pushed snapshots use the contract's
// camelCase (decision 5).
import type {
  AttentionItem, Deck, FrameStream, Id, Inputs, LightUpdate, Overlay, RunningZone, SignalValue, TempoSource,
} from './contract'

/** Today's beat (engine M1): no source, bar or server time. */
export interface BeatV1 {
  channel: 'beat'
  bpm: number
  beat_phase: number
  bar_phase: number
  is_playing: boolean
  /** Beat in the bar, 1–4. */
  beat_pos: number
  pitch_percent: number
  deck_number: number | null
  deck_name: string | null
}
/** §12.4's beat (engine M3). `server_time` is seconds since the epoch (decision 2). */
export interface BeatV2 {
  channel: 'beat'
  bpm: number
  beat_phase: number
  bar_phase: number
  bar: number
  /** Beat in the bar, 1–4. */
  beat_in_bar: number
  pitch_percent: number
  source: TempoSource
  stale: boolean
  server_time: number
}
export type BeatMessage = BeatV1 | BeatV2
export interface DecksMessage { channel: 'decks'; decks: Deck[] }
export interface RunningMessage { channel: 'running'; zones: RunningZone[]; overlays?: Overlay[] }
export interface LightsMessage { channel: 'lights'; lights: LightUpdate[] }
export interface AttentionMessage { channel: 'attention'; items: AttentionItem[] }
/** Preview only is `simulating` (§12.1). */
export interface TransportMessage { channel: 'transport'; state: 'stopped' | 'playing' | 'simulating' }
export interface DeviceStat {
  id: Id
  name: string
  send_fps: number
  latency_ms: number
  frames_dropped: number
  dropped_pct: number
  connected: boolean
  status: string
}
export interface StatsMessage { channel: 'stats'; devices: DeviceStat[] }
export interface StatusMessage { channel: 'status'; ok: boolean; device_count: number; avg_render_ms: number; transport: string }
/** A command's answer. `protocol: 2` switches the session's frames to v2 (decision 1). */
export interface AckMessage { channel: 'ack'; id: number | null; action: string; protocol?: number; fps?: number }
export interface ErrorMessage { channel: 'error'; id?: number | null; detail: string }
export interface InputsMessage { channel: 'inputs'; inputs: Inputs }
export interface SignalsMessage { channel: 'signals'; values: Record<string, SignalValue> }
/** "Effects in space" (§12.4, F10). Typed so it's recognised; nothing reads it before F10. */
export interface FxMessage { channel: 'fx' }
export type ServerMessage =
  | BeatMessage | DecksMessage | RunningMessage | LightsMessage | AttentionMessage | TransportMessage
  | StatsMessage | StatusMessage | AckMessage | ErrorMessage | InputsMessage | SignalsMessage | FxMessage

export type ClientCommand =
  | { action: 'subscribe_beat'; id: number; fps: number }
  | { action: 'subscribe_frames'; id: number; fps: number; protocol: 2; streams: FrameStream[]; lights?: Id[] }
  | { action: 'subscribe_signals'; id: number; names?: string[] }
  | { action: 'subscribe_fx'; id: number; on: boolean }
  | { action: 'tap'; id: number; client_time: number }
type WithoutId<T> = T extends unknown ? Omit<T, 'id'> : never
/** A command before the client numbers it. */
export type Command = WithoutId<ClientCommand>

// Snapshots whose list the stores rely on: without it, the message is dropped, not stored.
const LISTS: Partial<Record<string, string>> = {
  running: 'zones',
  lights: 'lights',
  attention: 'items',
  stats: 'devices',
  decks: 'decks',
}

/** A server message, or null for text that isn't one (bad JSON, no channel, a snapshot missing its list). */
export function parseMessage(text: string): ServerMessage | null {
  let value: unknown
  try {
    value = JSON.parse(text)
  } catch {
    return null
  }
  if (typeof value !== 'object' || value === null || Array.isArray(value)) return null
  const record = value as Record<string, unknown>
  if (typeof record.channel !== 'string') return null
  const list = LISTS[record.channel]
  if (list !== undefined && !Array.isArray(record[list])) return null
  if (record.channel === 'beat' && typeof record.bpm !== 'number') return null
  return value as ServerMessage
}
```

- [ ] **Step 6: Run the tests**

```bash
(cd web && npx vitest run src/api && npx tsc -b && echo "tsc ok")
```

Expected: the parse tests pass (11), and `tsc ok`. If M2 has merged, `tsc -b` fails in `contract.test.ts` naming the pending types M2 now serves. Swap each for its generated alias (Task 15, Step 3), then run again.

- [ ] **Step 7: Gate and commit**

```bash
git add web/src/api/contract.ts web/src/api/contract.test.ts web/src/api/ws-messages.ts web/src/api/ws-messages.test.ts
git commit -m "feat(web): the contract's types, pending ones marked by milestone, and the socket's messages"
```

---

### Task 3: The REST client

Implements spec §12 ("a REST client … Components never call `fetch`") over §12.3's endpoints, with M1's served paths typed against the generated `paths`. Decision 13. No renders.

**Files:**
- Create: `web/src/api/rest.ts`
- Test: `web/src/api/rest.test.ts`
- Modify: `web/vite.config.ts` (`unstubGlobals: true` in `test`)

**Interfaces:**
- Consumes: the types and `ApiPath`/`PendingPath` from `contract.ts` (Task 2).
- Produces:
  - `class ApiError extends Error { status: number; detail: string; path: string }`. Status 0 means no answer at all.
  - `apiPath(template: ApiPath | PendingPath, params?: Record<string, string>): string`, which fills in and URL-encodes the parameters and throws if one is missing.
  - `api`, an object of async functions, each resolving to the parsed body, or `undefined` for a 204.
    - Engine M1: `looks()`, `look(id)`, `saveLook(look)`, `updateLook(id, look)`, `deleteLook(id)`, `setStarred(id, starred)`, `zones()`, `createGroup(body)`, `updateGroup(id, body)`, `deleteGroup(id)`, `running()`, `start(zoneId, body)`, `setBrightness(zoneId, value)`, `off(zoneId)`, `restart(zoneId)`, `stopAll()`, `lights()`, `attention()`, `setPreviewOnly(on)`.
    - Pending on engine M2: `home()`, `updateHome(body)`, `addAnchor(body)`, `updateAnchor(id, body)`, `deleteAnchor(id)`, `addSubZone(body)`, `updateSubZone(id, body)`, `deleteSubZone(id)`, `setPlacement(lightId, body)`, `confirmPlacement(lightId)`, `guessPlacements()`, `startPreview(body)`, `updatePreview(id, look)`, `stopPreview(id)`.
    - Pending on M3–M7: `inputs()`, `signals()`.

- [ ] **Step 1: Read the spec**

Re-read §12.3 and §12's opening paragraph. Note CLAUDE.md's "Preview-only (`engine.preview_only`, `PUT /api/config`) applies at once", which is why `setPreviewOnly` PUTs the config.

- [ ] **Step 2: Write the failing test**

In `web/vite.config.ts`, add `unstubGlobals: true` beside `restoreMocks: true`, so a stubbed `fetch` ends with its test:

```ts
    // A spy (a muted console.error, say) ends with the test that made it, and so does a stubbed global.
    restoreMocks: true,
    unstubGlobals: true,
```

`web/src/api/rest.test.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api, apiPath } from './rest'

const fetchMock = vi.fn<typeof fetch>()

function answer(status: number, body?: unknown) {
  fetchMock.mockResolvedValueOnce(
    new Response(body === undefined ? null : JSON.stringify(body), {
      status,
      headers: { 'Content-Type': 'application/json' },
    }),
  )
}

beforeEach(() => {
  fetchMock.mockReset()
  // A new Response each time: a body can be read only once.
  fetchMock.mockImplementation(async () => new Response('{}', { status: 200 }))
  vi.stubGlobal('fetch', fetchMock)
})

function sent() {
  const [url, init] = fetchMock.mock.calls[0] as [URL, RequestInit]
  return { url, method: init.method, body: init.body === undefined ? undefined : JSON.parse(String(init.body)) }
}

const CALLS: { name: string; run: () => Promise<unknown>; method: string; path: string; body?: unknown }[] = [
  { name: 'looks', run: () => api.looks(), method: 'GET', path: '/api/looks' },
  { name: 'look', run: () => api.look('fireflies'), method: 'GET', path: '/api/looks/fireflies' },
  { name: 'setStarred', run: () => api.setStarred('fireflies', true), method: 'PUT', path: '/api/looks/fireflies/starred', body: { starred: true } },
  { name: 'zones', run: () => api.zones(), method: 'GET', path: '/api/zones' },
  { name: 'running', run: () => api.running(), method: 'GET', path: '/api/running' },
  { name: 'start', run: () => api.start('living', { lookId: 'embers' }), method: 'POST', path: '/api/zones/living/start', body: { lookId: 'embers' } },
  { name: 'setBrightness', run: () => api.setBrightness('living', 0.7), method: 'PUT', path: '/api/zones/living/brightness', body: { value: 0.7 } },
  { name: 'off', run: () => api.off('living'), method: 'POST', path: '/api/zones/living/off' },
  { name: 'restart', run: () => api.restart('kitchen'), method: 'POST', path: '/api/zones/kitchen/restart' },
  { name: 'stopAll', run: () => api.stopAll(), method: 'POST', path: '/api/running/stop-all' },
  { name: 'lights', run: () => api.lights(), method: 'GET', path: '/api/lights' },
  { name: 'attention', run: () => api.attention(), method: 'GET', path: '/api/attention' },
  { name: 'setPreviewOnly', run: () => api.setPreviewOnly(true), method: 'PUT', path: '/api/config', body: { engine: { preview_only: true } } },
  { name: 'home', run: () => api.home(), method: 'GET', path: '/api/home' },
  { name: 'addAnchor', run: () => api.addAnchor({ name: 'Lamp', position: [1, 2, 0.5] }), method: 'POST', path: '/api/home/anchors', body: { name: 'Lamp', position: [1, 2, 0.5] } },
  { name: 'deleteSubZone', run: () => api.deleteSubZone('office'), method: 'DELETE', path: '/api/home/subzones/office' },
  {
    name: 'setPlacement',
    run: () => api.setPlacement('rope', { shape: { kind: 'point', position: [1, 2, 0] } }),
    method: 'PUT',
    path: '/api/lights/rope/placement',
    body: { shape: { kind: 'point', position: [1, 2, 0] } },
  },
  { name: 'confirmPlacement', run: () => api.confirmPlacement('rope'), method: 'POST', path: '/api/lights/rope/placement/confirm' },
  { name: 'guessPlacements', run: () => api.guessPlacements(), method: 'POST', path: '/api/lights/placement/guess' },
  { name: 'startPreview', run: () => api.startPreview({ zoneId: 'living', lookId: 'embers' }), method: 'POST', path: '/api/preview', body: { zoneId: 'living', lookId: 'embers' } },
  { name: 'stopPreview', run: () => api.stopPreview('preview-1'), method: 'DELETE', path: '/api/preview/preview-1' },
  { name: 'inputs', run: () => api.inputs(), method: 'GET', path: '/api/inputs' },
  { name: 'signals', run: () => api.signals(), method: 'GET', path: '/api/signals' },
]

describe('api', () => {
  it.each(CALLS)('$name calls $method $path', async ({ run, method, path, body }) => {
    await run()
    expect(sent()).toMatchObject({ method, body })
    expect(sent().url.pathname).toBe(path)
  })

  it("sends absolute URLs on the page's own origin", async () => {
    await api.looks()
    expect(sent().url.origin).toBe(window.location.origin)
  })

  it('encodes path parameters', async () => {
    await api.look('a b/c')
    expect(sent().url.pathname).toBe('/api/looks/a%20b%2Fc')
  })

  it('returns the parsed body, and undefined for a 204', async () => {
    answer(200, [{ id: 'fireflies' }])
    expect(await api.looks()).toEqual([{ id: 'fireflies' }])
    answer(204)
    expect(await api.off('living')).toBeUndefined()
  })

  it("turns FastAPI's detail into an ApiError", async () => {
    answer(409, { detail: "Built-in looks can't be changed" })
    await expect(api.updateLook('fireflies', {} as never)).rejects.toMatchObject({
      name: 'ApiError',
      status: 409,
      detail: "Built-in looks can't be changed",
      path: '/api/looks/fireflies',
    })
  })

  it("joins a 422's problems into one detail", async () => {
    answer(422, { detail: [{ msg: 'Field required' }, { msg: 'Input should be a valid number' }] })
    await expect(api.setBrightness('living', Number.NaN)).rejects.toMatchObject({
      status: 422,
      detail: 'Field required; Input should be a valid number',
    })
  })

  it('falls back to the status text when the error body is not JSON', async () => {
    fetchMock.mockResolvedValueOnce(new Response('<html>', { status: 502, statusText: 'Bad Gateway' }))
    await expect(api.running()).rejects.toMatchObject({ status: 502, detail: 'Bad Gateway' })
  })

  it('reports no answer as status 0', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('fetch failed'))
    const error = await api.running().catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 0, detail: 'fetch failed' })
  })
})

describe('apiPath', () => {
  it('fills in every parameter', () => {
    expect(apiPath('/api/zones/{zone_id}/start', { zone_id: 'living' })).toBe('/api/zones/living/start')
  })

  it('throws when a parameter is missing', () => {
    expect(() => apiPath('/api/zones/{zone_id}/start')).toThrow('/api/zones/{zone_id}/start needs {zone_id}')
  })
})
```

- [ ] **Step 3: Run it to see it fail**

Run: `(cd web && npx vitest run src/api/rest.test.ts)`
Expected: FAIL, with `Failed to load url ./rest`.

- [ ] **Step 4: Write `rest.ts`**

```ts
// The REST client (spec §12.3). Every request the app makes goes through here; components never
// call fetch (§12). Paths are checked against the backend's schema (ApiPath) or §12.3 (PendingPath).
import type {
  Anchor, AnchorInput, ApiPath, AttentionItem, CreateGroup, Home, HomeUpdate, Id, Inputs, Light, Look,
  PendingPath, Placement, PlacementState, PreviewRequest, PreviewResponse, Running, RunningZone, Signal, StartRequest,
  StartResponse, SubZone, SubZoneInput, UpdateGroup, Zone,
} from './contract'

/** A request that failed. `status` 0 means no answer at all: the server is down, or the network. */
export class ApiError extends Error {
  readonly status: number
  readonly detail: string
  readonly path: string

  constructor(status: number, detail: string, path: string) {
    super(`${path}: ${status === 0 ? 'no answer' : status} ${detail}`)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    this.path = path
  }
}

/** A path template with its parameters filled in and encoded. */
export function apiPath(template: ApiPath | PendingPath, params: Record<string, string> = {}): string {
  return template.replace(/\{(\w+)\}/g, (_, name: string) => {
    const value = params[name]
    if (value === undefined) throw new Error(`${template} needs {${name}}`)
    return encodeURIComponent(value)
  })
}

type Method = 'GET' | 'POST' | 'PUT' | 'DELETE'

// Absolute: Node's fetch (Vitest, MSW's Node server) rejects a relative URL (decision 13).
function url(path: string): URL {
  return new URL(path, globalThis.location?.origin ?? 'http://localhost')
}

async function request<T>(method: Method, path: string, body?: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(url(path), {
      method,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch (error) {
    throw new ApiError(0, error instanceof Error ? error.message : String(error), path)
  }
  if (!response.ok) throw new ApiError(response.status, await errorDetail(response), path)
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

/** FastAPI's `detail`: a sentence, or a 422's list of problems. */
async function errorDetail(response: Response): Promise<string> {
  try {
    const { detail } = (await response.json()) as { detail?: unknown }
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail
        .map((problem) => (problem as { msg?: unknown }).msg)
        .filter((msg): msg is string => typeof msg === 'string')
        .join('; ')
    }
  } catch {
    // Not JSON: a proxy's error page, say.
  }
  return response.statusText || `HTTP ${response.status}`
}

const zone = (id: Id) => ({ zone_id: id })
const look = (id: Id) => ({ look_id: id })
const light = (id: Id) => ({ light_id: id })

export const api = {
  // Engine M1
  looks: () => request<Look[]>('GET', apiPath('/api/looks')),
  look: (id: Id) => request<Look>('GET', apiPath('/api/looks/{look_id}', look(id))),
  saveLook: (body: Look) => request<Look>('POST', apiPath('/api/looks'), body),
  updateLook: (id: Id, body: Look) => request<Look>('PUT', apiPath('/api/looks/{look_id}', look(id)), body),
  deleteLook: (id: Id) => request<void>('DELETE', apiPath('/api/looks/{look_id}', look(id))),
  setStarred: (id: Id, starred: boolean) =>
    request<Look>('PUT', apiPath('/api/looks/{look_id}/starred', look(id)), { starred }),
  zones: () => request<Zone[]>('GET', apiPath('/api/zones')),
  createGroup: (body: CreateGroup) => request<Zone>('POST', apiPath('/api/zones/groups'), body),
  updateGroup: (id: Id, body: UpdateGroup) =>
    request<Zone>('PUT', apiPath('/api/zones/groups/{zone_id}', zone(id)), body),
  deleteGroup: (id: Id) => request<void>('DELETE', apiPath('/api/zones/groups/{zone_id}', zone(id))),
  running: () => request<Running>('GET', apiPath('/api/running')),
  start: (zoneId: Id, body: StartRequest) =>
    request<StartResponse>('POST', apiPath('/api/zones/{zone_id}/start', zone(zoneId)), body),
  setBrightness: (zoneId: Id, value: number) =>
    request<RunningZone>('PUT', apiPath('/api/zones/{zone_id}/brightness', zone(zoneId)), { value }),
  off: (zoneId: Id) => request<void>('POST', apiPath('/api/zones/{zone_id}/off', zone(zoneId))),
  restart: (zoneId: Id) => request<RunningZone>('POST', apiPath('/api/zones/{zone_id}/restart', zone(zoneId))),
  stopAll: () => request<void>('POST', apiPath('/api/running/stop-all')),
  lights: () => request<Light[]>('GET', apiPath('/api/lights')),
  attention: () => request<AttentionItem[]>('GET', apiPath('/api/attention')),
  /** Preview only (§5.6) is the engine's `preview_only` setting today. */
  setPreviewOnly: (on: boolean) => request<unknown>('PUT', apiPath('/api/config'), { engine: { preview_only: on } }),

  // Pending: engine M2 (mocked until it lands)
  home: () => request<Home>('GET', apiPath('/api/home')),
  updateHome: (body: HomeUpdate) => request<Home>('PUT', apiPath('/api/home'), body),
  addAnchor: (body: AnchorInput) => request<Anchor>('POST', apiPath('/api/home/anchors'), body),
  updateAnchor: (id: Id, body: Partial<AnchorInput>) =>
    request<Anchor>('PUT', apiPath('/api/home/anchors/{anchor_id}', { anchor_id: id }), body),
  deleteAnchor: (id: Id) => request<void>('DELETE', apiPath('/api/home/anchors/{anchor_id}', { anchor_id: id })),
  addSubZone: (body: SubZoneInput) => request<SubZone>('POST', apiPath('/api/home/subzones'), body),
  updateSubZone: (id: Id, body: Partial<SubZoneInput>) =>
    request<SubZone>('PUT', apiPath('/api/home/subzones/{subzone_id}', { subzone_id: id }), body),
  deleteSubZone: (id: Id) => request<void>('DELETE', apiPath('/api/home/subzones/{subzone_id}', { subzone_id: id })),
  setPlacement: (lightId: Id, body: Placement) =>
    request<PlacementState>('PUT', apiPath('/api/lights/{light_id}/placement', light(lightId)), body),
  confirmPlacement: (lightId: Id) =>
    request<PlacementState>('POST', apiPath('/api/lights/{light_id}/placement/confirm', light(lightId))),
  guessPlacements: () => request<Light[]>('POST', apiPath('/api/lights/placement/guess')),
  startPreview: (body: PreviewRequest) => request<PreviewResponse>('POST', apiPath('/api/preview'), body),
  updatePreview: (id: Id, draft: Look) =>
    request<void>('PUT', apiPath('/api/preview/{preview_id}', { preview_id: id }), { look: draft }),
  stopPreview: (id: Id) => request<void>('DELETE', apiPath('/api/preview/{preview_id}', { preview_id: id })),

  // Pending: engine M3, M6 and M7 (mocked until they land)
  inputs: () => request<Inputs>('GET', apiPath('/api/inputs')),
  signals: () => request<Signal[]>('GET', apiPath('/api/signals')),
}
```

- [ ] **Step 5: Run the test**

Run: `(cd web && npx vitest run src/api/rest.test.ts)`
Expected: PASS (32 tests).

- [ ] **Step 6: Gate and commit**

```bash
git add web/src/api/rest.ts web/src/api/rest.test.ts web/vite.config.ts
git commit -m "feat(web): the REST client, typed against the backend's paths and §12.3's pending ones"
```

---

### Task 4: The frame decoder

Implements spec §12.4's binary frames, v1 and v2, and §14 Unit ("frame decoder v1/v2"). Review focus 5. No renders.

**Files:**
- Create: `web/src/api/frames.ts`
- Test: `web/src/api/frames.test.ts`

**Interfaces:**
- Consumes: `Id` and `FrameStream` from `contract.ts`.
- Produces:
  - `type FrameVersion = 1 | 2` and `STREAM_BYTE: Record<FrameStream, number>`.
  - `interface LightFrame { rgb: Uint8Array; seq: number; count: number; at: number; recent: number }`.
  - `class IdTable { lookup(bytes, start, length): Id | null }`.
  - `class FrameStore`, with:
    - fields: `live: Map<Id, LightFrame>`, `preview: Map<Id, LightFrame>`, `ids: IdTable`, `version: number`, `lastFrameAt: number | null` (wall-clock ms), `malformed: number`;
    - methods: `get(id, stream?)`, `reject(): false`, `sampleFps(): number`, `resetSeqs()`, `clearPreview()`.
  - `decodeFrame(data: ArrayBuffer, version: FrameVersion, frames: FrameStore, now: number): boolean`. `now` is the client clock's seconds. It returns false for a malformed message, which it also counts.
  - `encodeFrame(version: FrameVersion, id: Id, seq: number, rgb: Uint8Array, stream?: FrameStream): ArrayBuffer`, used by the mock and the tests.

- [ ] **Step 1: Read the spec**

Re-read §12.4's binary frame lines and §12.1's "Live LED frames" row. Also read `_frame_poll` in `src/dj_ledfx/web/ws.py`. It sends every routed light at each poll whether or not its seq moved, and keys frames by the stable id, whatever its comment calls the key.

- [ ] **Step 2: Write the failing test**

`web/src/api/frames.test.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { FrameStore, decodeFrame, encodeFrame } from './frames'

const rgb = (...values: number[]) => new Uint8Array(values)
const bytes = (...values: number[]) => new Uint8Array(values).buffer

let frames: FrameStore
beforeEach(() => {
  frames = new FrameStore()
})

describe('decodeFrame', () => {
  it("stores a v1 frame under its light's id, as live", () => {
    expect(decodeFrame(encodeFrame(1, 'rope', 7, rgb(1, 2, 3, 4, 5, 6)), 1, frames, 10)).toBe(true)
    expect(frames.get('rope')).toEqual({ rgb: rgb(1, 2, 3, 4, 5, 6), seq: 7, count: 2, at: 10, recent: 1 })
    expect(frames.version).toBe(1)
  })

  it("keeps v2's live and preview streams apart", () => {
    decodeFrame(encodeFrame(2, 'tube', 1, rgb(9, 9, 9), 'live'), 2, frames, 0)
    decodeFrame(encodeFrame(2, 'tube', 1, rgb(1, 1, 1), 'preview'), 2, frames, 0)
    expect(frames.get('tube')?.rgb).toEqual(rgb(9, 9, 9))
    expect(frames.get('tube', 'preview')?.rgb).toEqual(rgb(1, 1, 1))
  })

  it('reads an id that is not ASCII', () => {
    decodeFrame(encodeFrame(2, 'lampe-été', 1, rgb(0, 0, 0)), 2, frames, 0)
    expect(frames.live.has('lampe-été')).toBe(true)
  })

  it('skips a frame it already has, and takes the next seq', () => {
    decodeFrame(encodeFrame(1, 'rope', 5, rgb(1, 1, 1)), 1, frames, 0)
    decodeFrame(encodeFrame(1, 'rope', 5, rgb(2, 2, 2)), 1, frames, 1)
    expect(frames.get('rope')?.rgb).toEqual(rgb(1, 1, 1))
    expect(frames.version).toBe(1)
    decodeFrame(encodeFrame(1, 'rope', 6, rgb(2, 2, 2)), 1, frames, 1)
    expect(frames.get('rope')?.rgb).toEqual(rgb(2, 2, 2))
  })

  it('takes seq 1 again once a reconnect has reset the seqs', () => {
    decodeFrame(encodeFrame(2, 'rope', 500, rgb(1, 1, 1)), 2, frames, 0)
    frames.resetSeqs()
    decodeFrame(encodeFrame(2, 'rope', 1, rgb(2, 2, 2)), 2, frames, 1)
    expect(frames.get('rope')).toMatchObject({ seq: 1, rgb: rgb(2, 2, 2) })
  })

  it('writes into the same buffer while the LED count stays the same', () => {
    decodeFrame(encodeFrame(2, 'rope', 1, rgb(1, 1, 1, 2, 2, 2)), 2, frames, 0)
    const buffer = frames.get('rope')?.rgb
    decodeFrame(encodeFrame(2, 'rope', 2, rgb(3, 3, 3, 4, 4, 4)), 2, frames, 0)
    expect(frames.get('rope')?.rgb).toBe(buffer)
    expect(buffer).toEqual(rgb(3, 3, 3, 4, 4, 4))
  })

  // Review focus 5: a part added to the PC, or a light rediscovered with more LEDs.
  it('reallocates when the LED count changes, and takes a light with no LEDs', () => {
    decodeFrame(encodeFrame(2, 'pc', 1, rgb(1, 1, 1)), 2, frames, 0)
    decodeFrame(encodeFrame(2, 'pc', 2, rgb(1, 1, 1, 2, 2, 2)), 2, frames, 0)
    expect(frames.get('pc')).toMatchObject({ count: 2, rgb: rgb(1, 1, 1, 2, 2, 2) })
    expect(decodeFrame(encodeFrame(2, 'pc', 3, rgb()), 2, frames, 0)).toBe(true)
    expect(frames.get('pc')).toMatchObject({ count: 0, rgb: rgb() })
  })

  it('decodes each id once, however many frames carry it', () => {
    const decode = vi.spyOn(TextDecoder.prototype, 'decode')
    for (let seq = 1; seq <= 100; seq++) decodeFrame(encodeFrame(2, 'rope', seq, rgb(seq, 0, 0)), 2, frames, 0)
    expect(decode).toHaveBeenCalledTimes(1)
  })

  const good = [...new Uint8Array(encodeFrame(2, 'rope', 1, rgb(1, 2, 3)))]
  // Review focus 5: each is dropped and counted, and nothing else changes.
  it.each([
    ['an empty message', bytes()],
    ['an unknown stream byte', bytes(0x07, ...good.slice(1))],
    ['a message too short for its id length', bytes(0x01, 1)],
    ['an id length past the end', bytes(0x01, 200, 0, 0x72, 0x6f)],
    ['a zero-length id', bytes(0x01, 0, 0, 1, 0, 0, 0, 1, 2, 3)],
    ['a missing seq', bytes(0x01, 4, 0, 0x72, 0x6f, 0x70, 0x65, 1, 0)],
    ['an RGB tail that is not whole LEDs', bytes(...good, 9)],
    ['an id that is not UTF-8', bytes(0x01, 2, 0, 0xff, 0xfe, 1, 0, 0, 0, 1, 2, 3)],
  ])('drops and counts %s, and leaves the other lights alone', (_, message) => {
    decodeFrame(encodeFrame(2, 'tube', 1, rgb(7, 7, 7)), 2, frames, 0)
    const version = frames.version
    expect(decodeFrame(message, 2, frames, 1)).toBe(false)
    expect(frames.malformed).toBe(1)
    expect(frames.version).toBe(version)
    expect(frames.get('tube')?.rgb).toEqual(rgb(7, 7, 7))
    expect([...frames.live.keys()]).toEqual(['tube'])
  })

  it('drops a truncated v1 message too', () => {
    expect(decodeFrame(bytes(4, 0, 0x72), 1, frames, 0)).toBe(false)
    expect(frames.malformed).toBe(1)
  })
})

describe('FrameStore', () => {
  it('samples the most live frames any one light received, then starts again', () => {
    for (let seq = 1; seq <= 60; seq++) decodeFrame(encodeFrame(2, 'rope', seq, rgb(0, 0, 0)), 2, frames, 0)
    for (let seq = 1; seq <= 30; seq++) decodeFrame(encodeFrame(2, 'tube', seq, rgb(0, 0, 0)), 2, frames, 0)
    for (let seq = 1; seq <= 90; seq++) decodeFrame(encodeFrame(2, 'tube', seq, rgb(0, 0, 0), 'preview'), 2, frames, 0)
    expect(frames.sampleFps()).toBe(60)
    expect(frames.sampleFps()).toBe(0)
  })

  it("drops the preview's frames when the preview ends, and says so", () => {
    decodeFrame(encodeFrame(2, 'tube', 1, rgb(1, 1, 1), 'preview'), 2, frames, 0)
    frames.clearPreview()
    expect(frames.preview.size).toBe(0)
    expect(frames.version).toBe(2)
  })

  it('remembers when the last frame arrived, on the wall clock', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 8, 23, 19, 14, 32))
    decodeFrame(encodeFrame(2, 'rope', 1, rgb(0, 0, 0)), 2, frames, 0)
    expect(frames.lastFrameAt).toBe(new Date(2026, 8, 23, 19, 14, 32).getTime())
  })
})

describe('encodeFrame', () => {
  it('lays v1 and v2 out as §12.4 says', () => {
    expect([...new Uint8Array(encodeFrame(1, 'ab', 258, rgb(1, 2, 3)))]).toEqual([2, 0, 97, 98, 2, 1, 0, 0, 1, 2, 3])
    expect([...new Uint8Array(encodeFrame(2, 'ab', 258, rgb(1, 2, 3), 'preview'))]).toEqual([
      2, 2, 0, 97, 98, 2, 1, 0, 0, 1, 2, 3,
    ])
  })
})
```

- [ ] **Step 3: Run it to see it fail**

Run: `(cd web && npx vitest run src/api/frames.test.ts)`
Expected: FAIL, with `Failed to load url ./frames`.

- [ ] **Step 4: Write `frames.ts`**

```ts
// Binary LED frames (spec §12.4), decoded into buffers the stage reads in place.
//   v1 (engine M1): [2B id_len LE][id UTF-8][4B seq LE][RGB × leds]
//   v2 (engine M2): [1B stream: 0x01 live | 0x02 preview][2B id_len LE][id UTF-8][4B seq LE][RGB × leds]
// Once a light has its buffer, decoding a frame allocates nothing, and React never subscribes to
// any of this: 60 fps of frames must cost no renders (§13.1). The stage (F2) reads `live` and
// `preview` on each animation frame, and redraws when `version` has moved.
import type { FrameStream, Id } from './contract'

export type FrameVersion = 1 | 2

export const STREAM_BYTE: Record<FrameStream, number> = { live: 0x01, preview: 0x02 }

export interface LightFrame {
  /** RGB bytes, three per LED: the same array while the LED count stays the same. */
  rgb: Uint8Array
  /** The server's sequence number for this light and stream; -1 once a reconnect resets it. */
  seq: number
  /** LEDs in the frame. */
  count: number
  /** When it arrived, in the client clock's seconds. */
  at: number
  /** Frames since the last fps sample. */
  recent: number
}

// A server that sends ids nobody has seen before, frame after frame, can't grow the table forever.
const MAX_IDS = 1024

/** Light ids by their UTF-8 bytes: after the first frame, an id is compared, never decoded. */
export class IdTable {
  private readonly byLength = new Map<number, { bytes: Uint8Array; id: Id }[]>()
  private readonly decoder = new TextDecoder('utf-8', { fatal: true })
  private size = 0

  /** The id in bytes[start, start + length), or null if those bytes aren't UTF-8. */
  lookup(bytes: Uint8Array, start: number, length: number): Id | null {
    const known = this.byLength.get(length)
    if (known !== undefined) {
      for (const entry of known) if (sameBytes(entry.bytes, bytes, start)) return entry.id
    }
    const copy = bytes.slice(start, start + length)
    let id: Id
    try {
      id = this.decoder.decode(copy)
    } catch {
      return null
    }
    if (this.size >= MAX_IDS) {
      this.byLength.clear()
      this.size = 0
    }
    const entries = this.byLength.get(length) ?? []
    entries.push({ bytes: copy, id })
    this.byLength.set(length, entries)
    this.size += 1
    return id
  }
}

function sameBytes(known: Uint8Array, bytes: Uint8Array, start: number): boolean {
  for (let i = 0; i < known.length; i++) if (known[i] !== bytes[start + i]) return false
  return true
}

/** Every light's latest frame, per stream. */
export class FrameStore {
  readonly live = new Map<Id, LightFrame>()
  readonly preview = new Map<Id, LightFrame>()
  readonly ids = new IdTable()
  /** Moves with every frame stored: redraw when it has moved. */
  version = 0
  /** Wall-clock ms of the last frame, for §9.4's "This is the last frame, from 19:14:32". */
  lastFrameAt: number | null = null
  /** Binary messages dropped as malformed. */
  malformed = 0

  get(id: Id, stream: FrameStream = 'live'): LightFrame | undefined {
    return (stream === 'live' ? this.live : this.preview).get(id)
  }

  /** Counts a malformed message; decodeFrame returns what this returns. */
  reject(): false {
    this.malformed += 1
    return false
  }

  /** The most live frames any one light received since the last call. */
  sampleFps(): number {
    let most = 0
    for (const frame of this.live.values()) {
      if (frame.recent > most) most = frame.recent
      frame.recent = 0
    }
    return most
  }

  /** After a reconnect a restarted server counts from 1 again, so any seq is new once. */
  resetSeqs(): void {
    for (const frame of this.live.values()) frame.seq = -1
    for (const frame of this.preview.values()) frame.seq = -1
  }

  /** The preview ended (F4): its frames go. */
  clearPreview(): void {
    this.preview.clear()
    this.version += 1
  }
}

/** Decodes one binary message into `frames`. False, and counted, when it's malformed. */
export function decodeFrame(data: ArrayBuffer, version: FrameVersion, frames: FrameStore, now: number): boolean {
  const bytes = new Uint8Array(data)
  let offset = 0
  let target = frames.live
  if (version === 2) {
    const stream = bytes.length > 0 ? bytes[0] : -1
    if (stream === STREAM_BYTE.live) target = frames.live
    else if (stream === STREAM_BYTE.preview) target = frames.preview
    else return frames.reject()
    offset = 1
  }
  if (bytes.length < offset + 2) return frames.reject()
  const idLength = bytes[offset] | (bytes[offset + 1] << 8)
  offset += 2
  if (idLength === 0 || bytes.length < offset + idLength + 4) return frames.reject()
  const id = frames.ids.lookup(bytes, offset, idLength)
  if (id === null) return frames.reject()
  offset += idLength
  const seq = (bytes[offset] | (bytes[offset + 1] << 8) | (bytes[offset + 2] << 16) | (bytes[offset + 3] << 24)) >>> 0
  offset += 4
  const length = bytes.length - offset
  if (length % 3 !== 0) return frames.reject()

  let frame = target.get(id)
  // v1 sends every light at each poll, whether or not it has a new frame.
  if (frame !== undefined && frame.seq === seq) return true
  if (frame === undefined || frame.rgb.length !== length) {
    frame = { rgb: new Uint8Array(length), seq, count: length / 3, at: now, recent: 0 }
    target.set(id, frame)
  }
  const rgb = frame.rgb
  for (let i = 0; i < length; i++) rgb[i] = bytes[offset + i]
  frame.seq = seq
  frame.count = length / 3
  frame.at = now
  frame.recent += 1
  frames.version += 1
  frames.lastFrameAt = Date.now()
  return true
}

/** One frame as the server sends it: for the mock server and the tests. */
export function encodeFrame(
  version: FrameVersion,
  id: Id,
  seq: number,
  rgb: Uint8Array,
  stream: FrameStream = 'live',
): ArrayBuffer {
  const idBytes = new TextEncoder().encode(id)
  const head = version === 2 ? 1 : 0
  const out = new Uint8Array(head + 2 + idBytes.length + 4 + rgb.length)
  const view = new DataView(out.buffer)
  if (version === 2) out[0] = STREAM_BYTE[stream]
  view.setUint16(head, idBytes.length, true)
  out.set(idBytes, head + 2)
  view.setUint32(head + 2 + idBytes.length, seq >>> 0, true)
  out.set(rgb, head + 6 + idBytes.length)
  return out.buffer
}
```

- [ ] **Step 5: Run the test**

Run: `(cd web && npx vitest run src/api/frames.test.ts)`
Expected: PASS (21 tests).

- [ ] **Step 6: Gate and commit**

```bash
git add web/src/api/frames.ts web/src/api/frames.test.ts
git commit -m "feat(web): decode binary frames v1 and v2 into reused buffers"
```

---

### Task 5: The beat clock

Implements spec §12.4's beat extrapolation, §5.4 ("Beat-synced motion must follow the real beat clock") and §14 Unit ("beat extrapolation"). Decisions 2 and 9. Review focus 3 and 4. No renders.

**Files:**
- Create: `web/src/api/beat.ts`
- Test: `web/src/api/beat.test.ts`

**Interfaces:**
- Consumes: `TempoSource` from `contract.ts`, and `BeatMessage`, `BeatV1` and `BeatV2` from `ws-messages.ts`.
- Produces:
  - `clientNow(): number`, seconds since the epoch on the performance clock.
  - `interface Beat { bpm; beatPhase; barPhase; beatInBar; bar: number | null; pitchPercent; source: TempoSource; stale; playing; serverTime: number | null; receivedAt }`.
  - `normaliseBeat(message: BeatMessage, receivedAt: number): Beat`.
  - `class ClockOffset { add(serverTime, receivedAt); readonly value: number | null; reset() }`.
  - `SNAP_S = 0.005` and `SOFT_GAIN = 0.1`.
  - `interface BeatSample { beatPhase; barPhase; beatInBar; bar: number | null; bpm; running }`.
  - `class BeatClock { receive(beat: Beat, offset: number | null); sample(now: number): BeatSample; reset() }`.
  - Times are seconds on `clientNow()`'s clock. Tests pass their own.

- [ ] **Step 1: Read the spec**

Re-read §12.4's beat row and its "Beat extrapolation" paragraph, §5.4, §11.5, and decisions 2 and 9. Read `_beat_poll` in `src/dj_ledfx/web/ws.py` for today's v1 fields, and CLAUDE.md's "BeatClock drift correction: soft correct if <5ms, hard snap if >=5ms" and "Phase wraps from ~1.0 to ~0.0 at each beat".

- [ ] **Step 2: Write the failing test**

`web/src/api/beat.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { BeatClock, ClockOffset, clientNow, normaliseBeat, type Beat } from './beat'
import type { BeatV1, BeatV2 } from './ws-messages'

const V1: BeatV1 = {
  channel: 'beat',
  bpm: 124,
  beat_phase: 0.5,
  bar_phase: 0.375,
  is_playing: true,
  beat_pos: 2,
  pitch_percent: 1.2,
  deck_number: 2,
  deck_name: 'Player 2',
}
const V2: BeatV2 = {
  channel: 'beat',
  bpm: 121.8,
  beat_phase: 0.25,
  bar_phase: 0.3125,
  bar: 42,
  beat_in_bar: 2,
  pitch_percent: 0,
  source: 'music',
  stale: false,
  server_time: 1000,
}

/** A beat at 120 BPM (two beats a second), `beats` into bar `bar`, arriving at `at`. */
function beat(bar: number | null, beats: number, at: number, extra: Partial<Beat> = {}): Beat {
  return {
    bpm: 120,
    beatPhase: beats % 1,
    barPhase: beats / 4,
    beatInBar: Math.floor(beats) + 1,
    bar,
    pitchPercent: 0,
    source: 'internal',
    stale: false,
    playing: true,
    serverTime: null,
    receivedAt: at,
    ...extra,
  }
}

describe('normaliseBeat', () => {
  // Review focus 3: engine M1's beat.
  it("reads today's v1 beat as Pro DJ Link with no bar", () => {
    expect(normaliseBeat(V1, 5)).toEqual({
      bpm: 124,
      beatPhase: 0.5,
      barPhase: 0.375,
      beatInBar: 2,
      bar: null,
      pitchPercent: 1.2,
      source: 'prodjlink',
      stale: false,
      playing: true,
      serverTime: null,
      receivedAt: 5,
    })
  })

  it('reads a v1 beat with no DJ (bpm 0) as stopped', () => {
    expect(normaliseBeat({ ...V1, bpm: 0, is_playing: false }, 5).playing).toBe(false)
  })

  it("reads §12.4's beat", () => {
    expect(normaliseBeat(V2, 7)).toEqual({
      bpm: 121.8,
      beatPhase: 0.25,
      barPhase: 0.3125,
      beatInBar: 2,
      bar: 42,
      pitchPercent: 0,
      source: 'music',
      stale: false,
      playing: true,
      serverTime: 1000,
      receivedAt: 7,
    })
  })

  it('stops the beat while its source is stale', () => {
    expect(normaliseBeat({ ...V2, stale: true }, 7).playing).toBe(false)
  })
})

describe('ClockOffset', () => {
  it('takes the least-delayed of the last 64 messages', () => {
    const offset = new ClockOffset()
    expect(offset.value).toBeNull()
    offset.add(100, 100.04)
    offset.add(101, 101.01)
    offset.add(102, 102.03)
    expect(offset.value).toBeCloseTo(0.01)
    for (let i = 0; i < 64; i++) offset.add(200 + i, 200.02 + i)
    expect(offset.value).toBeCloseTo(0.02)
    offset.reset()
    expect(offset.value).toBeNull()
  })
})

describe('BeatClock', () => {
  it('runs on at the tempo between messages', () => {
    const clock = new BeatClock()
    clock.receive(beat(42, 1.5, 100), null)
    expect(clock.sample(100.25)).toEqual({ beatPhase: 0, barPhase: 0.5, beatInBar: 3, bar: 42, bpm: 120, running: true })
  })

  // Review focus 4.
  it('wraps the beat and the bar without a jump', () => {
    const clock = new BeatClock()
    clock.receive(beat(42, 3.96, 100), null)
    const before = clock.sample(100.01)
    const after = clock.sample(100.03)
    expect(before).toMatchObject({ beatInBar: 4, bar: 42 })
    expect(before.beatPhase).toBeCloseTo(0.98)
    expect(after).toMatchObject({ beatInBar: 1, bar: 43 })
    expect(after.beatPhase).toBeCloseTo(0.02)
    expect(after.barPhase).toBeCloseTo(0.005)
  })

  it('eases a small error in and snaps a large one', () => {
    const soft = new BeatClock()
    soft.receive(beat(1, 0, 100), null)
    // Half a second on, the clock expects beat 1.0. The server says 3 ms further (0.006 beats):
    // under 5 ms, so a tenth of it is taken.
    soft.receive(beat(1, 1.006, 100.5), null)
    expect(soft.sample(100.5).beatPhase).toBeCloseTo(0.0006, 6)

    const hard = new BeatClock()
    hard.receive(beat(1, 0, 100), null)
    // 20 ms off (0.04 beats): the clock lands on the server's beat.
    hard.receive(beat(1, 1.04, 100.5), null)
    expect(hard.sample(100.5).beatPhase).toBeCloseTo(0.04, 6)
  })

  // Review focus 4: engine M1's beat counts no bars, so an error is taken the near way round.
  it('corrects a v1 beat across the bar line forwards, not back', () => {
    const clock = new BeatClock()
    clock.receive(beat(null, 3.98, 100), null)
    // 30 ms on, the clock is at 4.04 beats: 0.04 into the next bar, where the server says it is.
    clock.receive(beat(null, 0.04, 100.03), null)
    const now = clock.sample(100.03)
    expect(now.beatInBar).toBe(1)
    expect(now.barPhase).toBeCloseTo(0.01)
    expect(now.bar).toBeNull()
  })

  // Review focus 4: the server's clock is 2 s ahead, and messages arrive 5–40 ms late.
  it('follows a server clock 2 s ahead through jittery delivery', () => {
    const clock = new BeatClock()
    const offset = new ClockOffset()
    const truth = (serverTime: number) => ((serverTime - 1000) * 120) / 60 // beats since bar 1 began
    const delays = [0.005, 0.04, 0.012, 0.031, 0.007, 0.022]
    let receivedAt = 0
    for (let i = 0; i < 60; i++) {
      const serverTime = 1000 + i / 30
      receivedAt = serverTime - 2 + delays[i % delays.length]
      const beats = truth(serverTime)
      offset.add(serverTime, receivedAt)
      clock.receive({ ...beat(Math.floor(beats / 4) + 1, beats % 4, receivedAt), serverTime }, offset.value)
    }
    const now = receivedAt + 0.01
    const sample = clock.sample(now)
    const position = ((sample.bar ?? 1) - 1) * 4 + sample.barPhase * 4
    // Within 10 ms of the true beat (0.02 beats at 120 BPM).
    expect(Math.abs(position - truth(now + 2))).toBeLessThan(0.02)
  })

  it('holds still while stale, stopped or at 0 BPM', () => {
    for (const extra of [{ stale: true, playing: false }, { playing: false }, { bpm: 0, playing: false }]) {
      const clock = new BeatClock()
      clock.receive(beat(42, 1.5, 100, extra), null)
      expect(clock.sample(101)).toEqual(clock.sample(100))
      expect(clock.sample(101)).toMatchObject({ running: false, beatInBar: 2, bar: 42 })
    }
  })

  it('forgets the beat on reset', () => {
    const clock = new BeatClock()
    clock.receive(beat(42, 1.5, 100), null)
    clock.reset()
    expect(clock.sample(100.5)).toEqual({ beatPhase: 0, barPhase: 0, beatInBar: 1, bar: null, bpm: 0, running: false })
  })
})

it('reads the client clock in seconds since the epoch', () => {
  expect(Math.abs(clientNow() - Date.now() / 1000)).toBeLessThan(1)
})
```

- [ ] **Step 3: Run it to see it fail**

Run: `(cd web && npx vitest run src/api/beat.test.ts)`
Expected: FAIL, with `Failed to load url ./beat`.

- [ ] **Step 4: Write `beat.ts`**

```ts
// The beat on the client (spec §12.4, §5.4). The server sends it at up to 30 Hz, and the UI
// samples it on every animation frame. Between messages the clock runs on at the tempo, and each
// message pulls it back: softly under 5 ms, with a snap at 5 ms or more, as the engine's BeatClock
// corrects its drift.
import type { TempoSource } from './contract'
import type { BeatMessage } from './ws-messages'

/**
 * Seconds since the epoch on the performance clock. It only moves forward, and Playwright's fixed
 * clock (which fixes Date) leaves it running, so beats and watchdogs keep time in e2e.
 */
export function clientNow(): number {
  return (performance.timeOrigin + performance.now()) / 1000
}

/** One beat message, whichever protocol sent it. */
export interface Beat {
  /** Pitch-adjusted. */
  bpm: number
  beatPhase: number
  barPhase: number
  /** 1–4. */
  beatInBar: number
  /** null: the source counts no bars (engine M1's beat). */
  bar: number | null
  pitchPercent: number
  source: TempoSource
  stale: boolean
  /** The beat moves: false while stale, stopped, or at 0 BPM. */
  playing: boolean
  /** Seconds since the epoch on the server's clock; null from engine M1. */
  serverTime: number | null
  /** clientNow() when it arrived. */
  receivedAt: number
}

export function normaliseBeat(message: BeatMessage, receivedAt: number): Beat {
  if ('source' in message) {
    return {
      bpm: message.bpm,
      beatPhase: message.beat_phase,
      barPhase: message.bar_phase,
      beatInBar: message.beat_in_bar,
      bar: message.bar,
      pitchPercent: message.pitch_percent,
      source: message.source,
      stale: message.stale,
      playing: !message.stale && message.bpm > 0,
      serverTime: message.server_time,
      receivedAt,
    }
  }
  // Engine M1: Pro DJ Link is its only source, and it counts no bars (decision 9).
  return {
    bpm: message.bpm,
    beatPhase: message.beat_phase,
    barPhase: message.bar_phase,
    beatInBar: message.beat_pos,
    bar: null,
    pitchPercent: message.pitch_percent,
    source: 'prodjlink',
    stale: false,
    playing: message.is_playing && message.bpm > 0,
    serverTime: null,
    receivedAt,
  }
}

const WINDOW = 64

/** How far the client's clock runs ahead of the server's, in seconds (decision 2). */
export class ClockOffset {
  private readonly gaps = new Float64Array(WINDOW)
  private count = 0
  private next = 0

  add(serverTime: number, receivedAt: number): void {
    this.gaps[this.next] = receivedAt - serverTime
    this.next = (this.next + 1) % WINDOW
    this.count = Math.min(this.count + 1, WINDOW)
  }

  /** The smallest gap in the window, the least-delayed message's; null before any. */
  get value(): number | null {
    if (this.count === 0) return null
    let smallest = Infinity
    for (let i = 0; i < this.count; i++) smallest = Math.min(smallest, this.gaps[i])
    return smallest
  }

  reset(): void {
    this.count = 0
    this.next = 0
  }
}

/** The engine's BeatClock threshold: under it a correction eases in, at or over it the clock snaps. */
export const SNAP_S = 0.005
/** How much of a small error each message corrects. */
export const SOFT_GAIN = 0.1

export interface BeatSample {
  beatPhase: number
  barPhase: number
  /** 1–4. */
  beatInBar: number
  bar: number | null
  bpm: number
  running: boolean
}

/** Beats within the bar, in [0, 4). */
const withinBar = (beats: number) => ((beats % 4) + 4) % 4
/** An error in beats, wrapped to (−2, 2]: the near way round the bar. */
const nearWay = (beats: number) => beats - 4 * Math.ceil((beats - 2) / 4)

/**
 * The beat between messages. A position is in beats: counted from the first bar's downbeat when
 * the source counts bars, else within the bar.
 */
export class BeatClock {
  private position = 0
  private at = 0
  private bpm = 0
  private running = false
  private counted = false

  receive(beat: Beat, offset: number | null): void {
    const counted = beat.bar !== null
    // When the message's beat was true, on this client's clock.
    const measuredAt = beat.serverTime !== null && offset !== null ? beat.serverTime + offset : beat.receivedAt
    let target = (beat.bar !== null ? (beat.bar - 1) * 4 : 0) + beat.barPhase * 4
    if (beat.playing) target += ((beat.receivedAt - measuredAt) * beat.bpm) / 60
    if (!beat.playing || !this.running || counted !== this.counted) {
      this.anchor(target, beat.receivedAt, beat.bpm, beat.playing, counted)
      return
    }
    const predicted = this.positionAt(beat.receivedAt)
    const error = counted ? target - predicted : nearWay(target - predicted)
    const errorS = (Math.abs(error) * 60) / beat.bpm
    const corrected = predicted + (errorS < SNAP_S ? error * SOFT_GAIN : error)
    this.anchor(corrected, beat.receivedAt, beat.bpm, true, counted)
  }

  sample(now: number): BeatSample {
    const position = this.positionAt(now)
    const beats = withinBar(position)
    return {
      beatPhase: beats % 1,
      barPhase: beats / 4,
      beatInBar: Math.floor(beats) + 1,
      bar: this.counted ? Math.floor(position / 4) + 1 : null,
      bpm: this.bpm,
      running: this.running,
    }
  }

  /** Forget the beat: after a reconnect, the next message anchors afresh. */
  reset(): void {
    this.anchor(0, 0, 0, false, false)
  }

  private positionAt(now: number): number {
    return this.running ? this.position + ((now - this.at) * this.bpm) / 60 : this.position
  }

  private anchor(position: number, at: number, bpm: number, running: boolean, counted: boolean): void {
    this.position = counted ? position : withinBar(position)
    this.at = at
    this.bpm = bpm
    this.running = running
    this.counted = counted
  }
}
```

- [ ] **Step 5: Run the test**

Run: `(cd web && npx vitest run src/api/beat.test.ts)`
Expected: PASS (13 tests).

- [ ] **Step 6: Gate and commit**

```bash
git add web/src/api/beat.ts web/src/api/beat.test.ts
git commit -m "feat(web): a beat clock that extrapolates between messages and corrects like the engine's"
```

---

### Task 6: The live store

Implements spec §3.3 (zustand stores) and §12.4's channels, and the owner's constraint 2 (nothing is claimed before it's heard). No renders.

**Files:**
- Modify: `web/package.json`, `web/package-lock.json` (zustand)
- Create: `web/src/api/live-store.ts`
- Test: `web/src/api/live-store.test.tsx`

**Interfaces:**
- Consumes: `normaliseBeat` and `Beat` (Task 5), the contract types (Task 2), and `ServerMessage` and `DeviceStat` (Task 2).
- Produces:
  - `type Connection = { status: 'connecting' } | { status: 'live'; fps: number | null } | { status: 'reconnecting'; attempt: number }`.
  - `interface LiveState { connection; beat: Beat | null; decks: Deck[] | null; running: { zones: RunningZone[]; overlays: Overlay[] } | null; lights: Record<Id, LightUpdate> | null; stats: Record<Id, DeviceStat> | null; attention: AttentionItem[] | null; previewOnly: boolean | null; inputs: Inputs | null; signals: Record<string, SignalValue> | null }`.
  - `EMPTY_LIVE`, `type LiveStore = StoreApi<LiveState>`, `createLiveStore()`, `liveStore` (the app's) and `resetLiveStore(store?)`.
  - `applyMessage(store: LiveStore, message: ServerMessage, receivedAt: number): void`.
  - `useLive<T>(selector)` and `useLiveShallow<T>(selector)`, hooks over `liveStore`.

- [ ] **Step 1: Read the spec and the library**

Re-read §12.4's channel table and §9.4's "Resync everything on reconnect". With context7, check zustand 5: `createStore` from `zustand/vanilla`, `useStore(store, selector)` from `zustand`, `useShallow` from `zustand/react/shallow`, and `setState(state, true)` to replace the state.

```bash
(cd web && npm install zustand@^5.0.15)
```

- [ ] **Step 2: Write the failing test**

`web/src/api/live-store.test.tsx`:

```tsx
import { act, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { AttentionItem, Deck, RunningZone } from './contract'
import {
  EMPTY_LIVE, applyMessage, createLiveStore, liveStore, resetLiveStore, useLive, type LiveState, type LiveStore,
} from './live-store'
import type { DeviceStat, ServerMessage } from './ws-messages'

const ZONE: RunningZone = {
  zoneId: 'zone-a',
  lookId: 'look-a',
  lookName: 'Look A',
  since: '2026-09-23T19:05:00Z',
  brightness: 0.7,
  lights: ['a'],
  covers: ['Room A'],
  state: 'running',
}
const ITEM: AttentionItem = {
  id: 'light-offline:a',
  kind: 'light-offline',
  severity: 'normal',
  subject: { type: 'light', id: 'a' },
  title: 'A offline',
  detail: 'A offline since 17:02.',
  since: '2026-09-23T17:02:00Z',
  actions: ['details'],
}
const STAT: DeviceStat = {
  id: 'a',
  name: 'A',
  send_fps: 60,
  latency_ms: 50,
  frames_dropped: 0,
  dropped_pct: 0,
  connected: true,
  status: 'online',
}
const DECK: Deck = { number: 2, player: 'Player 2', state: 'playing', bpm: 124, pitch_percent: 1.2, master: true }

let store: LiveStore
beforeEach(() => {
  store = createLiveStore()
})

describe('applyMessage', () => {
  it('starts out knowing nothing', () => {
    expect(store.getState()).toEqual(EMPTY_LIVE)
  })

  it.each<[string, ServerMessage, Partial<LiveState>]>([
    ['running', { channel: 'running', zones: [ZONE] }, { running: { zones: [ZONE], overlays: [] } }],
    [
      'lights',
      { channel: 'lights', lights: [{ id: 'a', status: 'offline', statusSince: '2026-09-23T17:02:00Z' }] },
      { lights: { a: { id: 'a', status: 'offline', statusSince: '2026-09-23T17:02:00Z' } } },
    ],
    ['attention', { channel: 'attention', items: [ITEM] }, { attention: [ITEM] }],
    ['transport', { channel: 'transport', state: 'simulating' }, { previewOnly: true }],
    ['stats', { channel: 'stats', devices: [STAT] }, { stats: { a: STAT } }],
    ['decks', { channel: 'decks', decks: [DECK] }, { decks: [DECK] }],
    ['signals', { channel: 'signals', values: { loudness: 0.5 } }, { signals: { loudness: 0.5 } }],
  ])('stores %s', (_, message, expected) => {
    applyMessage(store, message, 0)
    expect(store.getState()).toMatchObject(expected)
  })

  it('reads transport "playing" as preview only off', () => {
    applyMessage(store, { channel: 'transport', state: 'playing' }, 0)
    expect(store.getState().previewOnly).toBe(false)
  })

  it('normalises the beat', () => {
    const v1 = {
      channel: 'beat', bpm: 120, beat_phase: 0, bar_phase: 0, is_playing: true, beat_pos: 1,
      pitch_percent: 0, deck_number: null, deck_name: null,
    } as const
    applyMessage(store, v1, 5)
    expect(store.getState().beat).toMatchObject({ bpm: 120, source: 'prodjlink', bar: null, receivedAt: 5 })
  })

  it('changes nothing for channels it does not keep', () => {
    const messages = [
      { channel: 'ack', id: 1, action: 'subscribe_beat' },
      { channel: 'error', detail: 'Unknown action: x' },
      { channel: 'status', ok: true, device_count: 1, avg_render_ms: 1, transport: 'playing' },
      { channel: 'fx' },
      { channel: 'later' },
    ] as ServerMessage[]
    for (const message of messages) applyMessage(store, message, 0)
    expect(store.getState()).toEqual(EMPTY_LIVE)
  })
})

describe('the app store', () => {
  it('resets to knowing nothing', () => {
    applyMessage(liveStore, { channel: 'attention', items: [ITEM] }, 0)
    resetLiveStore()
    expect(liveStore.getState()).toEqual(EMPTY_LIVE)
  })

  it('re-renders a reader only when its slice changes', () => {
    const rendered = vi.fn()
    function Count() {
      rendered()
      return <p>{useLive((state) => state.attention?.length ?? 'unknown')}</p>
    }
    render(<Count />)
    act(() => applyMessage(liveStore, { channel: 'transport', state: 'simulating' }, 0))
    expect(rendered).toHaveBeenCalledTimes(1)
    act(() => applyMessage(liveStore, { channel: 'attention', items: [ITEM] }, 0))
    expect(rendered).toHaveBeenCalledTimes(2)
    expect(screen.getByText('1')).toBeInTheDocument()
  })
})
```

- [ ] **Step 3: Run it to see it fail**

Run: `(cd web && npx vitest run src/api/live-store.test.tsx)`
Expected: FAIL, with `Failed to load url ./live-store`.

- [ ] **Step 4: Write `live-store.ts`**

```ts
// What the socket has said (spec §12.4), in one zustand store. Each value is null until its channel
// has spoken, so nothing claims to know what it hasn't heard (F0 review). Components read it a slice
// at a time through useLive(selector), so a message re-renders only the components whose slice
// changed. Frames don't come here: they go to the FrameStore, which React never watches.
import { useStore } from 'zustand'
import { useShallow } from 'zustand/react/shallow'
import { createStore, type StoreApi } from 'zustand/vanilla'
import { normaliseBeat, type Beat } from './beat'
import type { AttentionItem, Deck, Id, Inputs, LightUpdate, Overlay, RunningZone, SignalValue } from './contract'
import type { DeviceStat, ServerMessage } from './ws-messages'

/** The link: before its first message, live (with the measured frame rate), or retrying. */
export type Connection =
  | { status: 'connecting' }
  | { status: 'live'; fps: number | null }
  | { status: 'reconnecting'; attempt: number }

export interface LiveState {
  connection: Connection
  /** The latest beat message. Motion samples the BeatClock instead (§5.4). */
  beat: Beat | null
  decks: Deck[] | null
  running: { zones: RunningZone[]; overlays: Overlay[] } | null
  lights: Record<Id, LightUpdate> | null
  stats: Record<Id, DeviceStat> | null
  attention: AttentionItem[] | null
  previewOnly: boolean | null
  inputs: Inputs | null
  signals: Record<string, SignalValue> | null
}

export const EMPTY_LIVE: LiveState = {
  connection: { status: 'connecting' },
  beat: null,
  decks: null,
  running: null,
  lights: null,
  stats: null,
  attention: null,
  previewOnly: null,
  inputs: null,
  signals: null,
}

export type LiveStore = StoreApi<LiveState>

export function createLiveStore(): LiveStore {
  return createStore<LiveState>()(() => ({ ...EMPTY_LIVE }))
}

/** The app's store. The shared test setup resets it after every test. */
export const liveStore = createLiveStore()

export function resetLiveStore(store: LiveStore = liveStore): void {
  store.setState({ ...EMPTY_LIVE }, true)
}

function byId<T extends { id: Id }>(items: T[]): Record<Id, T> {
  return Object.fromEntries(items.map((item) => [item.id, item]))
}

/** Stores one message. A channel the stores don't keep (ack, error, status, fx, or one not known yet) changes nothing. */
export function applyMessage(store: LiveStore, message: ServerMessage, receivedAt: number): void {
  switch (message.channel) {
    case 'beat':
      store.setState({ beat: normaliseBeat(message, receivedAt) })
      return
    case 'decks':
      store.setState({ decks: message.decks })
      return
    case 'running':
      store.setState({ running: { zones: message.zones, overlays: message.overlays ?? [] } })
      return
    case 'lights':
      store.setState({ lights: byId(message.lights) })
      return
    case 'stats':
      store.setState({ stats: byId(message.devices) })
      return
    case 'attention':
      store.setState({ attention: message.items })
      return
    case 'transport':
      store.setState({ previewOnly: message.state === 'simulating' })
      return
    case 'inputs':
      store.setState({ inputs: message.inputs })
      return
    case 'signals':
      store.setState({ signals: message.values })
      return
    default:
      return
  }
}

/** One slice of the live store; the component re-renders when that slice changes. */
export function useLive<T>(selector: (state: LiveState) => T): T {
  return useStore(liveStore, selector)
}

/** useLive for a selector that builds an object: it re-renders only when one of its fields changed. */
export function useLiveShallow<T>(selector: (state: LiveState) => T): T {
  return useStore(liveStore, useShallow(selector))
}
```

In `web/src/test/setup.ts`, reset the app's store after every test, after `cleanup()`:

```ts
import { resetLiveStore } from '@/api/live-store'
```

```ts
afterEach(() => {
  cleanup()
  // A test that fakes the clock gets the real one back, whether or not it remembers to.
  vi.useRealTimers()
  // And a test that filled the live store leaves it empty for the next.
  resetLiveStore()
})
```

- [ ] **Step 5: Run the test**

Run: `(cd web && npx vitest run src/api/live-store.test.tsx)`
Expected: PASS (13 tests).

- [ ] **Step 6: Gate and commit**

```bash
git add web/package.json web/package-lock.json web/src/api/live-store.ts web/src/api/live-store.test.tsx web/src/test/setup.ts
git commit -m "feat(web): the live store, empty until each channel speaks, read a slice at a time"
```

---

### Task 7: The live client

Implements spec §12.4 (the socket), §9.4 ("Exponential backoff 1, 2, 4, 8 s, max 10 s. Resync everything on reconnect"), §14 Resilience, and decisions 1, 2 and 3. Review focus 1, 3 and 5. Render: `State-Reconnecting.png`, for what "Reconnecting · try 3" counts.

**Files:**
- Create: `web/src/api/live-client.ts`, `web/src/test/fake-socket.ts`
- Test: `web/src/api/live-client.test.ts`

**Interfaces:**
- Consumes: `ClockOffset`, `clientNow` and `BeatClock` (Task 5); `decodeFrame`, `FrameStore` and `FrameVersion` (Task 4); `applyMessage` and `LiveStore` (Task 6); `parseMessage`, `Command` and `ClientCommand` (Task 2).
- Produces:
  - `BACKOFF_S = [1, 2, 4, 8, 10]`, `SILENCE_MS = 3000`, `BEAT_FPS = 30`, `FRAME_FPS = 60` and `V1_FRAME_FPS = 30`.
  - `interface LiveSocket { binaryType; send(data: string); close(code?, reason?); onopen; onmessage; onclose; onerror }`. The browser's `WebSocket` is one.
  - `type OpenSocket = (url: string) => LiveSocket` and `openWebSocket: OpenSocket`.
  - `liveSocketUrl(location?)`, `backoffMs(attempt: number): number` and `measuredFps(previous, current, cap): number | null`.
  - `interface LiveClientOptions { url; store; frames; beatClock; openSocket?; onResync?; clock? }`. `clock` is seconds, `clientNow` by default.
  - `class LiveClient { start(); stop(); retryNow(); subscribeSignals(names?); malformedJson: number }`.
  - In `src/test/fake-socket.ts`: `class FakeSocket implements LiveSocket { url; sent: ClientCommand[]; closed; open(); say(message); sayRaw(data); drop(); idOf(action) }` and `fakeSockets(): { sockets: FakeSocket[]; open: OpenSocket }`.

- [ ] **Step 1: Read the spec and the render**

Re-read §9.4's Reconnecting row, §12.4, §14 Resilience, and decisions 1–3. Look at `State-Reconnecting.png` and `Phone-State-Reconnecting.png`: the chrome's "Reconnecting · try 3" is `attempt`. Read `ws_endpoint` and `_handle_command` in `src/dj_ledfx/web/ws.py`: M1 sends its snapshots on connect, `stats` every second, and a bare ack.

- [ ] **Step 2: Write the fake socket**

`web/src/test/fake-socket.ts`:

```ts
import type { LiveSocket, OpenSocket } from '@/api/live-client'
import type { ClientCommand } from '@/api/ws-messages'

/** A socket a test drives by hand: it opens, speaks and closes when told to. */
export class FakeSocket implements LiveSocket {
  binaryType: BinaryType = 'blob'
  onopen: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  readonly url: string
  /** What the client sent, parsed. */
  readonly sent: ClientCommand[] = []
  closed = false

  constructor(url: string) {
    this.url = url
  }

  send(data: string): void {
    this.sent.push(JSON.parse(data) as ClientCommand)
  }

  close(): void {
    this.closed = true
  }

  open(): void {
    this.onopen?.(new Event('open'))
  }

  /** The server sends a JSON message. */
  say(message: object): void {
    this.onmessage?.({ data: JSON.stringify(message) } as MessageEvent)
  }

  /** The server sends raw text or a binary frame. */
  sayRaw(data: string | ArrayBuffer): void {
    this.onmessage?.({ data } as MessageEvent)
  }

  /** The link drops. */
  drop(): void {
    this.onclose?.({} as CloseEvent)
  }

  /** The id the client gave its last command of this kind. */
  idOf(action: ClientCommand['action']): number {
    const command = this.sent.findLast((sent) => sent.action === action)
    if (command === undefined) throw new Error(`the client never sent ${action}`)
    return command.id
  }
}

export function fakeSockets(): { sockets: FakeSocket[]; open: OpenSocket } {
  const sockets: FakeSocket[] = []
  return {
    sockets,
    open: (url) => {
      const socket = new FakeSocket(url)
      sockets.push(socket)
      return socket
    },
  }
}
```

- [ ] **Step 3: Write the failing test**

`web/src/api/live-client.test.ts`:

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fakeSockets, type FakeSocket } from '@/test/fake-socket'
import { BeatClock } from './beat'
import { FrameStore, encodeFrame } from './frames'
import { LiveClient, backoffMs, liveSocketUrl, measuredFps } from './live-client'
import { createLiveStore, type LiveStore } from './live-store'

let store: LiveStore
let frames: FrameStore
let beatClock: BeatClock
let sockets: FakeSocket[]
let client: LiveClient
const onResync = vi.fn()

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date(2026, 8, 23, 19, 14))
  onResync.mockClear()
  store = createLiveStore()
  frames = new FrameStore()
  beatClock = new BeatClock()
  const fake = fakeSockets()
  sockets = fake.sockets
  client = new LiveClient({
    url: 'ws://test/ws',
    store,
    frames,
    beatClock,
    openSocket: fake.open,
    onResync,
    clock: () => Date.now() / 1000,
  })
})

afterEach(() => {
  client.stop()
})

const rgb = (...values: number[]) => new Uint8Array(values)
const now = () => Date.now() / 1000
const latest = () => sockets[sockets.length - 1]
const connection = () => store.getState().connection

/** The latest socket opens and the server greets it, as the backend does on connect. */
function welcome(socket = latest()) {
  socket.open()
  socket.say({ channel: 'transport', state: 'playing' })
}

/** The server acks the frame subscription: with protocol 2 for v2, bare for today's v1. */
function ackFrames(protocol?: 2, socket = latest()) {
  socket.say({
    channel: 'ack',
    id: socket.idOf('subscribe_frames'),
    action: 'subscribe_frames',
    ...(protocol === 2 ? { protocol: 2, fps: 60 } : {}),
  })
}

/** `perSecond` new frames for a light, every second for `seconds`. */
function stream(version: 1 | 2, perSecond: number, seconds: number) {
  let seq = 1000
  for (let s = 0; s < seconds; s++) {
    for (let i = 0; i < perSecond; i++) latest().sayRaw(encodeFrame(version, 'rope', seq++, rgb(0, 0, 0)))
    vi.advanceTimersByTime(1000)
  }
}

describe('LiveClient', () => {
  it('is connecting until the server first speaks, then live', () => {
    client.start()
    expect(connection()).toEqual({ status: 'connecting' })
    latest().open()
    expect(connection()).toEqual({ status: 'connecting' })
    latest().say({ channel: 'transport', state: 'playing' })
    expect(connection()).toEqual({ status: 'live', fps: null })
    expect(store.getState().previewOnly).toBe(false)
  })

  // Review focus 1: no duplicate subscriptions (§14 Resilience). Live frames only: engine M2 keeps
  // a preview running while a tab watches its stream, so only F4's preview asks for it.
  it('subscribes to the beat and to the live frames, once per connection', () => {
    client.start()
    welcome()
    expect(latest().sent).toEqual([
      expect.objectContaining({ action: 'subscribe_beat', fps: 30 }),
      expect.objectContaining({ action: 'subscribe_frames', fps: 60, protocol: 2, streams: ['live'] }),
    ])
    latest().drop()
    vi.advanceTimersByTime(1000)
    welcome()
    expect(sockets).toHaveLength(2)
    expect(sockets[1].sent.map((command) => command.action)).toEqual(['subscribe_beat', 'subscribe_frames'])
  })

  // Review focus 1.
  it('drops to Reconnecting at once on a close, then retries after 1, 2, 4, 8, 10 and 10 s', () => {
    client.start()
    welcome()
    for (const [i, seconds] of [1, 2, 4, 8, 10, 10].entries()) {
      latest().drop()
      expect(connection()).toEqual({ status: 'reconnecting', attempt: i + 1 })
      const count = sockets.length
      vi.advanceTimersByTime(seconds * 1000 - 1)
      expect(sockets).toHaveLength(count)
      vi.advanceTimersByTime(1)
      expect(sockets).toHaveLength(count + 1)
    }
  })

  // Review focus 1: a server that hangs rather than closing.
  it('drops a link that has gone silent for 3 s', () => {
    client.start()
    welcome()
    vi.advanceTimersByTime(3000)
    expect(connection().status).toBe('live')
    vi.advanceTimersByTime(1000)
    expect(connection()).toEqual({ status: 'reconnecting', attempt: 1 })
    expect(sockets[0].closed).toBe(true)
  })

  it('gives up on a connection that never opens', () => {
    client.start()
    vi.advanceTimersByTime(4000)
    expect(connection()).toEqual({ status: 'reconnecting', attempt: 1 })
  })

  it('counts attempts from the first failure, and from 1 again after it was live', () => {
    client.start()
    latest().drop()
    expect(connection()).toEqual({ status: 'reconnecting', attempt: 1 })
    vi.advanceTimersByTime(1000)
    welcome()
    latest().drop()
    expect(connection()).toEqual({ status: 'reconnecting', attempt: 1 })
  })

  // Review focus 1.
  it("keeps one socket: Try now opens one, and a dead socket's late messages are ignored", () => {
    client.start()
    welcome()
    const dead = sockets[0]
    dead.drop()
    client.retryNow()
    client.retryNow()
    expect(sockets).toHaveLength(2)
    welcome(sockets[1])
    vi.advanceTimersByTime(1000)
    expect(sockets).toHaveLength(2)
    dead.say({ channel: 'attention', items: [] })
    dead.drop()
    expect(store.getState().attention).toBeNull()
    expect(connection().status).toBe('live')
    client.retryNow()
    expect(sockets).toHaveLength(2)
  })

  // Review focus 1: a restarted server counts its frames from 1 again (§9.4, "Resync everything").
  it('resyncs on reconnect: seqs restart, the beat clock re-anchors and REST refetches', () => {
    client.start()
    welcome()
    ackFrames(2)
    latest().sayRaw(encodeFrame(2, 'rope', 500, rgb(1, 1, 1)))
    latest().say({
      channel: 'beat', bpm: 120, beat_phase: 0.5, bar_phase: 0.375, bar: 42, beat_in_bar: 2,
      pitch_percent: 0, source: 'music', stale: false, server_time: now(),
    })
    expect(beatClock.sample(now()).running).toBe(true)
    expect(onResync).not.toHaveBeenCalled()

    latest().drop()
    vi.advanceTimersByTime(1000)
    welcome()
    ackFrames(2)
    expect(onResync).toHaveBeenCalledTimes(1)
    expect(beatClock.sample(now()).running).toBe(false)
    latest().sayRaw(encodeFrame(2, 'rope', 1, rgb(2, 2, 2)))
    expect(frames.get('rope')).toMatchObject({ seq: 1, rgb: rgb(2, 2, 2) })
  })

  // Review focus 3: engine M1 acks without a protocol and sends v1 frames.
  it('falls back to v1 frames at 30 fps when the ack has no protocol', () => {
    client.start()
    welcome()
    latest().sayRaw(encodeFrame(1, 'rope', 1, rgb(9, 9, 9)))
    expect(frames.live.size).toBe(0) // before the ack, the version isn't known
    ackFrames()
    latest().sayRaw(encodeFrame(1, 'rope', 2, rgb(1, 2, 3)))
    expect(frames.get('rope')?.rgb).toEqual(rgb(1, 2, 3))
    stream(1, 60, 3)
    expect(connection()).toEqual({ status: 'live', fps: 30 })
  })

  it('reads v2 frames once the ack says protocol 2, and measures up to 60 fps', () => {
    client.start()
    welcome()
    ackFrames(2)
    latest().sayRaw(encodeFrame(2, 'rope', 1, rgb(4, 5, 6), 'preview'))
    expect(frames.get('rope', 'preview')?.rgb).toEqual(rgb(4, 5, 6))
    stream(2, 60, 3)
    expect(connection()).toEqual({ status: 'live', fps: 60 })
  })

  it('shows no frame rate while no frames flow', () => {
    client.start()
    welcome()
    ackFrames(2)
    vi.advanceTimersByTime(2000)
    expect(connection()).toEqual({ status: 'live', fps: null })
  })

  // Review focus 5.
  it('drops bad JSON and counts it, and the next message still lands', () => {
    client.start()
    welcome()
    latest().sayRaw('{"channel":')
    latest().sayRaw('{"channel":"attention"}')
    expect(client.malformedJson).toBe(2)
    latest().say({ channel: 'attention', items: [] })
    expect(store.getState().attention).toEqual([])
  })

  it("feeds each beat to the beat clock, on the server's clock", () => {
    client.start()
    welcome()
    latest().say({
      channel: 'beat', bpm: 120, beat_phase: 0.5, bar_phase: 0.375, bar: 42, beat_in_bar: 2,
      pitch_percent: 0, source: 'music', stale: false, server_time: now(),
    })
    vi.advanceTimersByTime(250)
    expect(beatClock.sample(now())).toMatchObject({ bar: 42, beatInBar: 3, running: true })
  })

  it('subscribes to signals when asked, and again after a reconnect', () => {
    client.start()
    welcome()
    client.subscribeSignals(['loudness'])
    expect(latest().sent.at(-1)).toMatchObject({ action: 'subscribe_signals', names: ['loudness'] })
    latest().drop()
    vi.advanceTimersByTime(1000)
    welcome()
    expect(latest().sent.map((command) => command.action)).toEqual(['subscribe_beat', 'subscribe_frames', 'subscribe_signals'])
  })

  it('stops for good: it closes the socket and never retries', () => {
    client.start()
    welcome()
    client.stop()
    expect(sockets[0].closed).toBe(true)
    vi.advanceTimersByTime(60_000)
    expect(sockets).toHaveLength(1)
  })
})

describe('measuredFps', () => {
  it.each([
    [0, 60, 60, 60],
    [60, 59, 60, 60],
    [59, 61, 60, 60],
    [40, 44, 60, 42],
    [60, 60, 30, 30],
    [60, 0, 60, null],
  ])('(%i, %i, cap %i) is %s', (previous, current, cap, fps) => {
    expect(measuredFps(previous, current, cap)).toBe(fps)
  })
})

describe('backoffMs', () => {
  it.each([
    [1, 1000],
    [2, 2000],
    [3, 4000],
    [4, 8000],
    [5, 10_000],
    [9, 10_000],
  ])('waits before retry %i for %i ms', (attempt, ms) => {
    expect(backoffMs(attempt)).toBe(ms)
  })
})

describe('liveSocketUrl', () => {
  it("is the page's own /ws, secure when the page is", () => {
    expect(liveSocketUrl({ protocol: 'http:', host: 'localhost:5174' })).toBe('ws://localhost:5174/ws')
    expect(liveSocketUrl({ protocol: 'https:', host: 'example.test' })).toBe('wss://example.test/ws')
  })
})
```

- [ ] **Step 4: Run it to see it fail**

Run: `(cd web && npx vitest run src/api/live-client.test.ts)`
Expected: FAIL, with `Failed to load url ./live-client`.

- [ ] **Step 5: Write `live-client.ts`**

```ts
// The one link to the server (spec §12.4, §9.4). It subscribes once per connection, stores what the
// server says (the live store) and the frames it streams (the FrameStore), and feeds the beat clock.
// When the link drops it says so at once and retries after 1, 2, 4 and 8 s, then every 10 s. On
// the way back it resyncs: frame seqs, the beat clock, and REST data through onResync.
import { ClockOffset, clientNow, type BeatClock } from './beat'
import { decodeFrame, type FrameStore, type FrameVersion } from './frames'
import { applyMessage, type LiveStore } from './live-store'
import { parseMessage, type Command } from './ws-messages'

export const BACKOFF_S = [1, 2, 4, 8, 10]
/** A link silent this long is dead: the server sends stats every second. */
export const SILENCE_MS = 3000
export const BEAT_FPS = 30
export const FRAME_FPS = 60
/** The most a v1 link (engine M1) sends. */
export const V1_FRAME_FPS = 30
const TICK_MS = 1000

/** What the client needs of a WebSocket. The browser's WebSocket is one. */
export interface LiveSocket {
  binaryType: BinaryType
  send(data: string): void
  close(code?: number, reason?: string): void
  onopen: ((event: Event) => void) | null
  onmessage: ((event: MessageEvent) => void) | null
  onclose: ((event: CloseEvent) => void) | null
  onerror: ((event: Event) => void) | null
}
export type OpenSocket = (url: string) => LiveSocket
export const openWebSocket: OpenSocket = (url) => new WebSocket(url)

/** The page's own /ws, which the Vite proxy and FastAPI both serve. */
export function liveSocketUrl(location: Pick<Location, 'protocol' | 'host'> = window.location): string {
  return `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/ws`
}

/** How long to wait before retry `attempt` (1, 2, …). */
export function backoffMs(attempt: number): number {
  return BACKOFF_S[Math.min(attempt, BACKOFF_S.length) - 1] * 1000
}

/** Decision 3: this second's count and the last's, averaged and capped; null when no frames flow. */
export function measuredFps(previous: number, current: number, cap: number): number | null {
  if (current === 0) return null
  return Math.min(cap, previous > 0 ? Math.round((previous + current) / 2) : current)
}

export interface LiveClientOptions {
  url: string
  store: LiveStore
  frames: FrameStore
  beatClock: BeatClock
  openSocket?: OpenSocket
  /** After a reconnect: fetch again what REST loaded (resync() in queries.ts). */
  onResync?: () => void
  /** Seconds on a clock that only moves forward (clientNow). Tests pass their own. */
  clock?: () => number
}

export class LiveClient {
  /** JSON messages dropped as malformed: bad JSON, no channel, a snapshot missing its list. */
  malformedJson = 0
  private readonly url: string
  private readonly store: LiveStore
  private readonly frames: FrameStore
  private readonly beatClock: BeatClock
  private readonly openSocket: OpenSocket
  private readonly onResync: () => void
  private readonly clock: () => number
  private readonly offset = new ClockOffset()
  private socket: LiveSocket | null = null
  private opened = false
  private heard = false
  private everLive = false
  private attempt = 0
  private frameAckId: number | null = null
  private frameVersion: FrameVersion | null = null
  private frameCap = V1_FRAME_FPS
  private lastWindow = 0
  private lastHeardAt = 0
  private nextId = 1
  private signals: string[] | null = null
  private retryTimer: ReturnType<typeof setTimeout> | null = null
  private tickTimer: ReturnType<typeof setInterval> | null = null
  private running = false

  constructor(options: LiveClientOptions) {
    this.url = options.url
    this.store = options.store
    this.frames = options.frames
    this.beatClock = options.beatClock
    this.openSocket = options.openSocket ?? openWebSocket
    this.onResync = options.onResync ?? (() => {})
    this.clock = options.clock ?? clientNow
  }

  start(): void {
    if (this.running) return
    this.running = true
    this.tickTimer = setInterval(() => this.tick(), TICK_MS)
    this.connect()
  }

  stop(): void {
    this.running = false
    if (this.tickTimer !== null) clearInterval(this.tickTimer)
    if (this.retryTimer !== null) clearTimeout(this.retryTimer)
    this.tickTimer = null
    this.retryTimer = null
    const socket = this.socket
    this.detach()
    socket?.close()
  }

  /** §9.4's "Try now": retry at once rather than wait out the backoff. */
  retryNow(): void {
    if (!this.running || this.socket !== null) return
    if (this.retryTimer !== null) clearTimeout(this.retryTimer)
    this.retryTimer = null
    this.connect()
  }

  /** The `signals` channel (F6, F8): these names, or every signal. Sent again after a reconnect. */
  subscribeSignals(names?: string[]): void {
    this.signals = names ?? []
    if (this.opened) this.sendSignals()
  }

  private connect(): void {
    const socket = this.openSocket(this.url)
    socket.binaryType = 'arraybuffer'
    this.socket = socket
    this.opened = false
    this.heard = false
    this.frameAckId = null
    this.frameVersion = null
    this.lastHeardAt = this.clock()
    socket.onopen = () => {
      if (this.socket === socket) this.subscribe()
    }
    socket.onmessage = (event) => {
      if (this.socket === socket) this.receive(event.data)
    }
    socket.onclose = () => this.drop(socket)
    socket.onerror = () => this.drop(socket)
  }

  private subscribe(): void {
    this.opened = true
    this.send({ action: 'subscribe_beat', fps: BEAT_FPS })
    this.frameAckId = this.send({
      action: 'subscribe_frames',
      fps: FRAME_FPS,
      protocol: 2,
      // Engine M2 ends a preview nobody watches (its Spec Ruling 9), so the preview stream is F4's
      // to ask for while its preview is open.
      streams: ['live'],
    })
    if (this.signals !== null) this.sendSignals()
  }

  private sendSignals(): void {
    const names = this.signals ?? []
    this.send(names.length > 0 ? { action: 'subscribe_signals', names } : { action: 'subscribe_signals' })
  }

  private send(command: Command): number {
    const id = this.nextId++
    this.socket?.send(JSON.stringify({ ...command, id }))
    return id
  }

  private receive(data: unknown): void {
    const now = this.clock()
    this.lastHeardAt = now
    if (!this.heard) this.firstWord()
    if (typeof data === 'string') this.receiveText(data, now)
    // A frame before the ack is dropped: its version isn't known yet (decision 1).
    else if (data instanceof ArrayBuffer && this.frameVersion !== null) {
      decodeFrame(data, this.frameVersion, this.frames, now)
    }
  }

  /** The first message on a socket: the link is live. After a drop, that's a reconnect. */
  private firstWord(): void {
    this.heard = true
    this.attempt = 0
    if (this.everLive) {
      // The server may have restarted: seqs count from 1 again, the beat re-anchors, and REST data
      // is fetched again (§9.4, "Resync everything on reconnect").
      this.frames.resetSeqs()
      this.beatClock.reset()
      this.offset.reset()
      this.onResync()
    }
    this.everLive = true
    this.lastWindow = 0
    this.frames.sampleFps()
    this.store.setState({ connection: { status: 'live', fps: null } })
  }

  private receiveText(text: string, now: number): void {
    const message = parseMessage(text)
    if (message === null) {
      this.malformedJson += 1
      return
    }
    if (message.channel === 'ack' && message.id === this.frameAckId) {
      this.frameVersion = message.protocol === 2 ? 2 : 1
      this.frameCap = this.frameVersion === 2 ? Math.min(FRAME_FPS, message.fps ?? FRAME_FPS) : V1_FRAME_FPS
      return
    }
    applyMessage(this.store, message, now)
    if (message.channel === 'beat') {
      const beat = this.store.getState().beat
      if (beat === null) return
      if (beat.serverTime !== null) this.offset.add(beat.serverTime, now)
      this.beatClock.receive(beat, this.offset.value)
    }
  }

  private drop(socket: LiveSocket): void {
    if (this.socket !== socket) return // an old socket's late close
    this.detach()
    socket.close()
    if (!this.running) return
    this.attempt += 1
    this.store.setState({ connection: { status: 'reconnecting', attempt: this.attempt } })
    this.retryTimer = setTimeout(() => {
      this.retryTimer = null
      this.connect()
    }, backoffMs(this.attempt))
  }

  private detach(): void {
    const socket = this.socket
    if (socket !== null) {
      socket.onopen = null
      socket.onmessage = null
      socket.onclose = null
      socket.onerror = null
    }
    this.socket = null
    this.opened = false
    this.frameVersion = null
  }

  /** Once a second: the silence watchdog, and the frame rate for "Live 60 fps". */
  private tick(): void {
    const socket = this.socket
    if (socket !== null && this.clock() - this.lastHeardAt > SILENCE_MS / 1000) {
      this.drop(socket)
      return
    }
    const connection = this.store.getState().connection
    if (connection.status !== 'live') return
    const current = this.frames.sampleFps()
    const fps = measuredFps(this.lastWindow, current, this.frameCap)
    this.lastWindow = current
    // Only a change is stored, so a steady 60 fps re-renders nothing.
    if (fps !== connection.fps) this.store.setState({ connection: { status: 'live', fps } })
  }
}
```

- [ ] **Step 6: Run the test**

Run: `(cd web && npx vitest run src/api/live-client.test.ts)`
Expected: PASS (28 tests).

- [ ] **Step 7: Gate and commit**

```bash
git add web/src/api/live-client.ts web/src/api/live-client.test.ts web/src/test/fake-socket.ts
git commit -m "feat(web): the live client: one socket, backoff, a silence watchdog, resync and the frame rate"
```

---

### Task 8: Mock fixtures and the scenarios

Implements spec §12.5's fixtures and scenarios, §9.1–9.5's states, §11.3 (zones and take-over) and §14 Unit ("attention ordering"). Decisions 4, 7 and 8. Renders: `Main.png`, `Inputs.png`, `Live-Doorbell.png`, `State-Transition.png`, `State-Problems.png`, `State-Firmware.png`, `State-Inputs-Down.png`, `State-Nothing-Running.png`, `State-No-Lights-Placed.png`, `State-Reconnecting.png`, `State-Preview-Only.png` and `Phone-Tempo.png`.

**Files:**
- Create: `web/src/api/mocks/home.json`, `web/src/api/mocks/looks.json` (byte copies), `web/src/api/mocks/fixtures.ts`, `web/src/api/mocks/scenarios.ts`
- Modify: `web/src/design/payload.node.test.ts` (two more copies), `web/tsconfig.app.json` (`resolveJsonModule`)
- Test: `web/src/api/mocks/fixtures.test.ts`, `web/src/api/mocks/scenarios.test.ts`

**Interfaces:**
- Consumes: the contract types (Task 2), and `formatTime` and `formatBpm` from `src/lib/format.ts` (F0).
- Produces, from `fixtures.ts`:
  - `HOME_TOTALS: { lights: number; leds: number }` and `homeFixture: Home`.
  - `lightShape(raw): LightShape` and `lightFixtures(since: string): Light[]`. Each call builds new objects; every light starts `idle`, powered off, with no frames.
  - `lookFixtures: Look[]`, `lookName(id): string` and `roomName(id): string`.
  - `HOME_ZONE = 'home'`, `zoneFixtures(home, lights): Zone[]` and `coversOf(home, lights, ids): string[]`.
- Produces, from `scenarios.ts`:
  - `SCENARIOS`, the eleven names, `type ScenarioName`, and `isScenario(name): name is ScenarioName`.
  - `interface ScenarioBeat { source; bpm; bar; beatInBar; pitchPercent; stale }`.
  - `interface ScenarioLink { dropAfterMs: number | null }`.
  - `interface ScenarioState { name; home; lights; looks; zones; running; overlays; attention; beat; decks; inputs; signals; previewOnly; link }`.
  - `orderAttention(items): AttentionItem[]`, and `buildScenario(name, now?: Date): ScenarioState`. Each call builds a new state, which the mock server (Task 10) then changes as requests arrive.

- [ ] **Step 1: Read the spec and the renders**

Re-read §12.5, §9, §11.3 and decisions 4, 7 and 8. Look at each render named above. The HTML beside each PNG in the reference folder has the same text, and is cheaper to read than the image. Read M1's attention copy in `src/dj_ledfx/zones/attention.py`, and the firmware effects' `display_name`s in `src/dj_ledfx/effects/firmware_lifx.py` and `firmware_openrgb.py`.

The renders show LAN addresses, MACs and light models. None of them goes into code (Global Constraints). Addresses come from `192.0.2.0/24`, there are no MACs, a light's `model` is read from `home.json`, and the decks are "Player 1" to "Player 4".

- [ ] **Step 2: Copy the handoff's files, and pin the copies**

```bash
cp docs/design/web-app/home.json web/src/api/mocks/home.json
cp docs/design/web-app/looks.json web/src/api/mocks/looks.json
```

In `web/src/design/payload.node.test.ts`, add both to `COPIES`:

```ts
const COPIES = [
  { name: 'tokens.css', copy: 'web/src/styles/tokens.css' },
  { name: 'icons.ts', copy: 'web/src/design/icons.ts' },
  { name: 'home.json', copy: 'web/src/api/mocks/home.json' },
  { name: 'looks.json', copy: 'web/src/api/mocks/looks.json' },
]
```

In `web/tsconfig.app.json`, under `/* Bundler mode */`, add:

```json
    "resolveJsonModule": true,
```

- [ ] **Step 3: Write the failing tests**

`web/src/api/mocks/fixtures.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import homeJson from './home.json'
import looksJson from './looks.json'
import {
  HOME_TOTALS, HOME_ZONE, coversOf, homeFixture, lightFixtures, lookFixtures, lookName, roomName, zoneFixtures,
} from './fixtures'

const SINCE = '2026-09-23T17:04:00.000Z'
const lights = lightFixtures(SINCE)

describe('the fixtures', () => {
  it('builds every light in home.json, and their LEDs add up to its totals', () => {
    expect(lights).toHaveLength(HOME_TOTALS.lights)
    expect(lights.reduce((sum, light) => sum + light.leds, 0)).toBe(HOME_TOTALS.leds)
  })

  it("gives each light the shape the file's flat fields describe", () => {
    for (const raw of homeJson.lights) {
      const shape = lights.find((light) => light.id === raw.id)?.shape
      expect(shape?.kind).toBe(raw.shape)
      if (shape?.kind === 'point' && 'position' in raw) expect(shape.position).toEqual(raw.position)
      if (shape?.kind === 'bent-line' && 'path' in raw) expect(shape.path).toEqual(raw.path)
      if (shape?.kind === 'line') expect(shape.path).toHaveLength(2)
      if (shape?.kind === 'grid') expect(shape.rotation).toEqual([0, 0, 0])
    }
  })

  it('reads capabilities in lower case, with no MAC and only documentation addresses', () => {
    for (const light of lights) {
      expect(light.capabilities.every((name) => name === name.toLowerCase())).toBe(true)
      expect(light.mac ?? null).toBeNull()
      expect(light.address).toMatch(/^192\.0\.2\.\d+$/)
      expect(light).toMatchObject({ status: 'idle', statusSince: SINCE, power: false, sendFps: 0 })
    }
    expect(new Set(lights.map((light) => light.address)).size).toBe(lights.length)
  })

  it("serves the handoff's looks, built in, each needing its inputs", () => {
    expect(lookFixtures.map((look) => look.id)).toEqual(looksJson.looks.map((look) => look.id))
    for (const raw of looksJson.looks) {
      const look = lookFixtures.find((candidate) => candidate.id === raw.id)
      expect(look).toMatchObject({ name: raw.name, builtIn: true, needs: raw.inputs, description: raw.description })
      expect(lookName(raw.id)).toBe(raw.name)
    }
    expect(() => lookName('nope')).toThrow('nope')
  })

  it('makes a zone of the whole home, of each room with lights, and of each sub-zone', () => {
    const zones = zoneFixtures(homeFixture, lights)
    expect(zones[0]).toMatchObject({ id: HOME_ZONE, kind: 'home', lights: lights.map((light) => light.id) })
    const rooms = zones.filter((zone) => zone.kind === 'room')
    expect(rooms.map((zone) => zone.id)).toEqual(homeFixture.rooms.filter((room) => room.hasLights).map((room) => room.id))
    for (const zone of rooms) {
      expect(zone.name).toBe(roomName(zone.id))
      expect(zone.lights).toEqual(lights.filter((light) => light.room === zone.id).map((light) => light.id))
    }
    const subZones = zones.filter((zone) => zone.kind === 'sub-zone')
    expect(subZones.map((zone) => zone.id)).toEqual(homeFixture.subZones.map((sub) => sub.id))
  })

  it('lists the rooms a zone covers in the order of its lights', () => {
    expect(coversOf(homeFixture, lights, ['kcorner', 'bedl', 'kfloor', 'neon'])).toEqual([
      roomName('kitchen'),
      roomName('bedroom'),
      roomName('corridor'),
    ])
  })

  it("gives the PC's parts an id each, as engine M2 will", () => {
    const pc = lights.find((light) => light.id === 'pc')
    expect(pc?.parts?.length).toBeGreaterThan(1)
    expect(new Set(pc?.parts?.map((part) => (part as { id?: string }).id)).size).toBe(pc?.parts?.length)
  })
})
```

`web/src/api/mocks/scenarios.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { HERO_CHROME } from '@/chrome/state'
import { formatTime } from '@/lib/format'
import type { AttentionItem } from '../contract'
import { HOME_ZONE, lookName, roomName } from './fixtures'
import { SCENARIOS, buildScenario, isScenario, orderAttention } from './scenarios'

const NOW = new Date(2026, 8, 23, 19, 14)
const hhmm = (iso: string) => formatTime(new Date(iso))
const light = (name: (typeof SCENARIOS)[number], id: string) =>
  buildScenario(name, NOW).lights.find((candidate) => candidate.id === id)

describe('every scenario', () => {
  it.each(SCENARIOS)('%s runs known looks on known lights, each light in one zone at most', (name) => {
    const state = buildScenario(name, NOW)
    const ids = new Set(state.lights.map((candidate) => candidate.id))
    const owned = state.running.flatMap((zone) => zone.lights)
    expect(new Set(owned).size).toBe(owned.length)
    for (const id of owned) expect(ids.has(id)).toBe(true)
    for (const zone of state.running) {
      expect(zone.lookName).toBe(lookName(zone.lookId))
      expect(state.zones.map((candidate) => candidate.id)).toContain(zone.zoneId)
    }
    expect(state.attention).toEqual(orderAttention(state.attention))
  })

  it('is built afresh each time', () => {
    const first = buildScenario('hero', NOW)
    first.running.pop()
    first.lights[0].name = 'changed'
    const second = buildScenario('hero', NOW)
    expect(second.running).toHaveLength(3)
    expect(second.lights[0].name).not.toBe('changed')
  })

  it('knows its names', () => {
    expect(isScenario('hero')).toBe(true)
    expect(isScenario('preview-only')).toBe(true)
    expect(isScenario('nope')).toBe(false)
  })
})

describe('orderAttention', () => {
  it('puts high severity first, then the newest', () => {
    const item = (id: string, severity: AttentionItem['severity'], since: string): AttentionItem => ({
      id,
      severity,
      since,
      kind: 'zone-slow',
      subject: { type: 'zone', id },
      title: id,
      detail: '',
      actions: [],
    })
    const items = [
      item('a', 'normal', '2026-09-23T17:02:00Z'),
      item('b', 'high', '2026-09-23T17:00:00Z'),
      item('c', 'normal', '2026-09-23T19:12:00Z'),
      item('d', 'high', '2026-09-23T19:00:00Z'),
    ]
    expect(orderAttention(items).map((each) => each.id)).toEqual(['d', 'b', 'c', 'a'])
  })
})

describe('the hero', () => {
  const hero = buildScenario('hero', NOW)

  it('runs the three zones of the 19:14 render', () => {
    expect(hero.running.map((zone) => [zone.zoneId, zone.lookId, zone.brightness])).toEqual([
      [HOME_ZONE, 'homesunset', 0.85],
      ['living', 'fireflies', 0.7],
      ['office', 'comets', 1],
    ])
    expect(hero.running.map((zone) => hhmm(zone.since))).toEqual(['18:04', '19:05', '19:10'])
    expect(hero.running[0].covers).toEqual([roomName('kitchen'), roomName('bedroom'), roomName('corridor')])
  })

  it('has Rope offline since 17:02 and Candle 2 switched off, and one item needing attention', () => {
    const rope = hero.lights.find((candidate) => candidate.id === 'rope')
    expect(rope?.status).toBe('offline')
    expect(hhmm(rope?.statusSince ?? '')).toBe('17:02')
    expect(light('hero', 'candle2')).toMatchObject({ status: 'switched-off', power: false })
    expect(hero.lights.filter((candidate) => candidate.status === 'streaming')).toHaveLength(17)
    expect(hero.attention).toHaveLength(HERO_CHROME.attention.total)
    expect(hero.attention[0]).toMatchObject({
      id: 'light-offline:rope',
      kind: 'light-offline',
      severity: 'normal',
      subject: { type: 'light', id: 'rope' },
    })
    expect(hero.attention[0].detail).toContain('since 17:02')
  })

  it("agrees with the chrome's fixture on the tempo and the sunset", () => {
    expect(hero.beat).toMatchObject({
      source: HERO_CHROME.tempo.source,
      bpm: HERO_CHROME.tempo.bpm,
      bar: HERO_CHROME.tempo.bar,
      beatInBar: HERO_CHROME.tempo.beat,
      stale: false,
    })
    expect(hhmm(hero.inputs.sun.sunset)).toBe(HERO_CHROME.sunset)
    expect(hero.previewOnly).toBe(false)
    expect(hero.link.dropAfterMs).toBeNull()
  })
})

describe('the other scenarios', () => {
  it('doorbell plays the ripple over everything, with 2.4 s left', () => {
    const { overlays } = buildScenario('doorbell', NOW)
    expect(overlays).toHaveLength(1)
    expect(overlays[0]).toMatchObject({ lookId: 'doorbell', name: lookName('doorbell'), progress: 0.4 })
    expect(Date.parse(overlays[0].endsAt) - NOW.getTime()).toBe(2400)
  })

  it('transition dissolves the living room from one look into another', () => {
    const living = buildScenario('transition', NOW).running.find((zone) => zone.zoneId === 'living')
    expect(living).toMatchObject({
      lookId: 'embers',
      state: 'transition',
      transition: { from: lookName('fireflies'), kind: 'dissolve', progress: 0.62 },
    })
  })

  it('problems lists five items, the crash first', () => {
    const state = buildScenario('problems', NOW)
    expect(state.attention.map((item) => item.kind)).toEqual([
      'zone-crashed',
      'input-stale',
      'zone-slow',
      'input-disconnected',
      'light-offline',
    ])
    expect(state.running.find((zone) => zone.zoneId === 'kitchen')).toMatchObject({ state: 'crashed', lookId: 'lava' })
    expect(state.running.find((zone) => zone.zoneId === 'living')).toMatchObject({
      state: 'slow',
      fps: { actual: 38, target: 60 },
    })
    const waiting = state.looks.filter((look) => look.needs?.includes('home-assistant')).map((look) => look.name)
    const disconnected = state.attention.find((item) => item.kind === 'input-disconnected')
    for (const name of waiting) expect(disconnected?.detail).toContain(name)
    expect(state.beat).toMatchObject({ source: 'internal', bpm: 118 })
  })

  it("firmware runs each light's own effect, and a streamed copy where there is none", () => {
    const state = buildScenario('firmware', NOW)
    expect(state.running).toHaveLength(1)
    expect(state.running[0]).toMatchObject({ zoneId: HOME_ZONE, lookId: 'firmware', brightness: 0.9 })
    expect(state.running[0].lights).toHaveLength(state.lights.length)
    for (const each of state.lights) {
      if (each.builtInEffects.length === 0) expect(each.status).toBe('streamed-copy')
      else expect(each).toMatchObject({ status: 'own-effect', ownEffect: each.builtInEffects[0] })
    }
    expect(state.lights.filter((each) => each.ownEffect === 'LIFX waveform')).toHaveLength(11)
    expect(state.lights.filter((each) => each.status === 'streamed-copy')).toHaveLength(1)
    expect(state.attention).toEqual([])
  })

  it('inputs-down has the music stale, Home Assistant disconnected and the tempo on Internal', () => {
    const state = buildScenario('inputs-down', NOW)
    expect(state.inputs.music.state).toBe('stale')
    expect(NOW.getTime() - Date.parse(state.inputs.music.updatedAt)).toBe(42_000)
    expect(state.inputs.homeAssistant).toMatchObject({ state: 'disconnected', retryS: 10 })
    expect(hhmm(state.inputs.homeAssistant.since)).toBe('19:02')
    expect(state.inputs.tempo).toMatchObject({ source: 'internal', bpm: 118 })
    expect(state.attention.map((item) => item.kind)).toEqual(['input-stale', 'input-disconnected', 'light-offline'])
  })

  it('nothing-running leaves 9 lights on and 10 off, and nothing needs attention', () => {
    const state = buildScenario('nothing-running', NOW)
    expect(state.running).toEqual([])
    expect(state.lights.filter((each) => each.power === true)).toHaveLength(9)
    expect(state.lights.filter((each) => each.power !== true)).toHaveLength(10)
    expect(light('nothing-running', 'rope')?.status).toBe('offline')
    expect(state.attention).toEqual([])
  })

  it('no-lights has no shapes and no anchors', () => {
    const state = buildScenario('no-lights', NOW)
    expect(state.lights.every((each) => each.shape === null)).toBe(true)
    expect(state.home.anchors).toEqual([])
  })

  it('reconnecting drops the link a second after it connects', () => {
    expect(buildScenario('reconnecting', NOW).link.dropAfterMs).toBe(1000)
  })

  it('dj-playing has four decks, Player 2 the master, and the beat from Pro DJ Link', () => {
    const state = buildScenario('dj-playing', NOW)
    expect(state.decks.map((deck) => [deck.player, deck.state, deck.master])).toEqual([
      ['Player 1', 'cued', false],
      ['Player 2', 'playing', true],
      ['Player 3', 'empty', false],
      ['Player 4', 'empty', false],
    ])
    expect(state.beat).toMatchObject({ source: 'prodjlink', bar: 17, beatInBar: 3, pitchPercent: 1.2 })
    expect(state.beat.bpm).toBeCloseTo(125.488)
    expect(state.inputs.music).toMatchObject({ state: 'idle', track: null })
  })

  it('preview-only is the hero with preview only on', () => {
    const state = buildScenario('preview-only', NOW)
    expect(state.previewOnly).toBe(true)
    expect(state.running).toEqual(buildScenario('hero', NOW).running)
  })
})
```

- [ ] **Step 4: Run them to see them fail**

```bash
(cd web && npx vitest run src/api/mocks src/design/payload.node.test.ts)
```

Expected: the two copy tests pass (the files were copied in Step 2). The mock tests fail with `Failed to load url ./fixtures` and `./scenarios`.

- [ ] **Step 5: Write `fixtures.ts`**

```ts
// Fixtures from the handoff's own files (spec §12.5). The home, its lights and the looks come from
// byte copies of home.json and looks.json, so no name, position or description is typed here
// (CLAUDE.md, "Web App Design"). What the files don't say, the mock makes up in the API's shape:
// addresses from the documentation range (RFC 5737), no MACs, and M1's latency heuristics.
import type {
  Anchor, Box2, Furniture, Home, Id, InputKind, Light, LightShape, Location, Look, Outdoor, Room, SubZone, Vec2,
  Vec3, Wall, Zone,
} from '../contract'
import homeJson from './home.json'
import looksJson from './looks.json'

type Protocol = Light['protocol']
type Capability = Light['capabilities'][number]
const CAPABILITIES: readonly string[] = ['colour', 'multizone', 'matrix', 'effects'] satisfies Capability[]
const isCapability = (name: string): name is Capability => CAPABILITIES.includes(name)

/** A light as home.json has it: its shape's fields sit on the light itself. */
interface RawLight {
  id: Id
  name: string
  room: Id
  subZone: Id | null
  model: string
  protocol: Protocol
  leds: number
  ledsEstimated: boolean
  /** Capitalised in the file ("Colour"), lower case in the API. */
  capabilities: string[]
  shape: LightShape['kind']
  confirmed: boolean
  position?: Vec3
  path?: Vec3[]
  base?: Vec3
  height?: number
  radius?: number
  center?: Vec3
  width?: number
  depth?: number
  ledOrder?: string
  parts?: { name: string; leds: number }[]
}

interface RawHome {
  northOffsetDeg: number
  size: Home['size']
  ceiling: number
  beams: number
  wallCutHeight: number
  location: Location
  outline: Vec2[]
  rooms: Room[]
  subZones: SubZone[]
  outdoor: Outdoor
  walls: Wall[]
  columns: Box2[]
  furniture: Furniture[]
  anchors: Anchor[]
  lights: RawLight[]
  totals: { lights: number; leds: number }
}

interface RawLook {
  id: Id
  name: string
  category: Look['category']
  inputs: InputKind[]
  description: string
  thumbnail: string
  scope: NonNullable<Look['scope']>
}

// JSON imports type arrays as number[], not tuples. The tests pin the shapes these casts claim.
const RAW = homeJson as unknown as RawHome
const RAW_LOOKS = (looksJson as unknown as { looks: RawLook[] }).looks

/** home.json's own totals. */
export const HOME_TOTALS = RAW.totals

export const homeFixture: Home = {
  outline: RAW.outline,
  rooms: RAW.rooms,
  subZones: RAW.subZones,
  walls: RAW.walls,
  columns: RAW.columns,
  furniture: RAW.furniture,
  anchors: RAW.anchors,
  ceiling: RAW.ceiling,
  beams: RAW.beams,
  northOffsetDeg: RAW.northOffsetDeg,
  location: RAW.location,
  size: RAW.size,
  wallCutHeight: RAW.wallCutHeight,
  outdoor: RAW.outdoor,
}

function need<T>(value: T | undefined, light: RawLight, field: string): T {
  if (value === undefined) throw new Error(`home.json: ${light.id} is a ${light.shape} with no ${field}`)
  return value
}

/** §12.2's LightShape from home.json's flat fields. A grid starts unrotated. */
export function lightShape(raw: RawLight): LightShape {
  switch (raw.shape) {
    case 'point':
      return { kind: 'point', position: need(raw.position, raw, 'position') }
    case 'line': {
      const [from, to] = need(raw.path, raw, 'path')
      return { kind: 'line', path: [from, to] }
    }
    case 'bent-line':
      return { kind: 'bent-line', path: need(raw.path, raw, 'path') }
    case 'cylinder':
      return {
        kind: 'cylinder',
        base: need(raw.base, raw, 'base'),
        height: need(raw.height, raw, 'height'),
        radius: need(raw.radius, raw, 'radius'),
      }
    case 'grid':
      return {
        kind: 'grid',
        center: need(raw.center, raw, 'center'),
        width: need(raw.width, raw, 'width'),
        depth: need(raw.depth, raw, 'depth'),
        rotation: [0, 0, 0],
      }
  }
}

/**
 * The firmware effects a light like this offers, by the engine's display names
 * (effects/firmware_lifx.py, firmware_openrgb.py). The first is what it runs in the firmware scenario.
 */
function builtInEffects(protocol: Protocol, capabilities: Capability[]): string[] {
  if (protocol === 'OpenRGB') return ['OpenRGB mode']
  if (protocol !== 'LIFX') return []
  const matrix = capabilities.includes('matrix')
  const multizone = capabilities.includes('multizone')
  if (matrix && multizone) return ['LIFX Morph', 'LIFX Flame']
  if (matrix) return ['LIFX Flame', 'LIFX Morph']
  if (multizone) return ['LIFX Move']
  return ['LIFX waveform']
}

/** CLAUDE.md's device-type heuristics: LIFX 50 ms, Govee 100 ms, USB 5 ms. Only LIFX can be probed. */
const LATENCY_MS: Record<Protocol, number> = { LIFX: 50, Govee: 100, OpenRGB: 5 }

/** Every light in home.json, idle and off since `since`. Each call builds new objects. */
export function lightFixtures(since: string): Light[] {
  return RAW.lights.map((raw, index): Light => {
    const capabilities = raw.capabilities.map((name) => name.toLowerCase()).filter(isCapability)
    return {
      id: raw.id,
      name: raw.name,
      room: raw.room,
      subZone: raw.subZone,
      model: raw.model,
      protocol: raw.protocol,
      leds: raw.leds,
      capabilities,
      builtInEffects: builtInEffects(raw.protocol, capabilities),
      // Engine M2 gives each part an id (its Spec Ruling 4); the mock's are made up.
      parts: raw.parts?.map((part, number) => ({ ...part, id: `${raw.id}-part-${number + 1}` })) ?? null,
      shape: lightShape(raw),
      ledOrder: raw.ledOrder ?? '',
      confirmed: raw.confirmed,
      status: 'idle',
      statusSince: since,
      ownEffect: null,
      latency: { measuredMs: LATENCY_MS[raw.protocol], overrideMs: null, estimated: raw.protocol !== 'LIFX' },
      sendFps: 0,
      droppedPct: 0,
      address: `192.0.2.${10 + index}`,
      mac: null,
      firmware: null,
      power: false,
      colour: null,
    }
  })
}

/** The handoff's looks as M1 serves its built-ins: `needs` is the look's `inputs`. */
export const lookFixtures: Look[] = RAW_LOOKS.map((raw) => ({
  id: raw.id,
  name: raw.name,
  category: raw.category,
  builtIn: true,
  derivedFrom: null,
  description: raw.description,
  thumbnail: raw.thumbnail,
  scope: raw.scope,
  needs: raw.inputs,
  uses: [],
  starred: false,
  layers: [],
  modifiers: { trailsS: null, downbeatFlash: false, brightnessCap: null, evening: false },
  transition: { kind: 'cut', durationS: 0 },
}))

export function lookName(id: Id): string {
  const look = RAW_LOOKS.find((candidate) => candidate.id === id)
  if (look === undefined) throw new Error(`looks.json has no look ${id}`)
  return look.name
}

export function roomName(id: Id): string {
  const room = RAW.rooms.find((candidate) => candidate.id === id)
  if (room === undefined) throw new Error(`home.json has no room ${id}`)
  return room.name
}

/** The whole home's zone id, as engine M2 names it (its Spec Ruling 2). */
export const HOME_ZONE = 'home'

/** §11.3: "Whole home, each room with lights, sub-zones (Office desk, Kitchen counter)". */
export function zoneFixtures(home: Home, lights: Light[]): Zone[] {
  const ids = (keep: (light: Light) => boolean) => lights.filter(keep).map((light) => light.id)
  return [
    { id: HOME_ZONE, name: 'Whole home', kind: 'home', lights: ids(() => true) },
    ...home.rooms
      .filter((room) => room.hasLights)
      .map((room): Zone => ({ id: room.id, name: room.name, kind: 'room', lights: ids((light) => light.room === room.id) })),
    ...home.subZones.map(
      (sub): Zone => ({ id: sub.id, name: sub.name, kind: 'sub-zone', lights: ids((light) => light.subZone === sub.id) }),
    ),
  ]
}

/** The rooms a zone's lights are in, in the order of its lights: §12.2's `covers`. */
export function coversOf(home: Home, lights: Light[], ids: Id[]): string[] {
  const rooms = new Set<Id>()
  for (const id of ids) {
    const room = lights.find((light) => light.id === id)?.room
    if (room) rooms.add(room)
  }
  return [...rooms].map((id) => home.rooms.find((room) => room.id === id)?.name ?? id)
}
```

- [ ] **Step 6: Write `scenarios.ts`**

```ts
// The §12.5 scenarios, each a whole server state: the hero at 19:14 and the states around it, from
// the reference renders' sample content. Times count from `now`, so a clock fixed at 19:14 shows the
// renders' times (decision 8). Names come from the fixtures; ids pick things out of them.
import { formatBpm, formatTime } from '@/lib/format'
import type {
  AttentionItem, Deck, Home, Id, Inputs, Light, Look, Overlay, RunningZone, Signal, TempoSource, Zone,
} from '../contract'
import {
  HOME_ZONE, coversOf, homeFixture, lightFixtures, lookFixtures, lookName, roomName, zoneFixtures,
} from './fixtures'

export const SCENARIOS = [
  'hero',
  'doorbell',
  'transition',
  'problems',
  'firmware',
  'inputs-down',
  'nothing-running',
  'no-lights',
  'reconnecting',
  'dj-playing',
  'preview-only',
] as const
export type ScenarioName = (typeof SCENARIOS)[number]

export function isScenario(name: string): name is ScenarioName {
  return (SCENARIOS as readonly string[]).includes(name)
}

/** Where a scenario's beat starts. It moves unless stale or at 0 BPM. */
export interface ScenarioBeat {
  source: TempoSource
  /** Pitch-adjusted. */
  bpm: number
  bar: number
  /** 1–4. */
  beatInBar: number
  pitchPercent: number
  stale: boolean
}

export interface ScenarioLink {
  /** The mock drops every session this long after the first one connects, and refuses new ones. */
  dropAfterMs: number | null
}

export interface ScenarioState {
  name: ScenarioName
  home: Home
  lights: Light[]
  looks: Look[]
  zones: Zone[]
  running: RunningZone[]
  overlays: Overlay[]
  attention: AttentionItem[]
  beat: ScenarioBeat
  decks: Deck[]
  inputs: Inputs
  signals: Signal[]
  previewOnly: boolean
  link: ScenarioLink
}

const SEVERITY: Record<AttentionItem['severity'], number> = { high: 0, normal: 1 }

/** §9.5: "Ordered by severity then time", the newest first, as M1's feed sorts (decision 7). */
export function orderAttention(items: AttentionItem[]): AttentionItem[] {
  return [...items].sort(
    (a, b) => SEVERITY[a.severity] - SEVERITY[b.severity] || Date.parse(b.since) - Date.parse(a.since),
  )
}

const SECOND = 1000
const MINUTE = 60 * SECOND
/** The doorbell's entity, as the Inputs render names it. */
const DOORBELL = 'binary_sensor.front_door_ding'

/** The ISO time `ms` from now, as the API sends times. */
const after = (now: Date, ms: number) => new Date(now.getTime() + ms).toISOString()
const hhmm = (iso: string) => formatTime(new Date(iso))
const joinNames = (names: string[]) =>
  names.length < 2 ? names.join('') : `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`

function lightOf(state: ScenarioState, id: Id): Light {
  const light = state.lights.find((candidate) => candidate.id === id)
  if (light === undefined) throw new Error(`No light ${id} in the fixtures`)
  return light
}

function setLight(state: ScenarioState, id: Id, patch: Partial<Light>): void {
  Object.assign(lightOf(state, id), patch)
}

function zoneOf(state: ScenarioState, id: Id): Zone {
  const zone = state.zones.find((candidate) => candidate.id === id)
  if (zone === undefined) throw new Error(`No zone ${id} in the fixtures`)
  return zone
}

function runningOf(state: ScenarioState, zoneId: Id): RunningZone {
  const zone = state.running.find((candidate) => candidate.zoneId === zoneId)
  if (zone === undefined) throw new Error(`Zone ${zoneId} is not running`)
  return zone
}

/** Starts a look on a zone. Its lights stream from `since`. */
function run(
  state: ScenarioState,
  zoneId: Id,
  lookId: Id,
  since: string,
  brightness: number,
  lights: Id[] = zoneOf(state, zoneId).lights,
  extra: Partial<RunningZone> = {},
): RunningZone {
  const zone: RunningZone = {
    zoneId,
    lookId,
    lookName: lookName(lookId),
    since,
    brightness,
    lights,
    covers: coversOf(state.home, state.lights, lights),
    state: 'running',
    fps: { actual: 60, target: 60 },
    ...extra,
  }
  for (const id of lights) setLight(state, id, { status: 'streaming', statusSince: since, power: true, sendFps: 60 })
  state.running.push(zone)
  return zone
}

// ── Attention, in M1's words where M1 raises the kind (decision 8) ─────────────────────────

function lightOffline(state: ScenarioState, id: Id): AttentionItem {
  const light = lightOf(state, id)
  return {
    id: `light-offline:${id}`,
    severity: 'normal',
    kind: 'light-offline',
    subject: { type: 'light', id },
    title: `${light.name} offline`,
    detail: `${light.name} offline since ${hhmm(light.statusSince)}. It rejoins by itself when it's back.`,
    since: light.statusSince,
    actions: ['details'],
  }
}

function zoneCrashed(state: ScenarioState, zone: RunningZone): AttentionItem {
  const name = zoneOf(state, zone.zoneId).name
  const lights = name.toLowerCase().endsWith('lights') ? `${name} are` : `The ${name} lights are`
  const error = zone.error
  if (!error) throw new Error(`Zone ${zone.zoneId} has no error`)
  return {
    id: `zone-crashed:${zone.zoneId}`,
    severity: 'high',
    kind: 'zone-crashed',
    subject: { type: 'zone', id: zone.zoneId },
    title: `${zone.lookName} crashed`,
    detail: `${lights} holding the last frame. ${error.layer}: ${error.message}`,
    since: error.at,
    actions: ['restart', 'details'],
  }
}

function zoneSlow(state: ScenarioState, zone: RunningZone, since: string): AttentionItem {
  return {
    id: `zone-slow:${zone.zoneId}`,
    severity: 'normal',
    kind: 'zone-slow',
    subject: { type: 'zone', id: zone.zoneId },
    title: `${zoneOf(state, zone.zoneId).name} is running slow`,
    detail: `${zone.lookName} can't keep up with ${zone.fps?.target ?? 60} fps, so it runs at a lower frame rate.`,
    since,
    actions: ['details'],
  }
}

// M1 can't raise these two yet: they use the State-Problems render's words.
function homeAssistantDisconnected(state: ScenarioState): AttentionItem {
  const ha = state.inputs.homeAssistant
  const waiting = state.looks.filter((look) => look.needs?.includes('home-assistant')).map((look) => look.name)
  return {
    id: 'input-disconnected:home-assistant',
    severity: 'normal',
    kind: 'input-disconnected',
    subject: { type: 'input', id: 'home-assistant' },
    title: 'Home Assistant is disconnected',
    detail: `Since ${hhmm(ha.since)}, retrying every ${ha.retryS ?? 10} s. ${joinNames(waiting)} can't trigger.`,
    since: ha.since,
    actions: ['retry', 'open'],
  }
}

function musicWentQuiet(state: ScenarioState, now: Date): AttentionItem {
  const music = state.inputs.music
  const quietS = Math.round((now.getTime() - Date.parse(music.updatedAt)) / SECOND)
  return {
    id: 'input-stale:music',
    severity: 'normal',
    kind: 'input-stale',
    subject: { type: 'input', id: 'music' },
    title: 'Music Assistant went quiet',
    detail: `No update for ${quietS} s. The tempo fell back to Internal ${formatBpm(state.beat.bpm)}.`,
    since: music.updatedAt,
    actions: ['open'],
  }
}

// ── The hero, and the scenarios built on it ────────────────────────────────────────────────

const SPECTRUM = Array.from({ length: 32 }, (_, band) => Math.round(83 * Math.exp(-band / 10)) / 100)

function heroInputs(now: Date): Inputs {
  return {
    tempo: { source: 'music', lock: 'auto', bpm: 121.8, stale: false },
    prodjlink: {
      state: 'idle',
      interface: 'eth0',
      lastSet: { from: after(now, -4114 * MINUTE), to: after(now, -3959 * MINUTE) },
    },
    music: {
      state: 'connected',
      track: { title: 'Rain', artist: 'Kerri Chandler' },
      group: [roomName('living'), roomName('kitchen')],
      loudness: 0.58,
      lufs: -14,
      spectrum: [...SPECTRUM],
      onsets: { kick: 0.91, snare: 0.12, hihat: 0.44 },
      updatedAt: after(now, -40),
    },
    homeAssistant: {
      state: 'connected',
      url: 'homeassistant.local:8123',
      since: after(now, -1440 * MINUTE),
      retryS: null,
      entities: [
        { id: DOORBELL, state: 'off', since: after(now, -152 * MINUTE) },
        { id: 'input_boolean.bedtime', state: 'off', since: after(now, -1180 * MINUTE) },
        { id: 'media_player.living_room', state: 'playing', since: after(now, -12 * MINUTE) },
        { id: 'sun.sun', state: 'above_horizon', since: after(now, -724 * MINUTE) },
      ],
    },
    sun: { elevation: 2.1, azimuth: 268, sunrise: after(now, -724 * MINUTE), sunset: after(now, 12 * MINUTE) },
  }
}

/** The Inputs render's signals table. `usedBy` holds look ids. */
function heroSignals(): Signal[] {
  return [
    { name: 'beat.phase', value: 0.62, usedBy: ['comets'] },
    { name: 'bar.phase', value: 0.41, usedBy: ['comets'] },
    { name: 'bpm', value: 121.8, usedBy: ['comets'] },
    { name: 'loudness', value: 0.58, usedBy: [] },
    { name: 'spectrum.bass', value: 0.83, usedBy: [] },
    { name: 'onset.kick', value: 0.91, usedBy: [] },
    { name: 'doorbell', value: 'idle', usedBy: ['doorbell'] },
    { name: 'bedtime', value: 'off', usedBy: ['goodnight'] },
    { name: 'sun.elevation', value: 2.1, unit: '°', usedBy: ['homesunset'] },
    { name: 'sun.azimuth', value: 268, unit: '°', usedBy: ['homesunset'] },
    { name: 'time.evening', value: 0.31, usedBy: [] },
  ]
}

function base(name: ScenarioName, now: Date): ScenarioState {
  const home = structuredClone(homeFixture)
  const lights = lightFixtures(after(now, -70 * MINUTE))
  return {
    name,
    home,
    lights,
    looks: structuredClone(lookFixtures),
    zones: zoneFixtures(home, lights),
    running: [],
    overlays: [],
    attention: [],
    beat: { source: 'music', bpm: 121.8, bar: 42, beatInBar: 2, pitchPercent: 0, stale: false },
    decks: [],
    inputs: heroInputs(now),
    signals: heroSignals(),
    previewOnly: false,
    link: { dropAfterMs: null },
  }
}

/** Rope offline since 17:02 and Candle 2 switched off elsewhere at 18:43 (§9.1). */
function heroLights(state: ScenarioState, now: Date): void {
  setLight(state, 'rope', { status: 'offline', statusSince: after(now, -132 * MINUTE), power: null, sendFps: 0 })
  setLight(state, 'candle2', {
    status: 'switched-off',
    statusSince: after(now, -31 * MINUTE),
    power: false,
    sendFps: 0,
  })
}

/** Main.png: the whole home since 18:04, the living room since 19:05 and the office desk since 19:10. */
function hero(state: ScenarioState, now: Date): void {
  const living = zoneOf(state, 'living').lights
  const office = zoneOf(state, 'office').lights
  const taken = new Set([...living, ...office])
  const rest = state.lights.map((light) => light.id).filter((id) => !taken.has(id))
  run(state, HOME_ZONE, 'homesunset', after(now, -70 * MINUTE), 0.85, rest)
  run(state, 'living', 'fireflies', after(now, -9 * MINUTE), 0.7)
  run(state, 'office', 'comets', after(now, -4 * MINUTE), 1)
  heroLights(state, now)
  state.attention = orderAttention([lightOffline(state, 'rope')])
}

/** State-Inputs-Down: the music went quiet 42 s ago, so the tempo fell back to Internal. */
function inputsDown(state: ScenarioState, now: Date): void {
  state.beat = { ...state.beat, source: 'internal', bpm: 118 }
  state.inputs.tempo = { source: 'internal', lock: 'auto', bpm: 118, stale: false }
  state.inputs.music = { ...state.inputs.music, state: 'stale', updatedAt: after(now, -42 * SECOND) }
  state.inputs.homeAssistant = {
    ...state.inputs.homeAssistant,
    state: 'disconnected',
    since: after(now, -12 * MINUTE),
    retryS: 10,
  }
}

const BUILD: Record<ScenarioName, (state: ScenarioState, now: Date) => void> = {
  hero,
  doorbell(state, now) {
    hero(state, now)
    state.overlays = [
      { lookId: 'doorbell', name: lookName('doorbell'), trigger: DOORBELL, endsAt: after(now, 2.4 * SECOND), progress: 0.4 },
    ]
  },
  transition(state, now) {
    hero(state, now)
    Object.assign(runningOf(state, 'living'), {
      lookId: 'embers',
      lookName: lookName('embers'),
      state: 'transition',
      transition: { from: lookName('fireflies'), kind: 'dissolve', progress: 0.62 },
    } satisfies Partial<RunningZone>)
  },
  problems(state, now) {
    inputsDown(state, now)
    const office = zoneOf(state, 'office').lights
    const kitchen = run(state, 'kitchen', 'lava', after(now, -20 * MINUTE), 1, undefined, {
      state: 'crashed',
      fps: null,
      error: { layer: 'Plasma', message: 'raised an error', at: after(now, -2 * MINUTE) },
    })
    const living = run(state, 'living', 'embers', after(now, -24 * MINUTE), 0.7, undefined, {
      state: 'slow',
      fps: { actual: 38, target: 60 },
    })
    const bedroom = zoneOf(state, 'bedroom').lights.filter((id) => !office.includes(id))
    run(state, 'bedroom', 'sunset', after(now, -60 * MINUTE), 0.85, bedroom)
    run(state, 'office', 'comets', after(now, -4 * MINUTE), 1)
    heroLights(state, now)
    state.attention = orderAttention([
      zoneCrashed(state, kitchen),
      zoneSlow(state, living, after(now, -2 * MINUTE)),
      homeAssistantDisconnected(state),
      musicWentQuiet(state, now),
      lightOffline(state, 'rope'),
    ])
  },
  firmware(state, now) {
    run(state, HOME_ZONE, 'firmware', after(now, -10 * MINUTE), 0.9)
    for (const light of state.lights) {
      if (light.builtInEffects.length === 0) setLight(state, light.id, { status: 'streamed-copy' })
      else setLight(state, light.id, { status: 'own-effect', ownEffect: light.builtInEffects[0] })
    }
  },
  'inputs-down'(state, now) {
    hero(state, now)
    inputsDown(state, now)
    state.attention = orderAttention([
      homeAssistantDisconnected(state),
      musicWentQuiet(state, now),
      lightOffline(state, 'rope'),
    ])
  },
  'nothing-running'(state, now) {
    // "Your lights are as they were: 9 on, 10 off." M1 raises no item for a light in no running zone.
    const on = zoneOf(state, 'living').lights.filter((id) => id !== 'rope' && id !== 'tube')
    for (const id of on) setLight(state, id, { power: true })
    setLight(state, 'rope', { status: 'offline', statusSince: after(now, -132 * MINUTE), power: null })
  },
  'no-lights'(state, now) {
    hero(state, now)
    state.home.anchors = []
    for (const light of state.lights) light.shape = null
  },
  reconnecting(state, now) {
    hero(state, now)
    state.link = { dropAfterMs: 1000 }
  },
  'dj-playing'(state, now) {
    hero(state, now)
    const pitch = 1.2
    state.beat = { source: 'prodjlink', bpm: 124 * (1 + pitch / 100), bar: 17, beatInBar: 3, pitchPercent: pitch, stale: false }
    state.decks = [
      { number: 1, player: 'Player 1', state: 'cued', bpm: 126, pitch_percent: 0, master: false },
      { number: 2, player: 'Player 2', state: 'playing', bpm: 124, pitch_percent: pitch, master: true },
      { number: 3, player: 'Player 3', state: 'empty', bpm: null, pitch_percent: 0, master: false },
      { number: 4, player: 'Player 4', state: 'empty', bpm: null, pitch_percent: 0, master: false },
    ]
    state.inputs.tempo = { source: 'prodjlink', lock: 'auto', bpm: state.beat.bpm, stale: false }
    state.inputs.prodjlink = { ...state.inputs.prodjlink, state: 'connected' }
    // "Music Assistant: nothing playing."
    state.inputs.music = {
      ...state.inputs.music,
      state: 'idle',
      track: null,
      loudness: 0,
      spectrum: SPECTRUM.map(() => 0),
      onsets: { kick: 0, snare: 0, hihat: 0 },
    }
  },
  'preview-only'(state, now) {
    hero(state, now)
    state.previewOnly = true
  },
}

/** A new state for the scenario, with its times counted from `now`. */
export function buildScenario(name: ScenarioName, now: Date = new Date()): ScenarioState {
  const state = base(name, now)
  BUILD[name](state, now)
  return state
}
```

- [ ] **Step 7: Run the tests**

```bash
(cd web && npx vitest run src/api/mocks src/design/payload.node.test.ts)
```

Expected: PASS: fixtures 7, scenarios 27, payload 8.

- [ ] **Step 8: Gate and commit**

```bash
git add web/src/api/mocks web/src/design/payload.node.test.ts web/tsconfig.app.json
git commit -m "feat(web): mock fixtures from home.json and looks.json, and the eleven scenarios"
```

---

### Task 9: The mock frame generator

Implements §12.5's "The mock frame generator animates simple versions of the looks so the stage is alive without the engine." No design values: it paints motifs from hues it picks itself, never a colour from the handoff. No renders.

**Files:**
- Create: `web/src/api/mocks/frame-generator.ts`
- Test: `web/src/api/mocks/frame-generator.test.ts`

**Interfaces:**
- Consumes: `Look` and `Id` from `contract.ts`, and `lookFixtures` (Task 8, in the test).
- Produces:
  - `MOTIFS`, the seven motif names, and `type Motif`.
  - `interface MotifSpec { motif: Motif; hue: number; spread: number }`. Hues are degrees.
  - `motifFor(look: Pick<Look, 'id' | 'category'>): MotifSpec`.
  - `paint(out: Uint8Array, count: number, spec: MotifSpec, t: number, beatPhase: number, brightness: number, seed: number): void`. It writes `count` LEDs of RGB into `out` and allocates nothing.

- [ ] **Step 1: Read the spec**

Re-read §12.5's last sentence and §5.4. The generator only has to make the stage move: F2's stage and F5's thumbnails draw the real looks.

- [ ] **Step 2: Write the failing test**

`web/src/api/mocks/frame-generator.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { lookFixtures } from './fixtures'
import { MOTIFS, motifFor, paint, type MotifSpec } from './frame-generator'

const spec = (motif: MotifSpec['motif']): MotifSpec => ({ motif, hue: 30, spread: 40 })

describe('motifFor', () => {
  it('gives every handoff look a motif', () => {
    for (const look of lookFixtures) expect(MOTIFS).toContain(motifFor(look).motif)
  })

  it("uses the look's own motif, else its category's", () => {
    expect(motifFor({ id: 'fireflies', category: 'ambient' }).motif).toBe('twinkle')
    expect(motifFor({ id: 'not-a-look', category: 'tempo' })).toEqual(motifFor({ id: 'another', category: 'tempo' }))
  })
})

describe('paint', () => {
  it.each(MOTIFS)('%s paints the LEDs and moves over time', (motif) => {
    const before = new Uint8Array(30)
    const after = new Uint8Array(30)
    paint(before, 10, spec(motif), 0.3, 0.1, 1, 1)
    paint(after, 10, spec(motif), 1.7, 0.6, 1, 1)
    expect(before.some((value) => value > 0) || after.some((value) => value > 0)).toBe(true)
    expect(after).not.toEqual(before)
  })

  it('paints the same for the same inputs', () => {
    const one = new Uint8Array(9)
    const two = new Uint8Array(9)
    paint(one, 3, spec('ripple'), 2.5, 0.4, 0.8, 7)
    paint(two, 3, spec('ripple'), 2.5, 0.4, 0.8, 7)
    expect(one).toEqual(two)
  })

  it('scales with brightness, and paints black at 0', () => {
    const full = new Uint8Array(30)
    const half = new Uint8Array(30)
    const off = new Uint8Array(30).fill(9)
    paint(full, 10, spec('glow'), 1, 0, 1, 0)
    paint(half, 10, spec('glow'), 1, 0, 0.5, 0)
    paint(off, 10, spec('glow'), 1, 0, 0, 0)
    const total = (out: Uint8Array) => out.reduce((sum, value) => sum + value, 0)
    expect(total(half)).toBeLessThan(total(full))
    expect(total(off)).toBe(0)
  })

  it('follows the beat: a pulse is brightest on it', () => {
    const on = new Uint8Array(3)
    const late = new Uint8Array(3)
    paint(on, 1, spec('pulse'), 1, 0, 1, 0)
    paint(late, 1, spec('pulse'), 1, 0.9, 1, 0)
    expect(Math.max(...on)).toBeGreaterThan(Math.max(...late))
  })

  it('writes only its own LEDs, and takes a light with none', () => {
    const out = new Uint8Array(12)
    paint(out, 2, spec('gradient'), 1, 0, 1, 0)
    expect([...out.slice(6)]).toEqual([0, 0, 0, 0, 0, 0])
    expect(() => paint(new Uint8Array(0), 0, spec('chase'), 1, 0, 1, 0)).not.toThrow()
  })
})
```

- [ ] **Step 3: Run it to see it fail**

Run: `(cd web && npx vitest run src/api/mocks/frame-generator.test.ts)`
Expected: FAIL, with `Failed to load url ./frame-generator`.

- [ ] **Step 4: Write `frame-generator.ts`**

```ts
// Simple moving versions of the looks for the mock's frames (spec §12.5). They only keep the stage
// alive without the engine: the hues are picked here and are no design value, and F2's stage and F5's
// thumbnails draw the real looks. paint() runs 60 times a second for every light, so it allocates
// nothing.
import type { Id, Look } from '../contract'

export const MOTIFS = ['gradient', 'twinkle', 'chase', 'pulse', 'flicker', 'ripple', 'glow'] as const
export type Motif = (typeof MOTIFS)[number]

export interface MotifSpec {
  motif: Motif
  /** Degrees. */
  hue: number
  /** How far the hue wanders along the light, in degrees. */
  spread: number
}

const BY_CATEGORY: Record<Look['category'], MotifSpec> = {
  ambient: { motif: 'glow', hue: 30, spread: 40 },
  tempo: { motif: 'chase', hue: 190, spread: 60 },
  audio: { motif: 'pulse', hue: 280, spread: 50 },
  home: { motif: 'gradient', hue: 25, spread: 30 },
  firmware: { motif: 'flicker', hue: 35, spread: 20 },
}

// The looks the scenarios run get a motif of their own.
const BY_LOOK: Partial<Record<Id, MotifSpec>> = {
  homesunset: { motif: 'gradient', hue: 18, spread: 35 },
  sunset: { motif: 'gradient', hue: 28, spread: 40 },
  fireflies: { motif: 'twinkle', hue: 60, spread: 25 },
  comets: { motif: 'chase', hue: 195, spread: 40 },
  embers: { motif: 'flicker', hue: 14, spread: 18 },
  lava: { motif: 'ripple', hue: 8, spread: 30 },
  doorbell: { motif: 'ripple', hue: 205, spread: 20 },
  goodnight: { motif: 'glow', hue: 240, spread: 15 },
}

export function motifFor(look: Pick<Look, 'id' | 'category'>): MotifSpec {
  return BY_LOOK[look.id ?? ''] ?? BY_CATEGORY[look.category]
}

const clamp01 = (value: number) => Math.min(1, Math.max(0, value))

/** HSV to RGB, written into out[at..at+2]. */
function writeHsv(out: Uint8Array, at: number, hue: number, saturation: number, value: number): void {
  const h = (((hue % 360) + 360) % 360) / 60
  const chroma = value * saturation
  const x = chroma * (1 - Math.abs((h % 2) - 1))
  const m = value - chroma
  let r = 0
  let g = 0
  let b = 0
  if (h < 1) {
    r = chroma
    g = x
  } else if (h < 2) {
    r = x
    g = chroma
  } else if (h < 3) {
    g = chroma
    b = x
  } else if (h < 4) {
    g = x
    b = chroma
  } else if (h < 5) {
    r = x
    b = chroma
  } else {
    r = chroma
    b = x
  }
  out[at] = Math.round((r + m) * 255)
  out[at + 1] = Math.round((g + m) * 255)
  out[at + 2] = Math.round((b + m) * 255)
}

/**
 * Paints `count` LEDs of `spec` into `out` at `t` seconds. `beatPhase` is 0–1 through the beat,
 * `brightness` 0–1, and `seed` sets one light apart from another running the same look.
 */
export function paint(
  out: Uint8Array,
  count: number,
  spec: MotifSpec,
  t: number,
  beatPhase: number,
  brightness: number,
  seed: number,
): void {
  const onBeat = 1 - beatPhase
  for (let i = 0; i < count; i++) {
    const x = count > 1 ? i / (count - 1) : 0.5
    let hue = spec.hue
    let value = 1
    switch (spec.motif) {
      case 'gradient':
        hue += spec.spread * x + 8 * Math.sin(t * 0.2 + seed)
        value = 0.75 + 0.25 * Math.sin(t * 0.5 + x * 3)
        break
      case 'twinkle':
        value = Math.max(0, Math.sin(t * 1.7 + i * 2.39 + seed * 7.1)) ** 6
        break
      case 'chase': {
        const head = (t * 0.25 + beatPhase * 0.25 + seed * 0.13) % 1
        value = Math.max(0, 1 - Math.abs(x - head) * 6)
        hue += spec.spread * value
        break
      }
      case 'pulse':
        value = 0.25 + 0.75 * onBeat * onBeat
        hue += spec.spread * x
        break
      case 'flicker':
        value = 0.55 + 0.45 * Math.sin(t * 9.1 + i * 1.3 + seed) * Math.sin(t * 3.7 + i * 0.7)
        hue += spec.spread * 0.5 * Math.sin(t + i)
        break
      case 'ripple': {
        const wave = Math.sin((x - t * 0.6 - seed * 0.1) * Math.PI * 4)
        value = 0.5 + 0.5 * wave
        hue += spec.spread * 0.5 * (1 + wave)
        break
      }
      case 'glow':
        value = 0.6 + 0.4 * Math.sin(t * 0.8 + seed)
        hue += spec.spread * x
        break
    }
    writeHsv(out, i * 3, hue, 0.85, clamp01(value) * clamp01(brightness))
  }
}
```

- [ ] **Step 5: Run the test**

Run: `(cd web && npx vitest run src/api/mocks/frame-generator.test.ts)`
Expected: PASS (13 tests).

- [ ] **Step 6: Gate and commit**

```bash
git add web/src/api/mocks/frame-generator.ts web/src/api/mocks/frame-generator.test.ts
git commit -m "feat(web): a mock frame generator: simple moving motifs for each look"
```

---

### Task 10: The mock server, and MSW over it

Implements §12.5's "MSW handlers and a mock WS in `src/api/mocks/`", §12.3's endpoints and §12.4's channels as the mock plays them, and §11.3's take-over. Decisions 1, 5, 8 and 9. Review focus 3. Renders: none new; the scenarios are Task 8's.

**Files:**
- Modify: `web/package.json`, `web/package-lock.json` (msw)
- Create: `web/src/api/mocks/mock-server.ts`, `web/src/api/mocks/in-memory-socket.ts`, `web/src/api/mocks/handlers.ts`
- Test: `web/src/api/mocks/mock-server.test.ts`, `web/src/api/mocks/msw.test.ts`

**Interfaces:**
- Consumes:
  - `buildScenario`, `ScenarioState`, `ScenarioName` and `orderAttention` (Task 8), and `coversOf` (Task 8).
  - `motifFor`, `paint` and `MotifSpec` (Task 9).
  - `encodeFrame`, `decodeFrame`, `FrameStore` and `FrameVersion` (Task 4).
  - The message types (Task 2), `LiveSocket` and `OpenSocket` (Task 7), and in the tests `LiveClient` (Task 7), `createLiveStore` (Task 6), `BeatClock` (Task 5) and `api` (Task 3).
- Produces, from `mock-server.ts`:
  - `interface MockLink { send(data: string | ArrayBuffer): void; close(): void }`, the server's end of one socket.
  - `interface MockReply { status: number; body?: unknown }`.
  - `interface MockSession { readonly id: number }`, an open socket as the server knows it.
  - `interface MockServerOptions { scenario?; protocol?: 1 | 2; still?: boolean; clock?: () => number; wallClock?: () => number }`. `clock` is monotonic ms (`performance.now()` by default), `wallClock` epoch ms (`Date.now()`).
  - `class MockServer`, with:
    - `state: ScenarioState`;
    - `handle(method, path, body?): MockReply`;
    - `connect(link): MockSession | null`, which is null while it refuses connections;
    - `receive(session, text)`, `disconnect(session)`, `start()` and `stop()`.
  - `snapshotMessages(state, protocol): ServerMessage[]`, what a new connection hears first.
  - `beatMessage(state, elapsedS, serverTime, protocol): BeatV1 | BeatV2`.
  - `statsMessage(state): StatsMessage`.
- Produces, from `in-memory-socket.ts`: `inMemorySockets(server: MockServer): OpenSocket`. Its sockets open on a `setTimeout(0)` and deliver each message in a microtask.
- Produces, from `handlers.ts`: `mockHandlers(server: MockServer, socketUrl: string)`, MSW's handlers: `http.all('*/api/*')` and a `ws.link(socketUrl)` connection handler.

- [ ] **Step 1: Read the spec and the library**

Re-read §12.3, §12.4, §11.3 and decisions 1, 5, 8 and 9. Read `src/dj_ledfx/web/ws.py` (`ws_endpoint`, `_handle_command`, `stats_message`, `_status_poll`) and `router_zones.py` for M1's status codes (201 for created, 204 for off, stop all and deletes) and `detail` messages (`errors.py`).

With context7, check MSW 2's API: `http.all(path, resolver)` with `HttpResponse.json(body, { status })` and `new HttpResponse(null, { status: 204 })`; `ws.link(url)` and its `'connection'` event with `{ client }`, `client.send(data)`, `client.close()` and `client.addEventListener('message' | 'close', …)`; and `setupServer` from `msw/node`, which intercepts Node's global `WebSocket` too.

```bash
(cd web && npm install --save-dev msw@^2.15.0)
```

- [ ] **Step 2: Write the failing tests**

`web/src/api/mocks/mock-server.test.ts`:

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { BeatClock } from '../beat'
import { FrameStore, decodeFrame } from '../frames'
import { LiveClient } from '../live-client'
import { createLiveStore } from '../live-store'
import type { ClientCommand } from '../ws-messages'
import { inMemorySockets } from './in-memory-socket'
import { MockServer, beatMessage, snapshotMessages, type MockServerOptions } from './mock-server'
import { buildScenario } from './scenarios'

const NOW = new Date(2026, 8, 23, 19, 14)
let servers: MockServer[] = []

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(NOW)
})

afterEach(() => {
  for (const server of servers) server.stop()
  servers = []
})

function serve(options: MockServerOptions = {}) {
  const server = new MockServer({ scenario: 'hero', clock: () => Date.now(), wallClock: () => Date.now(), ...options })
  servers.push(server)
  server.start()
  return server
}

/** One socket to the server, recording what it hears. */
function connect(server: MockServer) {
  const heard: (string | ArrayBuffer)[] = []
  let closed = false
  const session = server.connect({ send: (data) => heard.push(data), close: () => (closed = true) })
  let id = 0
  return {
    session,
    heard,
    closed: () => closed,
    json: () => heard.filter((data): data is string => typeof data === 'string').map((text) => JSON.parse(text)),
    binary: () => heard.filter((data): data is ArrayBuffer => data instanceof ArrayBuffer),
    send: (command: Omit<ClientCommand, 'id'> | Record<string, unknown>) => {
      if (session !== null) server.receive(session, JSON.stringify({ ...command, id: ++id }))
    },
    clear: () => heard.splice(0),
  }
}

/** The frames heard, decoded as `version`. */
function decoded(frames: ArrayBuffer[], version: 1 | 2) {
  const store = new FrameStore()
  for (const frame of frames) decodeFrame(frame, version, store, 0)
  return store
}

describe('a connection', () => {
  it('hears the snapshots first, v2 adding decks and inputs', () => {
    expect(connect(serve()).json().map((message) => message.channel)).toEqual([
      'running', 'lights', 'attention', 'transport', 'decks', 'inputs',
    ])
    expect(connect(serve({ protocol: 1 })).json().map((message) => message.channel)).toEqual([
      'running', 'lights', 'attention', 'transport',
    ])
  })

  it('gets v2 frames at 60 fps once it asks with protocol 2, for the streaming lights only', () => {
    const socket = connect(serve())
    socket.clear()
    socket.send({ action: 'subscribe_frames', fps: 60, protocol: 2, streams: ['live', 'preview'] })
    expect(socket.json()).toEqual([{ channel: 'ack', id: 1, action: 'subscribe_frames', protocol: 2, fps: 60 }])
    vi.advanceTimersByTime(1000)
    const frames = decoded(socket.binary(), 2)
    expect(frames.malformed).toBe(0)
    expect(frames.live.size).toBe(17)
    expect(frames.live.has('rope')).toBe(false)
    expect(frames.live.has('candle2')).toBe(false)
    const fps = frames.sampleFps()
    expect(fps).toBeGreaterThanOrEqual(59)
    expect(fps).toBeLessThanOrEqual(61)
    expect(frames.preview.size).toBe(0)
  })

  it('speaks as engine M1 with protocol 1: a bare ack, v1 frames at 30 fps, and errors', () => {
    const socket = connect(serve({ protocol: 1 }))
    socket.clear()
    socket.send({ action: 'subscribe_frames', fps: 60, protocol: 2, streams: ['live'] })
    socket.send({ action: 'subscribe_signals' })
    expect(socket.json()).toEqual([
      { channel: 'ack', id: 1, action: 'subscribe_frames' },
      { channel: 'error', id: 2, detail: 'Unknown action: subscribe_signals' },
    ])
    vi.advanceTimersByTime(1000)
    const frames = decoded(socket.binary(), 1)
    expect(frames.malformed).toBe(0)
    expect(frames.live.size).toBe(17)
    expect(frames.sampleFps()).toBeLessThanOrEqual(31)
  })

  it('reads bad JSON as an error, as M1 does', () => {
    const server = serve()
    const socket = connect(server)
    socket.clear()
    if (socket.session !== null) server.receive(socket.session, '{"action":')
    expect(socket.json()).toEqual([{ channel: 'error', detail: 'Invalid JSON' }])
  })

  it('sends the beat at the rate asked, moving at the tempo', () => {
    const socket = connect(serve())
    socket.clear()
    socket.send({ action: 'subscribe_beat', fps: 30 })
    vi.advanceTimersByTime(1000)
    const beats = socket.json().filter((message) => message.channel === 'beat')
    expect(beats.length).toBeGreaterThanOrEqual(29)
    expect(beats.length).toBeLessThanOrEqual(31)
    const [first, last] = [beats[0], beats[beats.length - 1]]
    expect(first).toMatchObject({ source: 'music', bpm: 121.8, bar: 42, beat_in_bar: 2, stale: false })
    expect(first.beat_phase).toBeCloseTo(0.25, 1)
    const position = (beat: typeof first) => (beat.bar - 1) * 4 + (beat.beat_in_bar - 1) + beat.beat_phase
    expect(position(last) - position(first)).toBeCloseTo(((last.server_time - first.server_time) * 121.8) / 60, 2)
  })

  it('holds the beat for ?still: one beat after the ack, then none', () => {
    const socket = connect(serve({ still: true }))
    socket.clear()
    socket.send({ action: 'subscribe_beat', fps: 30 })
    vi.advanceTimersByTime(2000)
    expect(socket.json().filter((message) => message.channel === 'beat')).toHaveLength(1)
  })

  it('sends stats every second, and signals at 10 Hz once asked', () => {
    const socket = connect(serve())
    socket.clear()
    socket.send({ action: 'subscribe_signals', names: ['loudness'] })
    vi.advanceTimersByTime(1010)
    const channels = socket.json().map((message) => message.channel)
    expect(channels.filter((channel) => channel === 'stats')).toHaveLength(1)
    const signals = socket.json().filter((message) => message.channel === 'signals')
    expect(signals.length).toBeGreaterThanOrEqual(9)
    expect(Object.keys(signals[0].values)).toEqual(['loudness'])
  })

  it("drops every session after the scenario's dropAfterMs, and refuses new ones", () => {
    const server = serve({ scenario: 'reconnecting' })
    const socket = connect(server)
    vi.advanceTimersByTime(999)
    expect(socket.closed()).toBe(false)
    vi.advanceTimersByTime(20)
    expect(socket.closed()).toBe(true)
    expect(connect(server).session).toBeNull()
  })
})

describe('the REST API', () => {
  it('starts a look with take-over, and pushes running and lights', () => {
    const server = serve()
    const socket = connect(server)
    socket.clear()
    const reply = server.handle('POST', '/api/zones/bedroom/start', { lookId: 'sunset' })
    expect(reply.status).toBe(200)
    const body = reply.body as { zoneId: string; takeOvers: { zoneId: string; lights: string[]; stopped: boolean }[] }
    expect(body.zoneId).toBe('bedroom')
    expect(body.takeOvers).toEqual([
      expect.objectContaining({ zoneId: 'home', lights: ['bedl', 'bedr'], stopped: false }),
      expect.objectContaining({ zoneId: 'office', lights: ['deskl', 'deskr', 'pc'], stopped: true }),
    ])
    expect(server.state.running.map((zone) => zone.zoneId)).toEqual(['home', 'living', 'bedroom'])
    expect(server.state.running[0].lights).not.toContain('bedl')
    expect(socket.json().map((message) => message.channel)).toEqual(['running', 'lights'])
  })

  it('turns a zone off again and again, and says 404 for a zone it does not know', () => {
    const server = serve()
    expect(server.handle('POST', '/api/zones/living/off').status).toBe(204)
    expect(server.state.running.map((zone) => zone.zoneId)).toEqual(['home', 'office'])
    expect(server.state.lights.find((light) => light.id === 'rcl')?.status).toBe('idle')
    expect(server.handle('POST', '/api/zones/living/off').status).toBe(204)
    expect(server.handle('POST', '/api/zones/nope/off')).toEqual({ status: 404, body: { detail: "No zone 'nope'" } })
  })

  it('refuses to change a built-in look, and saves a new one', () => {
    const server = serve()
    const fireflies = server.state.looks.find((look) => look.id === 'fireflies')
    expect(server.handle('PUT', '/api/looks/fireflies', fireflies).status).toBe(409)
    const saved = server.handle('POST', '/api/looks', { ...fireflies, name: 'Mine', derivedFrom: 'fireflies' })
    expect(saved.status).toBe(201)
    expect(saved.body).toMatchObject({ name: 'Mine', builtIn: false, derivedFrom: 'fireflies' })
    expect(server.handle('GET', `/api/looks/${(saved.body as { id: string }).id}`).status).toBe(200)
  })

  it("streams a preview on the preview stream only, and leaves the lights alone", () => {
    const server = serve()
    const socket = connect(server)
    socket.send({ action: 'subscribe_frames', fps: 60, protocol: 2, streams: ['live', 'preview'] })
    const lights = JSON.stringify(server.state.lights)
    const reply = server.handle('POST', '/api/preview', { zoneId: 'living', lookId: 'embers' })
    expect(reply.body).toEqual({ previewId: expect.any(String) })
    vi.advanceTimersByTime(500)
    const frames = decoded(socket.binary(), 2)
    expect(frames.preview.size).toBe(server.state.zones.find((zone) => zone.id === 'living')?.lights.length)
    expect(JSON.stringify(server.state.lights)).toBe(lights)
    const id = (reply.body as { previewId: string }).previewId
    expect(server.handle('DELETE', `/api/preview/${id}`).status).toBe(204)
    socket.clear()
    vi.advanceTimersByTime(500)
    expect(decoded(socket.binary(), 2).preview.size).toBe(0)
  })

  it('puts preview only on through the config, and pushes transport', () => {
    const server = serve()
    const socket = connect(server)
    socket.clear()
    expect(server.handle('PUT', '/api/config', { engine: { preview_only: true } }).status).toBe(200)
    expect(socket.json()).toEqual([{ channel: 'transport', state: 'simulating' }])
    expect(server.handle('PUT', '/api/config', { engine: { preview_only: 'yes' } }).status).toBe(400)
  })

  it('answers what it does not serve with 404 Not Found', () => {
    expect(serve().handle('GET', '/api/nope')).toEqual({ status: 404, body: { detail: 'Not Found' } })
  })
})

describe('the messages', () => {
  it("sends today's beat as M1 does: bpm 0 with no DJ, Player 2's beat with one", () => {
    const hero = buildScenario('hero', NOW)
    expect(beatMessage(hero, 1, 0, 1)).toMatchObject({ bpm: 0, is_playing: false, deck_number: null })
    const dj = buildScenario('dj-playing', NOW)
    expect(beatMessage(dj, 0, 0, 1)).toMatchObject({ is_playing: true, beat_pos: 3, deck_number: 2, deck_name: 'Player 2' })
  })

  it('snapshots the transport as simulating while preview only is on', () => {
    const messages = snapshotMessages(buildScenario('preview-only', NOW), 2)
    expect(messages).toContainEqual({ channel: 'transport', state: 'simulating' })
  })
})

describe('the in-memory socket', () => {
  it('runs a LiveClient against the mock, with no MSW', async () => {
    const server = serve()
    const store = createLiveStore()
    const frames = new FrameStore()
    const client = new LiveClient({
      url: 'mock',
      store,
      frames,
      beatClock: new BeatClock(),
      openSocket: inMemorySockets(server),
      clock: () => Date.now() / 1000,
    })
    client.start()
    // Async: the socket delivers in microtasks, which run between the timers.
    await vi.advanceTimersByTimeAsync(2000)
    expect(store.getState().connection).toEqual({ status: 'live', fps: 60 })
    expect(store.getState().attention).toHaveLength(1)
    expect(frames.live.size).toBe(17)
    client.stop()
  })
})
```

`web/src/api/mocks/msw.test.ts`:

```ts
// @vitest-environment node
import { setupServer } from 'msw/node'
import { afterEach, describe, expect, it } from 'vitest'
import { BeatClock } from '../beat'
import { FrameStore } from '../frames'
import { LiveClient } from '../live-client'
import { createLiveStore } from '../live-store'
import { api } from '../rest'
import { mockHandlers } from './handlers'
import { MockServer } from './mock-server'

const SOCKET_URL = 'ws://localhost/ws'
let stop: () => void = () => {}

afterEach(() => stop())

function serve(protocol: 1 | 2) {
  const server = new MockServer({ scenario: 'hero', protocol })
  const msw = setupServer(...mockHandlers(server, SOCKET_URL))
  msw.listen({ onUnhandledRequest: 'error' })
  server.start()
  const store = createLiveStore()
  const frames = new FrameStore()
  const client = new LiveClient({ url: SOCKET_URL, store, frames, beatClock: new BeatClock() })
  client.start()
  stop = () => {
    client.stop()
    server.stop()
    msw.close()
  }
  return { store, frames, client }
}

describe('MSW over the mock server', () => {
  it('serves the REST API through fetch', async () => {
    serve(2)
    const running = await api.running()
    expect(running.zones.map((zone) => zone.zoneId)).toEqual(['home', 'living', 'office'])
    await expect(api.look('nope')).rejects.toMatchObject({ status: 404 })
  })

  it('speaks §12.4 to a LiveClient: snapshots, v2 frames and the beat', async () => {
    const { store, frames } = serve(2)
    await expect.poll(() => frames.live.size, { timeout: 3000 }).toBe(17)
    expect(store.getState().attention).toHaveLength(1)
    expect(store.getState().inputs?.music.state).toBe('connected')
    await expect.poll(() => store.getState().beat?.source, { timeout: 3000 }).toBe('music')
    expect(store.getState().beat?.bar).toBeGreaterThanOrEqual(42)
  })

  // Review focus 3: engine M1's protocol.
  it("speaks today's protocol to a LiveClient over MSW", async () => {
    const { store, frames, client } = serve(1)
    await expect.poll(() => frames.live.size, { timeout: 3000 }).toBe(17)
    expect(frames.version).toBeGreaterThan(0)
    await expect.poll(() => store.getState().beat?.source, { timeout: 3000 }).toBe('prodjlink')
    expect(store.getState().beat).toMatchObject({ bar: null, bpm: 0, playing: false })
    expect(store.getState().decks).toBeNull()
    expect(store.getState().inputs).toBeNull()
    expect(client.malformedJson).toBe(0)
  })
})
```

- [ ] **Step 3: Run them to see them fail**

Run: `(cd web && npx vitest run src/api/mocks/mock-server.test.ts src/api/mocks/msw.test.ts)`
Expected: FAIL, with `Failed to load url ./mock-server` and `./handlers`.

- [ ] **Step 4: Write `mock-server.ts`**

```ts
// A pretend server playing one scenario (spec §12.5): §12.3's REST API, §12.4's channels, and frames
// from the frame generator. MSW puts it behind fetch and WebSocket in dev and in the mock build
// (handlers.ts); tests reach it through an in-memory socket. With `protocol: 1` it speaks as engine
// M1 does today: a bare ack, the v1 beat, v1 frames at 30 fps, an error for any other command, and
// no decks or inputs (decision 9).
import type {
  AnchorInput, CreateGroup, FrameStream, HomeUpdate, Id, Light, LightUpdate, Look, Placement, PlacementState, PreviewRequest,
  RunningZone, StartRequest, SubZoneInput, TakeOver, UpdateGroup,
} from '../contract'
import { encodeFrame, type FrameVersion } from '../frames'
import type { BeatV1, BeatV2, ServerMessage, StatsMessage } from '../ws-messages'
import { coversOf } from './fixtures'
import { motifFor, paint, type MotifSpec } from './frame-generator'
import { buildScenario, type ScenarioName, type ScenarioState } from './scenarios'

const FRAME_MS = 1000 / 60
const TICK_MS = 16
const STATS_MS = 1000
const STATUS_MS = 10_000
const SIGNALS_MS = 100
/** After a stall longer than this (a hidden tab), frames pick up from now rather than catch up. */
const STALL_MS = 100

export interface MockLink {
  send(data: string | ArrayBuffer): void
  close(): void
}

export interface MockReply {
  status: number
  body?: unknown
}

export interface MockSession {
  readonly id: number
}

export interface MockServerOptions {
  scenario?: ScenarioName
  /** 2 speaks §12.4. 1 speaks engine M1's protocol (decision 9). */
  protocol?: 1 | 2
  /** ?still: one beat message after subscribe_beat, then none. */
  still?: boolean
  /** Monotonic ms. */
  clock?: () => number
  /** Epoch ms: the API's times and the beat's server_time. */
  wallClock?: () => number
}

interface Session extends MockSession {
  link: MockLink
  version: FrameVersion | null
  /** Send every nth frame: 1 for 60 fps, 2 for 30. */
  frameEvery: number
  streams: ReadonlySet<FrameStream>
  lights: ReadonlySet<Id> | null
  beatMs: number | null
  nextBeatAt: number
  signals: string[] | null
}

/** A light the mock streams, and the buffer it paints into. */
interface Painted {
  id: Id
  spec: MotifSpec
  brightness: number
  /** A crashed zone holds its last frame. */
  frozen: boolean
  seed: number
  rgb: Uint8Array
}

const STREAMING: ReadonlySet<Light['status']> = new Set(['streaming', 'streamed-copy'])

const ok = (body: unknown): MockReply => ({ status: 200, body })
const created = (body: unknown): MockReply => ({ status: 201, body })
const noContent: MockReply = { status: 204 }
const notFound = (detail = 'Not Found'): MockReply => ({ status: 404, body: { detail } })
const badRequest = (detail: string): MockReply => ({ status: 400, body: { detail } })
const BUILT_IN = 'Built-in looks are never changed; save an edit as a new look instead.'

function lightUpdate(light: Light): LightUpdate {
  return {
    id: light.id,
    status: light.status,
    statusSince: light.statusSince,
    ownEffect: light.ownEffect,
    power: light.power,
    colour: light.colour,
  }
}

type Pushed = 'running' | 'lights' | 'attention' | 'transport'

/** What a new connection hears first: M1's four snapshots, and in v2 the decks and inputs too. */
export function snapshotMessages(state: ScenarioState, protocol: 1 | 2): ServerMessage[] {
  const messages: ServerMessage[] = [
    { channel: 'running', zones: state.running, overlays: state.overlays },
    { channel: 'lights', lights: state.lights.map(lightUpdate) },
    { channel: 'attention', items: state.attention },
    { channel: 'transport', state: state.previewOnly ? 'simulating' : 'playing' },
  ]
  if (protocol === 2) messages.push({ channel: 'decks', decks: state.decks }, { channel: 'inputs', inputs: state.inputs })
  return messages
}

/** Beats since bar 1's downbeat, `elapsedS` after the scenario began a quarter into its beat. */
function position(state: Pick<ScenarioState, 'beat'>, elapsedS: number): number {
  const { beat } = state
  const start = (beat.bar - 1) * 4 + (beat.beatInBar - 1) + 0.25
  return beat.stale || beat.bpm <= 0 ? start : start + (elapsedS * beat.bpm) / 60
}

/** The beat message. M1 (protocol 1) only has Pro DJ Link: with no DJ it sends bpm 0, stopped. */
export function beatMessage(
  state: Pick<ScenarioState, 'beat' | 'decks'>,
  elapsedS: number,
  serverTime: number,
  protocol: 1 | 2,
): BeatV1 | BeatV2 {
  const { beat } = state
  const at = position(state, elapsedS)
  const withinBar = at % 4
  if (protocol === 1) {
    if (beat.source !== 'prodjlink') {
      return {
        channel: 'beat', bpm: 0, beat_phase: 0, bar_phase: 0, is_playing: false, beat_pos: 1,
        pitch_percent: 0, deck_number: null, deck_name: null,
      }
    }
    const master = state.decks.find((deck) => deck.master)
    return {
      channel: 'beat',
      bpm: beat.bpm,
      beat_phase: withinBar % 1,
      bar_phase: withinBar / 4,
      is_playing: !beat.stale && beat.bpm > 0,
      beat_pos: Math.floor(withinBar) + 1,
      pitch_percent: beat.pitchPercent,
      deck_number: master?.number ?? null,
      deck_name: master?.player ?? null,
    }
  }
  return {
    channel: 'beat',
    bpm: beat.bpm,
    beat_phase: withinBar % 1,
    bar_phase: withinBar / 4,
    bar: Math.floor(at / 4) + 1,
    beat_in_bar: Math.floor(withinBar) + 1,
    pitch_percent: beat.pitchPercent,
    source: beat.source,
    stale: beat.stale,
    server_time: serverTime,
  }
}

export function statsMessage(state: ScenarioState): StatsMessage {
  return {
    channel: 'stats',
    devices: state.lights.map((light) => ({
      id: light.id,
      name: light.name,
      send_fps: light.sendFps,
      latency_ms: light.latency.measuredMs ?? 0,
      frames_dropped: 0,
      dropped_pct: light.droppedPct,
      connected: light.status !== 'offline',
      status: light.status === 'offline' ? 'offline' : 'online',
    })),
  }
}

type Route = [method: string, pattern: RegExp, handler: (params: string[], body: unknown) => MockReply]

export class MockServer {
  readonly state: ScenarioState
  private readonly protocol: 1 | 2
  private readonly still: boolean
  private readonly clock: () => number
  private readonly wallClock: () => number
  private readonly startedAt: number
  private sessions: Session[] = []
  private nextSessionId = 0
  private nextId = 0
  private timer: ReturnType<typeof setInterval> | null = null
  private live: Painted[] = []
  private preview: { id: Id; lights: Painted[] } | null = null
  private readonly seqs = new Map<string, number>()
  /** When each light's placement was confirmed; the seed's confirmed lights have no time. */
  private readonly confirmedAt = new Map<Id, string>()
  private frameCount = 0
  private nextFrameAt: number
  private nextStatsAt: number
  private nextStatusAt: number
  private nextSignalsAt: number
  private firstConnectAt: number | null = null
  private refusing = false

  constructor(options: MockServerOptions = {}) {
    this.protocol = options.protocol ?? 2
    this.still = options.still ?? false
    this.clock = options.clock ?? (() => performance.now())
    this.wallClock = options.wallClock ?? (() => Date.now())
    this.state = buildScenario(options.scenario ?? 'hero', new Date(this.wallClock()))
    this.startedAt = this.clock()
    this.nextFrameAt = this.startedAt
    this.nextStatsAt = this.startedAt + STATS_MS
    this.nextStatusAt = this.startedAt + STATUS_MS
    this.nextSignalsAt = this.startedAt
    this.plan()
  }

  start(): void {
    this.timer ??= setInterval(() => this.tick(), TICK_MS)
  }

  stop(): void {
    if (this.timer !== null) clearInterval(this.timer)
    this.timer = null
  }

  // ── The socket ───────────────────────────────────────────────────────────────────────────

  /** A new connection hears the snapshots at once. Null while the scenario refuses connections. */
  connect(link: MockLink): MockSession | null {
    if (this.refusing) return null
    const session: Session = {
      id: ++this.nextSessionId,
      link,
      version: null,
      frameEvery: 1,
      streams: new Set(),
      lights: null,
      beatMs: null,
      nextBeatAt: 0,
      signals: null,
    }
    this.sessions.push(session)
    this.firstConnectAt ??= this.clock()
    for (const message of snapshotMessages(this.state, this.protocol)) this.sendJson(session, message)
    return session
  }

  disconnect(handle: MockSession): void {
    this.sessions = this.sessions.filter((session) => session.id !== handle.id)
  }

  receive(handle: MockSession, text: string): void {
    const session = this.sessions.find((candidate) => candidate.id === handle.id)
    if (session === undefined) return
    let command: Record<string, unknown>
    try {
      const parsed: unknown = JSON.parse(text)
      if (typeof parsed !== 'object' || parsed === null) throw new Error('not an object')
      command = parsed as Record<string, unknown>
    } catch {
      this.sendJson(session, { channel: 'error', detail: 'Invalid JSON' })
      return
    }
    const id = typeof command.id === 'number' ? command.id : null
    const action = String(command.action)
    const fps = typeof command.fps === 'number' ? command.fps : 10
    if (action === 'subscribe_beat') {
      session.beatMs = 1000 / Math.min(Math.max(fps, 1), 30)
      session.nextBeatAt = this.clock()
      this.ack(session, id, action)
      if (this.still) this.sendJson(session, this.beat(this.clock()))
      return
    }
    if (action === 'subscribe_frames') {
      const v2 = this.protocol === 2 && command.protocol === 2
      const granted = Math.min(Math.max(fps, 1), v2 ? 60 : 30)
      const wanted = v2 ? command.lights : command.devices
      session.version = v2 ? 2 : 1
      session.frameEvery = Math.max(1, Math.round(60 / granted))
      session.streams = new Set(v2 && Array.isArray(command.streams) ? (command.streams as FrameStream[]) : ['live'])
      session.lights = Array.isArray(wanted) && wanted.length > 0 ? new Set(wanted as Id[]) : null
      this.ack(session, id, action, v2 ? { protocol: 2, fps: granted } : {})
      return
    }
    if (this.protocol === 2 && action === 'subscribe_signals') {
      session.signals = Array.isArray(command.names) ? (command.names as string[]) : []
      this.ack(session, id, action)
      return
    }
    if (this.protocol === 2 && (action === 'subscribe_fx' || action === 'tap')) {
      this.ack(session, id, action)
      return
    }
    this.sendJson(session, { channel: 'error', id, detail: `Unknown action: ${action}` })
  }

  private ack(session: Session, id: number | null, action: string, extra: object = {}): void {
    this.sendJson(session, { channel: 'ack', id, action, ...extra })
  }

  private sendJson(session: Session, message: object): void {
    session.link.send(JSON.stringify(message))
  }

  private broadcast(message: object): void {
    const text = JSON.stringify(message)
    for (const session of this.sessions) session.link.send(text)
  }

  private isoNow(): string {
    return new Date(this.wallClock()).toISOString()
  }

  private beat(now: number): BeatV1 | BeatV2 {
    const elapsedS = this.still ? 0 : (now - this.startedAt) / 1000
    return beatMessage(this.state, elapsedS, this.wallClock() / 1000, this.protocol)
  }

  private tick(): void {
    const now = this.clock()
    const dropAfter = this.state.link.dropAfterMs
    if (!this.refusing && dropAfter !== null && this.firstConnectAt !== null && now - this.firstConnectAt >= dropAfter) {
      this.refusing = true
      for (const session of this.sessions) session.link.close()
      this.sessions = []
    }
    if (now - this.nextFrameAt > STALL_MS) this.nextFrameAt = now
    while (now >= this.nextFrameAt) {
      this.frame(now)
      this.nextFrameAt += FRAME_MS
    }
    for (const session of this.sessions) {
      if (session.beatMs === null || this.still || now < session.nextBeatAt) continue
      this.sendJson(session, this.beat(now))
      session.nextBeatAt = Math.max(session.nextBeatAt + session.beatMs, now - session.beatMs)
    }
    if (now >= this.nextSignalsAt) {
      this.nextSignalsAt += SIGNALS_MS
      for (const session of this.sessions) if (session.signals !== null) this.sendJson(session, this.signals(now, session.signals))
    }
    if (now >= this.nextStatsAt) {
      this.nextStatsAt += STATS_MS
      this.broadcast(statsMessage(this.state))
    }
    if (now >= this.nextStatusAt) {
      this.nextStatusAt += STATUS_MS
      this.broadcast({
        channel: 'status',
        ok: true,
        device_count: this.state.lights.length,
        avg_render_ms: 1.2,
        transport: this.state.previewOnly ? 'simulating' : 'playing',
      })
    }
  }

  private signals(now: number, names: string[]): ServerMessage {
    const at = position(this.state, this.still ? 0 : (now - this.startedAt) / 1000)
    const live: Record<string, number> = { 'beat.phase': at % 1, 'bar.phase': (at % 4) / 4, bpm: this.state.beat.bpm }
    const values = Object.fromEntries(
      this.state.signals
        .filter((signal) => names.length === 0 || names.includes(signal.name))
        .map((signal) => [signal.name, live[signal.name] ?? signal.value]),
    )
    return { channel: 'signals', values }
  }

  // ── Frames ───────────────────────────────────────────────────────────────────────────────

  private painted(id: Id, leds: number, spec: MotifSpec, brightness: number, frozen: boolean): Painted {
    return { id, spec, brightness, frozen, seed: id.length * 1.7 + id.charCodeAt(0) / 50, rgb: new Uint8Array(leds * 3) }
  }

  /** Which lights stream, and how: after every change to what runs or to a light. */
  private plan(): void {
    const lights = new Map(this.state.lights.map((light) => [light.id, light]))
    this.live = []
    for (const zone of this.state.running) {
      const look = this.state.looks.find((candidate) => candidate.id === zone.lookId)
      const spec = motifFor(look ?? { id: zone.lookId, category: 'ambient' })
      for (const id of zone.lights) {
        const light = lights.get(id)
        if (light === undefined || !STREAMING.has(light.status)) continue
        this.live.push(this.painted(id, light.leds, spec, zone.brightness, zone.state === 'crashed'))
      }
    }
  }

  /** One frame: each light painted once, encoded once per protocol, sent to each session that wants it. */
  private frame(now: number): void {
    this.frameCount += 1
    const sessions = this.sessions.filter((session) => session.version !== null)
    if (sessions.length === 0) return
    const t = (now - this.startedAt) / 1000
    const beatPhase = position(this.state, this.still ? 0 : t) % 1
    for (const light of this.live) this.sendFrame(light, 'live', t, beatPhase, sessions)
    for (const light of this.preview?.lights ?? []) this.sendFrame(light, 'preview', t, beatPhase, sessions)
  }

  private sendFrame(light: Painted, stream: FrameStream, t: number, beatPhase: number, sessions: Session[]): void {
    paint(light.rgb, light.rgb.length / 3, light.spec, light.frozen ? 0 : t, beatPhase, light.brightness, light.seed)
    const key = `${stream}:${light.id}`
    const seq = (this.seqs.get(key) ?? 0) + 1
    this.seqs.set(key, seq)
    let v1: ArrayBuffer | null = null
    let v2: ArrayBuffer | null = null
    for (const session of sessions) {
      if (this.frameCount % session.frameEvery !== 0 || !session.streams.has(stream)) continue
      if (session.lights !== null && !session.lights.has(light.id)) continue
      if (session.version === 2) session.link.send((v2 ??= encodeFrame(2, light.id, seq, light.rgb, stream)))
      else session.link.send((v1 ??= encodeFrame(1, light.id, seq, light.rgb)))
    }
  }

  // ── REST ─────────────────────────────────────────────────────────────────────────────────

  /** One request. `path` may carry a query, which is ignored. */
  handle(method: string, path: string, body?: unknown): MockReply {
    const pathname = path.split('?')[0]
    for (const [verb, pattern, handler] of this.routes) {
      if (verb !== method) continue
      const match = pattern.exec(pathname)
      if (match !== null) return handler(match.slice(1).map(decodeURIComponent), body)
    }
    return notFound()
  }

  private readonly routes: Route[] = [
    // Engine M1
    ['GET', /^\/api\/looks$/, () => ok(this.state.looks)],
    ['POST', /^\/api\/looks$/, (_, body) => this.saveLook(body as Look)],
    ['GET', /^\/api\/looks\/([^/]+)$/, ([id]) => this.withLook(id, (look) => ok(look))],
    ['PUT', /^\/api\/looks\/([^/]+)$/, ([id], body) => this.updateLook(id, body as Look)],
    ['DELETE', /^\/api\/looks\/([^/]+)$/, ([id]) => this.deleteLook(id)],
    [
      'PUT',
      /^\/api\/looks\/([^/]+)\/starred$/,
      ([id], body) =>
        this.withLook(id, (look) => {
          look.starred = (body as { starred: boolean }).starred
          return ok(look)
        }),
    ],
    ['GET', /^\/api\/zones$/, () => ok(this.state.zones)],
    ['POST', /^\/api\/zones\/groups$/, (_, body) => this.createGroup(body as CreateGroup)],
    ['PUT', /^\/api\/zones\/groups\/([^/]+)$/, ([id], body) => this.updateGroup(id, body as UpdateGroup)],
    ['DELETE', /^\/api\/zones\/groups\/([^/]+)$/, ([id]) => this.deleteGroup(id)],
    ['GET', /^\/api\/running$/, () => ok({ zones: this.state.running, overlays: this.state.overlays })],
    ['POST', /^\/api\/zones\/([^/]+)\/start$/, ([id], body) => this.start(id, body as StartRequest)],
    [
      'PUT',
      /^\/api\/zones\/([^/]+)\/brightness$/,
      ([id], body) =>
        this.withRunning(id, (zone) => {
          zone.brightness = (body as { value: number }).value
          this.changed('running')
          return ok(zone)
        }),
    ],
    ['POST', /^\/api\/zones\/([^/]+)\/off$/, ([id]) => this.off(id)],
    [
      'POST',
      /^\/api\/zones\/([^/]+)\/restart$/,
      ([id]) =>
        this.withRunning(id, (zone) => {
          Object.assign(zone, { state: 'running', error: null, fps: { actual: 60, target: 60 } } satisfies Partial<RunningZone>)
          this.state.attention = this.state.attention.filter((item) => item.subject.id !== id)
          this.changed('running', 'attention')
          return ok(zone)
        }),
    ],
    ['POST', /^\/api\/running\/stop-all$/, () => this.stopAll()],
    ['GET', /^\/api\/lights$/, () => ok(this.state.lights)],
    ['GET', /^\/api\/attention$/, () => ok(this.state.attention)],
    ['GET', /^\/api\/config$/, () => ok({ engine: { preview_only: this.state.previewOnly } })],
    ['PUT', /^\/api\/config$/, (_, body) => this.putConfig(body)],

    // Pending: engine M2
    ['GET', /^\/api\/home$/, () => ok(this.state.home)],
    ['PUT', /^\/api\/home$/, (_, body) => ok(Object.assign(this.state.home, body as HomeUpdate))],
    [
      'POST',
      /^\/api\/home\/anchors$/,
      (_, body) => {
        const anchor = { ...(body as AnchorInput), id: this.newId('anchor'), confirmed: false }
        this.state.home.anchors.push(anchor)
        return created(anchor)
      },
    ],
    ['PUT', /^\/api\/home\/anchors\/([^/]+)$/, ([id], body) => this.update(this.state.home.anchors, id, body)],
    ['DELETE', /^\/api\/home\/anchors\/([^/]+)$/, ([id]) => this.remove(this.state.home.anchors, id)],
    [
      'POST',
      /^\/api\/home\/subzones$/,
      (_, body) => {
        const subZone = { ...(body as SubZoneInput), id: this.newId('subzone') }
        this.state.home.subZones.push(subZone)
        return created(subZone)
      },
    ],
    ['PUT', /^\/api\/home\/subzones\/([^/]+)$/, ([id], body) => this.update(this.state.home.subZones, id, body)],
    ['DELETE', /^\/api\/home\/subzones\/([^/]+)$/, ([id]) => this.remove(this.state.home.subZones, id)],
    ['POST', /^\/api\/lights\/placement\/guess$/, () => this.guess()],
    [
      'PUT',
      /^\/api\/lights\/([^/]+)\/placement$/,
      ([id], body) =>
        this.withLight(id, (light) => {
          const placement = body as Placement
          Object.assign(light, { shape: placement.shape, ledOrder: placement.ledOrder ?? light.ledOrder, confirmed: false })
          this.confirmedAt.delete(id)
          return ok(this.placementOf(light))
        }),
    ],
    [
      'POST',
      /^\/api\/lights\/([^/]+)\/placement\/confirm$/,
      ([id]) =>
        this.withLight(id, (light) => {
          light.confirmed = true
          this.confirmedAt.set(id, new Date(this.wallClock()).toISOString())
          return ok(this.placementOf(light))
        }),
    ],
    ['POST', /^\/api\/preview$/, (_, body) => this.startPreview(body as PreviewRequest)],
    ['PUT', /^\/api\/preview\/([^/]+)$/, ([id], body) => this.updatePreview(id, body as { look?: Look })],
    ['DELETE', /^\/api\/preview\/([^/]+)$/, ([id]) => this.stopPreview(id)],

    // Pending: engine M3, M6 and M7
    ['GET', /^\/api\/inputs$/, () => ok(this.state.inputs)],
    ['GET', /^\/api\/signals$/, () => ok(this.state.signals)],
  ]

  private newId(kind: string): Id {
    return `${kind}-${++this.nextId}`
  }

  /** Pushes these channels' snapshots to every session, and replans the frames. */
  private changed(...channels: Pushed[]): void {
    for (const message of snapshotMessages(this.state, this.protocol)) {
      if ((channels as string[]).includes(message.channel)) this.broadcast(message)
    }
    this.plan()
  }

  private withLook(id: Id, then: (look: Look) => MockReply): MockReply {
    const look = this.state.looks.find((candidate) => candidate.id === id)
    return look === undefined ? notFound(`No look '${id}'`) : then(look)
  }

  private withLight(id: Id, then: (light: Light) => MockReply): MockReply {
    const light = this.state.lights.find((candidate) => candidate.id === id)
    return light === undefined ? notFound(`No light '${id}'`) : then(light)
  }

  /** A light's placement, as engine M2 answers a placement request (its Spec Ruling 16). */
  private placementOf(light: Light): PlacementState {
    return {
      shape: light.shape ?? null,
      ledOrder: light.ledOrder ?? null,
      confirmed: light.confirmed ?? false,
      confirmedAt: this.confirmedAt.get(light.id) ?? null,
    }
  }

  private withRunning(zoneId: Id, then: (zone: RunningZone) => MockReply): MockReply {
    const zone = this.state.running.find((candidate) => candidate.zoneId === zoneId)
    return zone === undefined ? notFound(`Zone '${zoneId}' is not running`) : then(zone)
  }

  private update<T extends { id: Id }>(items: T[], id: Id, body: unknown): MockReply {
    const item = items.find((candidate) => candidate.id === id)
    return item === undefined ? notFound(`No '${id}'`) : ok(Object.assign(item, body as Partial<T>, { id }))
  }

  private remove<T extends { id: Id }>(items: T[], id: Id): MockReply {
    const index = items.findIndex((candidate) => candidate.id === id)
    if (index < 0) return notFound(`No '${id}'`)
    items.splice(index, 1)
    return noContent
  }

  private saveLook(body: Look): MockReply {
    const look: Look = { ...body, id: this.newId('look'), builtIn: false, starred: false }
    this.state.looks.push(look)
    return created(look)
  }

  private updateLook(id: Id, body: Look): MockReply {
    return this.withLook(id, (look) => {
      if (look.builtIn) return { status: 409, body: { detail: BUILT_IN } }
      return ok(Object.assign(look, body, { id, builtIn: false }))
    })
  }

  private deleteLook(id: Id): MockReply {
    return this.withLook(id, (look) => {
      if (look.builtIn) return { status: 409, body: { detail: BUILT_IN } }
      return this.remove(this.state.looks, id)
    })
  }

  private createGroup(body: CreateGroup): MockReply {
    const zone = { id: this.newId('group'), name: body.name, kind: 'group' as const, lights: body.lights }
    this.state.zones.push(zone)
    return created(zone)
  }

  private updateGroup(id: Id, body: UpdateGroup): MockReply {
    const zone = this.state.zones.find((candidate) => candidate.id === id && candidate.kind === 'group')
    if (zone === undefined) return notFound(`No zone '${id}'`)
    if (body.name != null) zone.name = body.name
    if (body.lights != null) zone.lights = body.lights
    return ok(zone)
  }

  private deleteGroup(id: Id): MockReply {
    if (!this.state.zones.some((zone) => zone.id === id && zone.kind === 'group')) return notFound(`No zone '${id}'`)
    this.off(id)
    return this.remove(this.state.zones, id)
  }

  /** §11.3: the zone takes its lights from any running zone; a zone left with none stops. */
  private start(zoneId: Id, body: StartRequest): MockReply {
    const zone = this.state.zones.find((candidate) => candidate.id === zoneId)
    if (zone === undefined) return notFound(`No zone '${zoneId}'`)
    if ((body.lookId == null) === (body.look == null)) return badRequest('Send either lookId or look')
    const look = body.lookId != null ? this.state.looks.find((candidate) => candidate.id === body.lookId) : body.look
    if (look == null) return notFound(`No look '${body.lookId}'`)
    const taking = new Set(zone.lights)
    const takeOvers: TakeOver[] = []
    for (const other of this.state.running) {
      if (other.zoneId === zoneId) continue
      const lost = other.lights.filter((id) => taking.has(id))
      if (lost.length === 0) continue
      other.lights = other.lights.filter((id) => !taking.has(id))
      other.covers = coversOf(this.state.home, this.state.lights, other.lights)
      const name = this.state.zones.find((candidate) => candidate.id === other.zoneId)?.name ?? other.zoneId
      takeOvers.push({ zoneId: other.zoneId, zoneName: name, lookName: other.lookName, lights: lost, stopped: other.lights.length === 0 })
    }
    const previous = this.state.running.find((candidate) => candidate.zoneId === zoneId)
    this.state.running = this.state.running.filter((other) => other.zoneId !== zoneId && other.lights.length > 0)
    const running: RunningZone = {
      zoneId,
      lookId: look.id ?? '',
      lookName: look.name,
      since: this.isoNow(),
      brightness: previous?.brightness ?? 1,
      lights: zone.lights,
      covers: coversOf(this.state.home, this.state.lights, zone.lights),
      state: 'running',
      fps: { actual: 60, target: 60 },
    }
    this.state.running.push(running)
    for (const light of this.state.lights) {
      if (!taking.has(light.id) || light.status === 'offline' || light.status === 'switched-off') continue
      Object.assign(light, { status: 'streaming', statusSince: running.since, ownEffect: null, power: true, sendFps: 60 } satisfies Partial<Light>)
    }
    this.changed('running', 'lights')
    return ok({ ...running, takeOvers })
  }

  /** Off (§11.3): the look stops and its lights go back to how they were. Idempotent. */
  private off(zoneId: Id): MockReply {
    if (!this.state.zones.some((zone) => zone.id === zoneId)) return notFound(`No zone '${zoneId}'`)
    const running = this.state.running.find((zone) => zone.zoneId === zoneId)
    if (running === undefined) return noContent
    this.state.running = this.state.running.filter((zone) => zone !== running)
    this.release(running.lights)
    this.state.attention = this.state.attention.filter((item) => item.subject.id !== zoneId)
    this.changed('running', 'lights', 'attention')
    return noContent
  }

  private stopAll(): MockReply {
    this.release(this.state.running.flatMap((zone) => zone.lights))
    this.state.running = []
    this.state.overlays = []
    this.state.attention = this.state.attention.filter((item) => item.subject.type !== 'zone')
    this.changed('running', 'lights', 'attention')
    return noContent
  }

  private release(ids: Id[]): void {
    const since = this.isoNow()
    for (const light of this.state.lights) {
      if (!ids.includes(light.id) || light.status === 'offline' || light.status === 'switched-off') continue
      Object.assign(light, { status: 'idle', statusSince: since, ownEffect: null, sendFps: 0 } satisfies Partial<Light>)
    }
  }

  private putConfig(body: unknown): MockReply {
    const on = (body as { engine?: { preview_only?: unknown } } | null)?.engine?.preview_only
    if (on !== undefined && typeof on !== 'boolean') return badRequest('engine.preview_only must be true or false')
    if (on !== undefined && on !== this.state.previewOnly) {
      this.state.previewOnly = on
      this.changed('transport')
    }
    return ok({ engine: { preview_only: this.state.previewOnly } })
  }

  /** Spreads unplaced lights around their rooms, unconfirmed (§12.3): here, at the room's label. */
  private guess(): MockReply {
    const guessed: Light[] = []
    for (const light of this.state.lights) {
      const room = this.state.home.rooms.find((candidate) => candidate.id === light.room)
      if (light.shape != null || room === undefined) continue
      light.shape = { kind: 'point', position: [room.labelAt[0], room.labelAt[1], 1] }
      light.confirmed = false
      guessed.push(light)
    }
    return ok(guessed)
  }

  /** One preview at a time (§12.3): its frames go on the preview stream, and the lights are left alone. */
  private startPreview(body: PreviewRequest): MockReply {
    const zone = this.state.zones.find((candidate) => candidate.id === body.zoneId)
    if (zone === undefined) return notFound(`No zone '${body.zoneId}'`)
    const look = body.lookId != null ? this.state.looks.find((candidate) => candidate.id === body.lookId) : body.look
    if (look == null) return badRequest('Send either lookId or look')
    const lights = new Map(this.state.lights.map((light) => [light.id, light]))
    const spec = motifFor(look)
    this.preview = {
      id: this.newId('preview'),
      lights: zone.lights.map((id) => this.painted(id, lights.get(id)?.leds ?? 0, spec, 1, false)),
    }
    return ok({ previewId: this.preview.id })
  }

  private updatePreview(id: Id, body: { look?: Look }): MockReply {
    if (this.preview?.id !== id) return notFound(`No preview '${id}'`)
    if (body.look !== undefined) {
      const spec = motifFor(body.look)
      for (const light of this.preview.lights) light.spec = spec
    }
    return noContent
  }

  private stopPreview(id: Id): MockReply {
    if (this.preview?.id === id) this.preview = null
    return noContent
  }
}
```

- [ ] **Step 5: Write `in-memory-socket.ts`**

```ts
// A LiveSocket wired straight to a MockServer: the whole data layer runs in a test without MSW.
// It opens on the next timer and delivers each message in a microtask, as a real socket is async.
import type { LiveSocket, OpenSocket } from '../live-client'
import type { MockServer, MockSession } from './mock-server'

class InMemorySocket implements LiveSocket {
  binaryType: BinaryType = 'blob'
  onopen: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  private readonly server: MockServer
  private session: MockSession | null = null
  private closed = false

  constructor(server: MockServer) {
    this.server = server
    setTimeout(() => this.open(), 0)
  }

  send(data: string): void {
    if (this.session !== null && !this.closed) this.server.receive(this.session, data)
  }

  close(): void {
    if (this.closed) return
    this.closed = true
    if (this.session !== null) this.server.disconnect(this.session)
  }

  private open(): void {
    if (this.closed) return
    this.session = this.server.connect({ send: (data) => this.deliver(data), close: () => this.shut() })
    if (this.session === null) {
      this.shut()
      return
    }
    // The snapshots connect() sent are still in their microtasks, so open comes first, as on a real socket.
    this.onopen?.(new Event('open'))
  }

  private deliver(data: string | ArrayBuffer): void {
    queueMicrotask(() => {
      if (!this.closed) this.onmessage?.({ data } as MessageEvent)
    })
  }

  private shut(): void {
    if (this.closed) return
    this.closed = true
    queueMicrotask(() => this.onclose?.({} as CloseEvent))
  }
}

export function inMemorySockets(server: MockServer): OpenSocket {
  return () => new InMemorySocket(server)
}
```

- [ ] **Step 6: Write `handlers.ts`**

```ts
// MSW's handlers over a MockServer (spec §12.5): every /api request, and the /ws socket.
import { HttpResponse, http, ws } from 'msw'
import type { MockServer } from './mock-server'

export function mockHandlers(server: MockServer, socketUrl: string) {
  return [
    http.all('*/api/*', async ({ request }) => {
      const text = await request.text()
      let body: unknown
      try {
        body = text === '' ? undefined : JSON.parse(text)
      } catch {
        return HttpResponse.json({ detail: 'Invalid JSON' }, { status: 400 })
      }
      const reply = server.handle(request.method, new URL(request.url).pathname, body)
      return reply.body === undefined
        ? new HttpResponse(null, { status: reply.status })
        : HttpResponse.json(reply.body, { status: reply.status })
    }),
    ws.link(socketUrl).addEventListener('connection', ({ client }) => {
      const session = server.connect({ send: (data) => client.send(data), close: () => client.close() })
      if (session === null) {
        client.close()
        return
      }
      client.addEventListener('message', (event) => {
        if (typeof event.data === 'string') server.receive(session, event.data)
      })
      client.addEventListener('close', () => server.disconnect(session))
    }),
  ]
}
```

- [ ] **Step 7: Run the tests**

Run: `(cd web && npx vitest run src/api/mocks/mock-server.test.ts src/api/mocks/msw.test.ts)`
Expected: PASS (mock server 17, MSW 3). If the MSW socket test sees no frames, check that MSW hands the client the `ArrayBuffer` as sent: `LiveClient.receive` decodes `ArrayBuffer` only, and a `Blob` would be dropped without a count.

- [ ] **Step 8: Gate and commit**

```bash
git add web/package.json web/package-lock.json web/src/api/mocks
git commit -m "feat(web): a mock server for each scenario, over MSW and in memory, speaking v2 or today's M1"
```

---

### Task 11: Booting the data layer, and the mock build

Implements §12.5's "A `?scenario=` query switches fixtures in dev", §9.4's "Resync everything on reconnect" for REST data, §3.3's TanStack Query, and §14 Performance's bundle budget. Decisions 11 and 13. No renders.

**Files:**
- Modify: `web/package.json`, `web/package-lock.json` (@tanstack/react-query; the `msw.workerDirectory` entry; scripts), `web/vite.config.ts`, `web/playwright.config.ts`, `web/.gitignore`, `web/eslint.config.js`, `web/src/main.tsx`
- Create: `web/public/mockServiceWorker.js` (by `npx msw init`), `web/scripts/check-dist.ts`, `web/src/api/queries.ts`, `web/src/api/live.ts`, `web/src/api/mocks/choice.ts`, `web/src/api/mocks/browser.ts`
- Test: `web/src/api/queries.test.ts`, `web/src/api/live.test.ts`, `web/src/api/mocks/choice.test.ts`

**Interfaces:**
- Consumes: `api` (Task 3), `FrameStore` (Task 4), `BeatClock` (Task 5), `liveStore` (Task 6), `LiveClient`, `liveSocketUrl` and `OpenSocket` (Task 7), `isScenario` and `ScenarioName` (Task 8), and `MockServer`, `inMemorySockets` and `mockHandlers` (Task 10).
- Produces:
  - From `queries.ts`: `createQueryClient(): QueryClient`, `queryClient`, `queries` (`looks()`, `look(id)`, `zones()`, `lights()`, `home()`, `inputs()`, `signals()`, each a `queryOptions`), and `resync(client): Promise<void>`.
  - From `live.ts`: the app's `frames: FrameStore` and `beatClock: BeatClock`; `startDataLayer(options?: { openSocket?: OpenSocket; url?: string }): LiveClient`, which stops any client it started before; and `liveClient(): LiveClient | null`.
  - From `mocks/choice.ts`: `interface MockChoice { scenario: ScenarioName; still: boolean; protocol: 1 | 2 }` and `mockChoice(search: string, options: { mockBuild: boolean }): MockChoice | null`.
  - From `mocks/browser.ts`: `startMocks(choice: MockChoice): Promise<MockServer>`.
  - npm scripts `build` (now ending in `node scripts/check-dist.ts`) and `build:mock`. `npm run build:mock` writes `web/dist-mock`, which Playwright serves.

- [ ] **Step 1: Read the spec and the libraries**

Re-read §12.5, §9.4, §3.3, §14 Performance, and decisions 11 and 13. With context7, check:
- @tanstack/react-query 5: `QueryClient` with `defaultOptions.queries`, `queryOptions`, `QueryClientProvider`, `fetchQuery`, and `invalidateQueries()`, which marks every query stale and refetches the active ones.
- MSW 2: `setupWorker(...handlers)` from `msw/browser`, and `worker.start({ serviceWorker: { url }, onUnhandledRequest: 'bypass', quiet: true })`; `npx msw init <dir> --save`.
- Vite 8: a config function of `{ mode }`, `publicDir: false`, `build.outDir`, and `vite build --mode` and `vite preview --mode`.

```bash
(cd web && npm install @tanstack/react-query@^5.103.2 && npx msw init public --save)
```

Expected: `web/public/mockServiceWorker.js` exists, and `web/package.json` has `"msw": { "workerDirectory": ["public"] }`.

- [ ] **Step 2: Write the failing tests**

`web/src/api/mocks/choice.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { mockChoice } from './choice'

describe('mockChoice', () => {
  it('leaves dev on the real server unless a scenario is asked for', () => {
    expect(mockChoice('', { mockBuild: false })).toBeNull()
    expect(mockChoice('?zone=living', { mockBuild: false })).toBeNull()
  })

  it('plays the scenario asked for', () => {
    expect(mockChoice('?scenario=problems', { mockBuild: false })).toEqual({ scenario: 'problems', still: false, protocol: 2 })
  })

  it('holds the beat with ?still', () => {
    expect(mockChoice('?scenario=hero&still', { mockBuild: false })?.still).toBe(true)
  })

  it('always mocks in the mock build, the hero by default', () => {
    expect(mockChoice('', { mockBuild: true })).toEqual({ scenario: 'hero', still: false, protocol: 2 })
  })

  it('plays the hero for a scenario it does not know', () => {
    expect(mockChoice('?scenario=nope', { mockBuild: false })?.scenario).toBe('hero')
  })

  it("speaks today's M1 protocol with ?protocol=1", () => {
    expect(mockChoice('?scenario=hero&protocol=1', { mockBuild: false })?.protocol).toBe(1)
  })
})
```

`web/src/api/queries.test.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createQueryClient, queries, resync } from './queries'

const fetchMock = vi.fn<typeof fetch>()

beforeEach(() => {
  fetchMock.mockReset()
  fetchMock.mockImplementation(async () => Response.json([{ id: 'fireflies' }]))
  vi.stubGlobal('fetch', fetchMock)
})

describe('queries', () => {
  it('fetch through the REST client once, and again after a resync', async () => {
    const client = createQueryClient()
    expect(await client.fetchQuery(queries.looks())).toEqual([{ id: 'fireflies' }])
    await client.fetchQuery(queries.looks())
    expect(fetchMock).toHaveBeenCalledTimes(1)
    await resync(client)
    await client.fetchQuery(queries.looks())
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('key each look apart, under the looks', () => {
    expect(queries.look('a').queryKey).not.toEqual(queries.look('b').queryKey)
    expect(queries.look('a').queryKey[0]).toBe(queries.looks().queryKey[0])
  })
})
```

`web/src/api/live.test.ts`:

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fakeSockets } from '@/test/fake-socket'
import { frames, liveClient, startDataLayer } from './live'
import { liveStore } from './live-store'
import { inMemorySockets } from './mocks/in-memory-socket'
import { MockServer } from './mocks/mock-server'

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(new Date(2026, 8, 23, 19, 14))
})

afterEach(() => {
  liveClient()?.stop()
})

describe('startDataLayer', () => {
  it("fills the app's stores from the server", async () => {
    const server = new MockServer({ clock: () => Date.now(), wallClock: () => Date.now() })
    server.start()
    startDataLayer({ openSocket: inMemorySockets(server), url: 'mock' })
    await vi.advanceTimersByTimeAsync(1100)
    expect(liveStore.getState().attention).toHaveLength(1)
    expect(liveStore.getState().connection.status).toBe('live')
    expect(frames.live.size).toBeGreaterThan(0)
    server.stop()
  })

  it('keeps one client: starting again stops the first', () => {
    const { sockets, open } = fakeSockets()
    const first = startDataLayer({ openSocket: open, url: 'ws://test/ws' })
    const second = startDataLayer({ openSocket: open, url: 'ws://test/ws' })
    expect(second).not.toBe(first)
    expect(liveClient()).toBe(second)
    expect(sockets).toHaveLength(2)
    expect(sockets[0].closed).toBe(true)
  })
})
```

- [ ] **Step 3: Run them to see them fail**

Run: `(cd web && npx vitest run src/api/queries.test.ts src/api/live.test.ts src/api/mocks/choice.test.ts)`
Expected: FAIL, with `Failed to load url ./queries`, `./live` and `./choice`.

- [ ] **Step 4: Write `queries.ts` and `live.ts`**

`web/src/api/queries.ts`:

```ts
// REST reads through TanStack Query (spec §3.3). The socket pushes what changes (running, lights,
// attention), so what REST loads stays fresh until a reconnect, when resync() fetches it all again
// (§9.4, "Resync everything on reconnect").
import { QueryClient, queryOptions } from '@tanstack/react-query'
import type { Id } from './contract'
import { api } from './rest'

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { staleTime: Infinity, retry: 1, refetchOnWindowFocus: false } },
  })
}

/** The app's query client. */
export const queryClient = createQueryClient()

export const queries = {
  looks: () => queryOptions({ queryKey: ['looks'], queryFn: api.looks }),
  look: (id: Id) => queryOptions({ queryKey: ['looks', id], queryFn: () => api.look(id) }),
  zones: () => queryOptions({ queryKey: ['zones'], queryFn: api.zones }),
  lights: () => queryOptions({ queryKey: ['lights'], queryFn: api.lights }),
  home: () => queryOptions({ queryKey: ['home'], queryFn: api.home }),
  inputs: () => queryOptions({ queryKey: ['inputs'], queryFn: api.inputs }),
  signals: () => queryOptions({ queryKey: ['signals'], queryFn: api.signals }),
}

/** After a reconnect: every query goes stale, and the ones on screen fetch again. */
export function resync(client: QueryClient): Promise<void> {
  return client.invalidateQueries()
}
```

`web/src/api/live.ts`:

```ts
// The app's one data layer: a frame store, a beat clock, and the live client that fills them and
// the live store. main.tsx starts it once; F3's "Try now" and F6/F8's signal subscriptions reach the
// client through liveClient().
import { BeatClock } from './beat'
import { FrameStore } from './frames'
import { LiveClient, liveSocketUrl, type OpenSocket } from './live-client'
import { liveStore } from './live-store'
import { queryClient, resync } from './queries'

export const frames = new FrameStore()
export const beatClock = new BeatClock()

let client: LiveClient | null = null

/** Starts the live client, stopping any this started before: there is one socket at a time. */
export function startDataLayer(options: { openSocket?: OpenSocket; url?: string } = {}): LiveClient {
  client?.stop()
  client = new LiveClient({
    url: options.url ?? liveSocketUrl(),
    store: liveStore,
    frames,
    beatClock,
    openSocket: options.openSocket,
    onResync: () => void resync(queryClient),
  })
  client.start()
  return client
}

export function liveClient(): LiveClient | null {
  return client
}
```

- [ ] **Step 5: Write `choice.ts` and `browser.ts`**

`web/src/api/mocks/choice.ts` (no MSW import, so it loads anywhere):

```ts
// Which mock the page asks for (decision 11): in dev only with ?scenario=, in the mock build always.
import { isScenario, type ScenarioName } from './scenarios'

export interface MockChoice {
  scenario: ScenarioName
  /** ?still: the beat holds, for screenshots and render counts. */
  still: boolean
  /** ?protocol=1: speak as engine M1 does today. */
  protocol: 1 | 2
}

/** The mock the URL asks for, or null for the real server. An unknown scenario plays the hero. */
export function mockChoice(search: string, { mockBuild }: { mockBuild: boolean }): MockChoice | null {
  const params = new URLSearchParams(search)
  const asked = params.get('scenario')
  if (asked === null && !mockBuild) return null
  return {
    scenario: asked !== null && isScenario(asked) ? asked : 'hero',
    still: params.has('still'),
    protocol: params.get('protocol') === '1' ? 1 : 2,
  }
}
```

`web/src/api/mocks/browser.ts`:

```ts
// MSW in the browser over a MockServer. main.tsx imports this only in dev and in the mock build.
import { setupWorker } from 'msw/browser'
import { liveSocketUrl } from '../live-client'
import type { MockChoice } from './choice'
import { mockHandlers } from './handlers'
import { MockServer } from './mock-server'

export async function startMocks(choice: MockChoice): Promise<MockServer> {
  const server = new MockServer(choice)
  const worker = setupWorker(...mockHandlers(server, liveSocketUrl()))
  await worker.start({
    serviceWorker: { url: `${import.meta.env.BASE_URL}mockServiceWorker.js` },
    onUnhandledRequest: 'bypass',
    quiet: true,
  })
  server.start()
  return server
}
```

- [ ] **Step 6: Boot from `main.tsx`**

Replace `web/src/main.tsx`:

```tsx
import { QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router'
import { startDataLayer } from './api/live'
import { queryClient } from './api/queries'
import { routerBasename } from './app/router'
import { routes } from './app/routes'
import './styles/app.css'

async function boot(): Promise<void> {
  // Decision 11: the mocks load in dev (with ?scenario=) and in the mock build only. A production
  // build folds this condition to false and drops the import, MSW with it (scripts/check-dist.ts).
  if (import.meta.env.DEV || import.meta.env.MODE === 'mock') {
    const { mockChoice } = await import('./api/mocks/choice')
    const choice = mockChoice(window.location.search, { mockBuild: import.meta.env.MODE === 'mock' })
    if (choice !== null) {
      const { startMocks } = await import('./api/mocks/browser')
      await startMocks(choice)
    }
  }
  startDataLayer()
  const router = createBrowserRouter(routes, { basename: routerBasename(import.meta.env.BASE_URL) })
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </StrictMode>,
  )
}

void boot()
```

- [ ] **Step 7: The mock build, and the check that production has no MSW**

Replace `web/vite.config.ts`:

```ts
import { fileURLToPath, URL } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// Served by FastAPI at /next until the F11 cut-over (engine spec §10). `--mode mock` builds the app
// with its mocks into dist-mock for Playwright. Only dev and that build get MSW's worker from
// public/; production has no public dir (decision 11).
export default defineConfig(({ mode }) => ({
  base: '/next/',
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  publicDir: mode === 'production' ? false : 'public',
  build: { outDir: mode === 'mock' ? 'dist-mock' : 'dist' },
  server: {
    port: 5174,
    strictPort: true,
    proxy: {
      '/api': 'http://localhost:8080',
      '/ws': { target: 'ws://localhost:8080', ws: true },
    },
  },
  preview: { port: 4174, strictPort: true },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
    // A spy (a muted console.error, say) ends with the test that made it, and so does a stubbed global.
    restoreMocks: true,
    unstubGlobals: true,
  },
}))
```

`web/scripts/check-dist.ts`:

```ts
// Fails when MSW reached a build (decision 11). `npm run build` runs it over web/dist; pass another
// directory to check that one.
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, resolve } from 'node:path'

const MARKERS = ['mockServiceWorker', '[MSW]']
const dir = resolve(import.meta.dirname, '..', process.argv[2] ?? 'dist')

function files(path: string): string[] {
  return readdirSync(path).flatMap((name) => {
    const full = join(path, name)
    return statSync(full).isDirectory() ? files(full) : [full]
  })
}

const found = files(dir).flatMap((file) => {
  const text = readFileSync(file, 'utf8')
  return MARKERS.filter((marker) => file.includes(marker) || text.includes(marker)).map((marker) => `${file}: ${marker}`)
})

if (found.length > 0) {
  console.error(`MSW reached ${dir}:\n${found.join('\n')}`)
  process.exit(1)
}
console.log(`${dir}: no MSW`)
```

In `web/package.json`, change `build` and add `build:mock`:

```json
    "build": "tsc -b && vite build && node scripts/check-dist.ts",
    "build:mock": "tsc -b && vite build --mode mock",
```

In `web/playwright.config.ts`, serve the mock build:

```ts
// Runs against the mock build (vite preview --mode mock) at /next, the way FastAPI serves the real
// one: the same bundle, with MSW playing ?scenario= (the hero by default).
```

```ts
  webServer: {
    command: 'npm run build:mock && npm run preview -- --mode mock',
    url: 'http://localhost:4174/next/',
    reuseExistingServer: false,
  },
```

Add `dist-mock` to `web/.gitignore`, under `dist`, and to ESLint's ignores in `web/eslint.config.js`:

```js
  globalIgnores(['dist', 'dist-mock', 'playwright-report', 'test-results', 'src/api/generated/schema.d.ts']),
```

Commit `web/public/mockServiceWorker.js` as `npx msw init` wrote it; MSW warns in the console when the worker and the package disagree, and `npx msw init public` refreshes it. ESLint lints only `**/*.{ts,tsx}`, so it never reads the worker.

- [ ] **Step 8: Run the tests and both builds**

```bash
(cd web && npx vitest run src/api/queries.test.ts src/api/live.test.ts src/api/mocks/choice.test.ts)
(cd web && npm run build)
(cd web && npm run build:mock && ls dist-mock/mockServiceWorker.js && ! node scripts/check-dist.ts dist-mock >/dev/null 2>&1 && echo "the check catches MSW")
```

Expected:
- The tests pass: queries 2, live 2, choice 6.
- `npm run build` ends with `…/web/dist: no MSW`.
- The mock build has the worker, and `the check catches MSW` shows `check-dist.ts` fails on it. A check that can't fail proves nothing.

- [ ] **Step 9: Run e2e on the mock build**

Run: `(cd web && npm run e2e 2>&1 | tail -3)`
Expected: as before Task 1, `56 passed`, `16 skipped`. The chrome still draws F0's fixture here (Task 12 moves it to the stores), so the screenshots match. Only the server behind the page changed.

- [ ] **Step 10: Gate and commit**

```bash
git add web/package.json web/package-lock.json web/vite.config.ts web/playwright.config.ts web/.gitignore web/eslint.config.js web/public/mockServiceWorker.js web/scripts/check-dist.ts web/src/main.tsx web/src/api/queries.ts web/src/api/queries.test.ts web/src/api/live.ts web/src/api/live.test.ts web/src/api/mocks/choice.ts web/src/api/mocks/choice.test.ts web/src/api/mocks/browser.ts
git commit -m "feat(web): boot the data layer, mock in dev with ?scenario= and in the mock build, keep MSW out of dist"
```

---

### Task 12: The chrome on the stores

This task implements the F0 review's two constraints (the whole Owner's constraints list under Global Constraints), §9's first-load and Reconnecting states for the chrome, and decisions 3, 9 and 10. It owns review focus 2 and 3. Renders: `Main.png`, `Phone-Live.png`, `State-Reconnecting.png` and `Phone-State-Reconnecting.png`.

**Files:**
- Modify:
  - `web/src/chrome/state.ts`, `web/src/chrome/tempo-module.tsx`, `web/src/chrome/connection-indicator.tsx` and `web/src/chrome/chrome.test.tsx`.
  - `web/src/shell/app-shell.tsx`, `web/src/shell/top-bar.tsx`, `web/src/shell/phone-header.tsx`, `web/src/shell/rail.tsx`, `web/src/shell/tab-bar.tsx`, `web/src/shell/nav-dot.tsx` and `web/src/shell/shell.test.tsx`.
  - `web/src/app/page-meta.ts`, `web/src/app/routes.tsx` and `web/src/app/app.test.tsx`.
  - `web/e2e/shell.spec.ts`.
- Create: `web/src/chrome/hooks.ts`, `web/src/chrome/live.tsx`, `web/src/test/live.ts`, `web/src/test/app.tsx` and `web/src/test/count-renders.ts`.
- Test: `web/src/chrome/live.test.tsx`.

**Interfaces:**
- Consumes:
  - From Task 6: `liveStore`, `applyMessage`, `useLive`, `useLiveShallow` and `Connection`.
  - From Task 2: `AttentionItem`, `Id` and `TempoSource`.
  - From Task 7: `LiveClient` and, in the tests, `fakeSockets`.
  - From Task 5: `BeatClock`.
  - From Task 4: `FrameStore`, `encodeFrame` and `decodeFrame`.
  - From Task 11: `frames`.
  - In the tests: `buildScenario` and `ScenarioName` (Task 8), and `snapshotMessages`, `beatMessage` and `statsMessage` (Task 10).
- Produces:
  - `state.ts`:
    - `TempoState`, whose `beat: number | null` is null while stopped and whose `bar: number | null` is null with no bar count.
    - `AttentionCounts`, `ChromeState` and `HERO_CHROME`.
    - Re-exports of `Connection` (from the live store) and `TempoSource`.
    - `useChrome()` is gone.
  - `hooks.ts`:
    - `useTempo(): TempoState | null`.
    - `useConnection(): Connection` and `useConnectionStatus()`.
    - `countAttention(items): AttentionCounts` and `useAttentionCounts(): AttentionCounts | null`.
    - `usePreviewOnly()`, `useServerName()` and `useSunset()`, which keep the fixture (decision 10).
  - `live.tsx`: `ChromeTempo`, `ChromeTempoStrip`, `ChromePreviewOnly({ variant })`, `ChromeAttention({ variant })` and `ChromeConnection({ variant })`.
  - Shell props:
    - `TopBar({ title, context? })` and `PhoneHeader({ title, context?, children? })`.
    - `Rail({ server })`, `TabBar()` and `NavDot({ item, className })`.
    - `MetaContext { now: Date; sunset: string }`.
  - Test helpers:
    - `src/test/live.ts`: `HERO_NOW`, `seedLive(name?, now?)` and `attentionAbout(type, id)`.
    - `src/test/app.tsx`: `renderApp(path, routeList?)`.
    - `src/test/count-renders.ts`: `renders`, `resetRenders()` and `counted(name, Component)`.

- [ ] **Step 1: Read the spec and the renders**

Re-read these:
- §9.4's Reconnecting row.
- §6.2, for the cluster.
- §5.4, since F3 drives the pips from the beat clock.
- §10's "BPM (one decimal …)".
- The Owner's constraints in Global Constraints.
- Decisions 3, 9 and 10.

Look at these renders:
- `Main.png` and `Phone-Live.png`, which the screenshots must still match.
- `State-Reconnecting.png` and `Phone-State-Reconnecting.png`.

F1 moves the connection, the tempo and the attention onto the stores. It does nothing else to the chrome, and the Hand-off section lists what F3 does.

- [ ] **Step 2: Write the test helpers**

`web/src/test/live.ts`:

```ts
import type { AttentionItem, Id } from '@/api/contract'
import { applyMessage, liveStore } from '@/api/live-store'
import { beatMessage, snapshotMessages } from '@/api/mocks/mock-server'
import { buildScenario, type ScenarioName } from '@/api/mocks/scenarios'

/** The hero moment (§12.5): Wednesday 23 September 2026, 19:14. */
export const HERO_NOW = new Date(2026, 8, 23, 19, 14)

/** Fills the app's live store as a scenario's server does on connect: snapshots, a beat, and 60 fps. */
export function seedLive(name: ScenarioName = 'hero', now: Date = HERO_NOW): void {
  const state = buildScenario(name, now)
  const at = now.getTime() / 1000
  for (const message of snapshotMessages(state, 2)) applyMessage(liveStore, message, at)
  applyMessage(liveStore, beatMessage(state, 0, at, 2), at)
  liveStore.setState({ connection: { status: 'live', fps: 60 } })
}

const KIND = { light: 'light-offline', zone: 'zone-crashed', input: 'input-disconnected' } as const

/** One attention item about a light, a zone or an input. */
export function attentionAbout(type: keyof typeof KIND, id: Id): AttentionItem {
  return {
    id: `${KIND[type]}:${id}`,
    severity: 'normal',
    kind: KIND[type],
    subject: { type, id },
    title: id,
    detail: id,
    since: '2026-09-23T19:02:00-05:00',
    actions: ['details'],
  }
}
```

`web/src/test/app.tsx`, moved out of `app.test.tsx` so other tests can render the whole app:

```tsx
import { render } from '@testing-library/react'
import { createMemoryRouter, RouterProvider, type RouteObject } from 'react-router'
import { routerBasename } from '@/app/router'
import { routes } from '@/app/routes'

/** Renders the app's routes (or `routeList`) at `path`, under /next as main.tsx serves them. */
export function renderApp(path: string, routeList: RouteObject[] = routes) {
  // Vite's base, as main.tsx gets it. Vitest reports '/' for import.meta.env.BASE_URL, so it's literal.
  const router = createMemoryRouter(routeList, { basename: routerBasename('/next/'), initialEntries: [path] })
  render(<RouterProvider router={router} />)
  return router
}
```

`web/src/test/count-renders.ts`:

```ts
import { createElement, type ComponentType } from 'react'

/** How often each counted component rendered since the last resetRenders(). */
export const renders: Record<string, number> = {}

export function resetRenders(): void {
  for (const name of Object.keys(renders)) delete renders[name]
}

/** `Real`, counting each render under `name`. For a vi.mock factory. */
export function counted<P extends object>(name: string, Real: ComponentType<P>): ComponentType<P> {
  function Counted(props: P) {
    renders[name] = (renders[name] ?? 0) + 1
    return createElement(Real, props)
  }
  return Counted
}
```

- [ ] **Step 3: Write the failing tests**

`web/src/chrome/live.test.tsx`:

```tsx
import { act, screen, within } from '@testing-library/react'
import { describe, expect, it, onTestFinished, vi } from 'vitest'
import { BeatClock } from '@/api/beat'
import { decodeFrame, encodeFrame, FrameStore } from '@/api/frames'
import { frames } from '@/api/live'
import { LiveClient } from '@/api/live-client'
import { applyMessage, liveStore } from '@/api/live-store'
import { beatMessage, statsMessage } from '@/api/mocks/mock-server'
import { buildScenario } from '@/api/mocks/scenarios'
import { renderApp } from '@/test/app'
import { renders, resetRenders } from '@/test/count-renders'
import { fakeSockets } from '@/test/fake-socket'
import { attentionAbout, HERO_NOW, seedLive } from '@/test/live'
import { countAttention } from './hooks'

// Each chrome part, and the top bar around them, counts its renders.
vi.mock('./tempo-module', async (importOriginal) => {
  const { counted } = await import('@/test/count-renders')
  const real = await importOriginal<typeof import('./tempo-module')>()
  return { ...real, TempoModule: counted('tempo', real.TempoModule) }
})
vi.mock('./attention-button', async (importOriginal) => {
  const { counted } = await import('@/test/count-renders')
  const real = await importOriginal<typeof import('./attention-button')>()
  return { ...real, AttentionButton: counted('attention', real.AttentionButton) }
})
vi.mock('./connection-indicator', async (importOriginal) => {
  const { counted } = await import('@/test/count-renders')
  const real = await importOriginal<typeof import('./connection-indicator')>()
  return { ...real, ConnectionIndicator: counted('connection', real.ConnectionIndicator) }
})
vi.mock('@/shell/top-bar', async (importOriginal) => {
  const { counted } = await import('@/test/count-renders')
  const real = await importOriginal<typeof import('@/shell/top-bar')>()
  return { ...real, TopBar: counted('topBar', real.TopBar) }
})

const hero = buildScenario('hero', HERO_NOW)

describe('the chrome on the live store', () => {
  // F0 review: the chrome reads the stores a slice at a time, "so a beat doesn't re-render all of the chrome".
  it('redraws only the part whose slice changed', () => {
    seedLive()
    renderApp('/next/live')
    resetRenders()

    // A beat message inside the same beat changes nothing the chrome shows.
    act(() => applyMessage(liveStore, beatMessage(hero, 0.1, 0, 2), 0))
    expect(renders).toEqual({})

    // The next beat moves the pips: the tempo module alone redraws, not the bar around it.
    act(() => applyMessage(liveStore, beatMessage(hero, 0.5, 0, 2), 0))
    expect(renders).toEqual({ tempo: 1 })
    expect(screen.getByRole('img', { name: 'Beat 3 of 4' })).toBeInTheDocument()

    // Nothing needs attention any more: the attention button alone redraws, to All good.
    resetRenders()
    act(() => applyMessage(liveStore, { channel: 'attention', items: [] }, 0))
    expect(renders).toEqual({ attention: 1 })
    expect(screen.getByRole('button', { name: 'All good' })).toBeInTheDocument()

    // The devices' stats, and a second of frames for every light, redraw nothing.
    resetRenders()
    act(() => {
      applyMessage(liveStore, statsMessage(hero), 0)
      for (let seq = 1; seq <= 60; seq++) {
        for (const light of hero.lights) {
          decodeFrame(encodeFrame(2, light.id, seq, new Uint8Array(light.leds * 3)), 2, frames, seq / 60)
        }
      }
    })
    expect(renders).toEqual({})
  })

  // Review focus 2, and F0 review: never "All good" before the server's first data.
  it('shows no tempo, no All good and no Live before the server speaks', () => {
    renderApp('/next/live')
    const bar = screen.getByRole('banner')
    expect(within(bar).queryByRole('group', { name: 'Tempo' })).toBeNull()
    expect(within(bar).queryByRole('button', { name: /All good|attention/ })).toBeNull()
    // The title is the banner's only "Live".
    expect(within(bar).getAllByText('Live')).toEqual([within(bar).getByRole('heading', { level: 1 })])
    expect(screen.queryByText(', needs attention')).toBeNull()

    act(() => seedLive())
    expect(within(bar).getByRole('group', { name: 'Tempo' })).toHaveTextContent('121.8')
    expect(within(bar).getByRole('button', { name: '1 needs attention' })).toBeInTheDocument()
    expect(bar).toHaveTextContent('Live60 fps')
  })

  // Review focus 2: the server is down when the page loads.
  it('says Reconnecting, not All good, when the server is down from the start', () => {
    const { sockets, open } = fakeSockets()
    const client = new LiveClient({
      url: 'ws://test/ws',
      store: liveStore,
      frames: new FrameStore(),
      beatClock: new BeatClock(),
      openSocket: open,
    })
    client.start()
    onTestFinished(() => client.stop())
    renderApp('/next/live')

    act(() => sockets[0].drop())
    const bar = screen.getByRole('banner')
    expect(bar).toHaveTextContent('Reconnecting· try 1')
    expect(screen.getByRole('status')).toHaveTextContent(/^Reconnecting$/)
    expect(within(bar).queryByRole('button', { name: /All good|attention/ })).toBeNull()
    expect(within(bar).queryByRole('group', { name: 'Tempo' })).toBeNull()
  })

  // Review focus 3: engine M1 with no DJ sends a beat at 0 BPM, stopped, with no bar.
  it('holds the pips still when no DJ plays', () => {
    renderApp('/next/live')
    act(() => applyMessage(liveStore, beatMessage(hero, 0, 0, 1), 0))
    const tempo = within(screen.getByRole('banner')).getByRole('group', { name: 'Tempo' })
    expect(within(tempo).getByRole('button', { name: 'Pro DJ Link' })).toBeInTheDocument()
    expect(tempo).toHaveTextContent('0.0BPM')
    expect(within(tempo).queryByRole('img')).toBeNull()
    expect(tempo).not.toHaveTextContent(/bar \d/)
  })
})

describe('countAttention', () => {
  it('counts every item, and the lights and the inputs apart', () => {
    const items = [
      attentionAbout('light', 'rope'),
      attentionAbout('zone', 'kitchen'),
      attentionAbout('input', 'music'),
      attentionAbout('light', 'tube'),
    ]
    expect(countAttention(items)).toEqual({ total: 4, lights: 2, inputs: 1 })
    expect(countAttention([])).toEqual({ total: 0, lights: 0, inputs: 0 })
  })
})
```

In `web/src/chrome/chrome.test.tsx`, add to `describe('TempoModule')`:

```tsx
  // Engine M1's beat counts no bars (decision 9).
  it('leaves the bar out when the source counts none', () => {
    render(<TempoModule variant="bar" {...HERO_CHROME.tempo} bar={null} />)
    expect(screen.getByRole('group', { name: 'Tempo' })).not.toHaveTextContent(/bar \d/)
  })
```

Add to `describe('ConnectionIndicator')`:

```tsx
  // F0 review: before the server's first word, the link claims nothing.
  it.each(['bar', 'header'] as const)('shows nothing while it first connects (%s)', (variant) => {
    const { container } = render(<ConnectionIndicator variant={variant} connection={{ status: 'connecting' }} />)
    expect(container).toBeEmptyDOMElement()
  })

  // Decision 3: no frames yet, so no frame rate.
  it('shows Live alone until it has measured the frame rate', () => {
    render(<ConnectionIndicator variant="bar" connection={{ status: 'live', fps: null }} />)
    expect(screen.getByText('Live')).toBeInTheDocument()
    expect(screen.queryByText(/fps/)).toBeNull()
  })
```

Add to `describe('connection news')`:

```tsx
  it('says nothing on the first connect, and Reconnecting when it fails', () => {
    const { rerender } = render(<Region connection={{ status: 'connecting' }} />)
    const status = screen.getByRole('status')
    expect(status).toBeEmptyDOMElement()
    rerender(<Region connection={{ status: 'live', fps: null }} />)
    expect(status).toBeEmptyDOMElement()
    rerender(<Region connection={{ status: 'reconnecting', attempt: 1 }} />)
    expect(status).toHaveTextContent(/^Reconnecting$/)
  })
```

- [ ] **Step 4: Run them to see them fail**

Run: `(cd web && npx vitest run src/chrome/)`
Expected: FAIL. `live.test.tsx` fails with `Failed to load url ./hooks`, and the new `chrome.test.tsx` tests fail on "bar 42", "60 fps" and the `connecting` status.

- [ ] **Step 5: Put the chrome's types and parts on the store**

Replace `web/src/chrome/state.ts`:

```ts
// The chrome's data. The live store (src/api/live-store.ts) produces it; hooks.ts reads it one slice
// at a time, and the components in this folder draw it.
import type { TempoSource } from '@/api/contract'
import type { Connection } from '@/api/live-store'

export type { Connection, TempoSource }

export interface TempoState {
  source: TempoSource
  bpm: number
  /** Beat in the bar, 1–4. null: the beat doesn't move (stopped, stale, or 0 BPM), so no pip lights. */
  beat: number | null
  /** null: the source counts no bars (engine M1's beat), and the module leaves "bar N" out. */
  bar: number | null
  /** §6.2: the source stopped updating; its label turns signal and the pips stop. */
  stale: boolean
}

export interface AttentionCounts {
  total: number
  /** Light items: the rail dot on Devices. */
  lights: number
  /** Input items: the rail dot on Inputs (the Tempo tab on phone). */
  inputs: number
}

/** Everything the chrome shows. */
export interface ChromeState {
  tempo: TempoState
  previewOnly: boolean
  attention: AttentionCounts
  connection: Connection
  /** The server's name, in the rail footer. */
  server: string
  /** Today's sunset, 24 h, in the phone Live context line. */
  sunset: string
}

/**
 * The §12.5 "hero" scenario's chrome, as drawn in Main.png and Phone-Live.png. The System specimen
 * draws it, and hooks.ts serves its preview only, server name and sunset until F3 and F6 own them
 * (decision 10).
 */
export const HERO_CHROME: ChromeState = {
  tempo: { source: 'music', bpm: 121.8, beat: 2, bar: 42, stale: false },
  previewOnly: false,
  attention: { total: 1, lights: 1, inputs: 0 },
  connection: { status: 'live', fps: 60 },
  server: 'homeserver',
  sunset: '19:26',
}
```

`web/src/chrome/hooks.ts`:

```ts
// The chrome's reads from the live store, one slice each (F0 review: "so a beat doesn't re-render
// all of the chrome"). Each is null until its channel has spoken, and the part that draws it draws
// nothing until then (F0 review: no "All good" before the server's first data).
import type { AttentionItem } from '@/api/contract'
import { useLive, useLiveShallow, type Connection } from '@/api/live-store'
import { HERO_CHROME, type AttentionCounts, type TempoState } from './state'

/** The tempo module's values. BPM to one decimal (§10); the beat in the bar only while it moves. */
export function useTempo(): TempoState | null {
  return useLiveShallow(({ beat }) =>
    beat === null
      ? null
      : {
          source: beat.source,
          bpm: Math.round(beat.bpm * 10) / 10,
          beat: beat.playing ? beat.beatInBar : null,
          bar: beat.bar,
          stale: beat.stale,
        },
  )
}

export function useConnection(): Connection {
  return useLive((state) => state.connection)
}

/** The link's status alone: the shell's news follows it, and not the frame rate. */
export function useConnectionStatus(): Connection['status'] {
  return useLive((state) => state.connection.status)
}

/** §9.5: the items, and the light and input items apart for the dots on Devices and Inputs. */
export function countAttention(items: readonly AttentionItem[]): AttentionCounts {
  let lights = 0
  let inputs = 0
  for (const item of items) {
    if (item.subject.type === 'light') lights += 1
    else if (item.subject.type === 'input') inputs += 1
  }
  return { total: items.length, lights, inputs }
}

export function useAttentionCounts(): AttentionCounts | null {
  return useLiveShallow(({ attention }) => (attention === null ? null : countAttention(attention)))
}

/** The fixture until F3 wires the switch to the server (decision 10). */
export function usePreviewOnly(): boolean {
  return HERO_CHROME.previewOnly
}

/** The fixture until F6 (decision 10). */
export function useServerName(): string {
  return HERO_CHROME.server
}

/** The fixture until F6 (decision 10). */
export function useSunset(): string {
  return HERO_CHROME.sunset
}
```

`web/src/chrome/live.tsx`:

```tsx
// The chrome's parts on the live store. Each reads its own slice (hooks.ts), so a beat redraws the
// tempo module and nothing else, and each draws nothing until its data has arrived.
import { AttentionButton } from './attention-button'
import { ConnectionIndicator } from './connection-indicator'
import { useAttentionCounts, useConnection, usePreviewOnly, useTempo } from './hooks'
import { PreviewOnlySwitch } from './preview-only-switch'
import { TempoModule } from './tempo-module'

type Variant = 'bar' | 'header'

/** The top bar's tempo module, and the divider after it. */
export function ChromeTempo() {
  const tempo = useTempo()
  if (tempo === null) return null
  return (
    <>
      <TempoModule variant="bar" {...tempo} />
      <span aria-hidden="true" className="h-6 w-px bg-line tablet:hidden" />
    </>
  )
}

/** The phone's tempo strip under the header, on Live. */
export function ChromeTempoStrip() {
  const tempo = useTempo()
  if (tempo === null) return null
  return (
    <div className="mx-4 mt-1.5">
      <TempoModule variant="strip" {...tempo} />
    </div>
  )
}

export function ChromePreviewOnly({ variant }: { variant: Variant }) {
  return <PreviewOnlySwitch variant={variant} on={usePreviewOnly()} />
}

export function ChromeAttention({ variant }: { variant: Variant }) {
  const counts = useAttentionCounts()
  if (counts === null) return null
  return <AttentionButton variant={variant} count={counts.total} />
}

export function ChromeConnection({ variant }: { variant: Variant }) {
  return <ConnectionIndicator variant={variant} connection={useConnection()} />
}
```

The divider's classes move from `top-bar.tsx` to `ChromeTempo` unchanged, so the bar's DOM stays the same once the data is in.

In `web/src/chrome/connection-indicator.tsx`:
- Return nothing while connecting.
- Draw the frame rate only once it has been measured.

```tsx
export function ConnectionIndicator({ connection, variant }: ConnectionIndicatorProps) {
  // Before the server's first word the link claims nothing (F0 review).
  if (connection.status === 'connecting') return null

  if (connection.status === 'live') {
    if (variant === 'header') return null
    return (
      <span className="inline-flex items-center gap-1.75 text-meta whitespace-nowrap text-text-2">
        <span aria-hidden="true" className="size-1.75 rounded-full bg-text animate-[livedot_2s_ease-in-out_infinite]" />
        Live
        {connection.fps !== null && <span className="num text-text-3 tablet:hidden">{connection.fps} fps</span>}
      </span>
    )
  }
```

The reconnecting branches below it are unchanged.

In `web/src/chrome/tempo-module.tsx`:

1. Leave out a missing bar:

```tsx
      {bar !== null && <span className="num text-[11.5px] whitespace-nowrap text-text-3 tablet:hidden">bar {bar}</span>}
```

2. Update the component's comment:

```tsx
/**
 * §6.2 TempoModule. F1 draws the beat in the bar that each beat message carries; F3 drives the pips
 * from the beat clock (§5.4).
 */
```

- [ ] **Step 6: Give the shell slices instead of a ChromeState**

Replace `web/src/shell/top-bar.tsx`:

```tsx
import type { ReactNode } from 'react'
import { ChromeAttention, ChromeConnection, ChromePreviewOnly, ChromeTempo } from '@/chrome/live'

export interface TopBarProps {
  title: string
  context?: ReactNode
}

/**
 * §4.1 top bar (Main.png): title and context, then the always-within-reach cluster (§6.2). Each part
 * of the cluster reads its own slice of the live store, so the bar itself doesn't redraw for a beat.
 */
export function TopBar({ title, context }: TopBarProps) {
  return (
    <header className="flex h-(--topbar-h) min-w-0 items-center justify-between gap-4 border-b border-line-soft bg-bg pr-5 pl-6">
      <div className="flex min-w-0 items-baseline gap-3">
        <h1 className="truncate text-title font-semibold tracking-[-0.005em]">{title}</h1>
        {context && <span className="text-data whitespace-nowrap text-text-3 tablet:hidden">{context}</span>}
      </div>
      <div className="flex shrink-0 items-center gap-3.5 tablet:gap-2.5">
        <ChromeTempo />
        <ChromePreviewOnly variant="bar" />
        <ChromeAttention variant="bar" />
        <ChromeConnection variant="bar" />
      </div>
    </header>
  )
}
```

Replace `web/src/shell/phone-header.tsx`:

```tsx
import type { ReactNode } from 'react'
import { ChromeAttention, ChromeConnection, ChromePreviewOnly } from '@/chrome/live'

export interface PhoneHeaderProps {
  title: string
  context?: ReactNode
  /** Drawn under the title row, inside the banner: the tempo strip on Live. */
  children?: ReactNode
}

/** §4.2 phone header (Phone-Live.png): serif title and context; reconnect, eye and attention. */
export function PhoneHeader({ title, context, children }: PhoneHeaderProps) {
  return (
    <header className="shrink-0">
      <div className="flex h-(--phone-header-h) items-center justify-between gap-2 px-4">
        <div className="flex min-w-0 flex-col">
          <h1 className="truncate font-serif text-display-md leading-none">{title}</h1>
          {context && <span className="mt-0.75 truncate text-meta text-text-3">{context}</span>}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <ChromeConnection variant="header" />
          <ChromePreviewOnly variant="header" />
          <ChromeAttention variant="header" />
        </div>
      </div>
      {children}
    </header>
  )
}
```

Replace `web/src/shell/nav-dot.tsx`:

```tsx
import { useAttentionCounts } from '@/chrome/hooks'
import { cx } from '@/design/cx'
import type { NavItem } from './nav'

export interface NavDotProps {
  item: NavItem
  /** Where the dot sits on its item. */
  className: string
}

/**
 * The signal dot on a place that needs attention (spec §9.5), and its words for screen readers.
 * None before the server's first attention snapshot.
 */
export function NavDot({ item, className }: NavDotProps) {
  const counts = useAttentionCounts()
  if (item.dot === undefined || counts === null || counts[item.dot] === 0) return null
  return (
    <>
      <span aria-hidden="true" className={cx('absolute size-1.75 rounded-full bg-signal', className)} />
      <span className="sr-only">, needs attention</span>
    </>
  )
}
```

In `web/src/shell/rail.tsx`:
- Drop the `AttentionCounts` import.
- `RailProps` becomes `{ server: string }`, and the component becomes `export function Rail({ server }: RailProps)`.
- The dot becomes `<NavDot item={item} className="top-1.5 right-3 shadow-[0_0_0_2px_var(--color-bg)]" />`.

In `web/src/shell/tab-bar.tsx`:
- Drop the `AttentionCounts` import.
- The component becomes `export function TabBar()`.
- The dot becomes `<NavDot item={item} className="top-1.5 left-1/2 ml-2" />`.

Replace `web/src/shell/app-shell.tsx`:

```tsx
import { Outlet } from 'react-router'
import { documentTitle, usePageMeta, type MetaContext } from '@/app/page-meta'
import { useConnectionNews } from '@/chrome/connection-news'
import { useConnectionStatus, useServerName, useSunset } from '@/chrome/hooks'
import { ChromeTempoStrip } from '@/chrome/live'
import { Announcer } from '@/design/announcer'
import { cx } from '@/design/cx'
import { useIsPhone } from '@/lib/use-media-query'
import { useNow } from '@/lib/use-now'
import { PhoneHeader } from './phone-header'
import { Rail } from './rail'
import { TabBar } from './tab-bar'
import { TopBar } from './top-bar'

/**
 * §4.1–4.2: rail and top bar on desktop; header (with the tempo strip on Live) and tab bar on phone.
 * `<main>` keeps its place in the tree, so crossing the breakpoint swaps the chrome without
 * remounting the page. The root alone keeps everything out of the safe-area insets (index.html
 * sets viewport-fit=cover): a notch, a home indicator, a phone turned sideways, in either layout.
 * The page's one status region sits outside the swapped chrome, so it's there before any news.
 * Each part of the chrome reads its own slice of the live store (src/chrome/live.tsx); the shell
 * follows only the link's status, for that news.
 */
export function AppShell() {
  const isPhone = useIsPhone()
  const meta = usePageMeta()
  const news = useConnectionNews(useConnectionStatus())
  const server = useServerName()

  return (
    <Announcer news={news}>
      <div
        className={cx(
          'h-dvh pt-[env(safe-area-inset-top)] pr-[env(safe-area-inset-right)] pb-[env(safe-area-inset-bottom)] pl-[env(safe-area-inset-left)]',
          isPhone ? 'flex flex-col' : 'grid grid-cols-[var(--rail-w)_minmax(0,1fr)] grid-rows-[var(--topbar-h)_minmax(0,1fr)]',
        )}
      >
        <title>{documentTitle(meta.title)}</title>
        {isPhone ? (
          <PhoneHeader title={meta.phoneTitle ?? meta.title} context={meta.phoneContext && <PageContext get={meta.phoneContext} />}>
            {meta.tempoStrip && <ChromeTempoStrip />}
          </PhoneHeader>
        ) : (
          <>
            <div className="row-span-2">
              <Rail server={server} />
            </div>
            <TopBar title={meta.title} context={meta.context && <PageContext get={meta.context} />} />
          </>
        )}
        <main className="min-h-0 flex-1 overflow-y-auto">
          <Outlet />
        </main>
        {isPhone && <TabBar />}
      </div>
    </Announcer>
  )
}

/** A page's context line. It alone reads the clock, so the minute ticking over redraws just the line. */
function PageContext({ get }: { get: (at: MetaContext) => string }) {
  return get({ now: useNow(), sunset: useSunset() })
}
```

In `web/src/app/page-meta.ts`, drop the `ChromeState` import and change `MetaContext` to this:

```ts
export interface MetaContext {
  now: Date
  /** Today's sunset, 24 h: the fixture until F6 (decision 10). */
  sunset: string
}
```

In `web/src/app/routes.tsx`, the Live line reads the sunset from the context:

```tsx
  phoneContext: ({ now, sunset }) => `${formatDayTime(now)} · sun sets ${sunset}`,
```

`useChrome()` is gone, and `web/src/pages/system.tsx` keeps drawing `HERO_CHROME.tempo` for the specimen. Check that nothing still calls it:

```bash
grep -rn "useChrome\|chrome={" web/src
```

Expected: nothing.

- [ ] **Step 7: Seed the store in the shell's and the app's tests**

Replace `web/src/shell/shell.test.tsx`:

```tsx
import { act, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { liveStore } from '@/api/live-store'
import { attentionAbout, seedLive } from '@/test/live'
import { linkNames, renderAt as at } from '@/test/router'
import { PhoneHeader } from './phone-header'
import { Rail } from './rail'
import { TabBar } from './tab-bar'
import { TopBar } from './top-bar'

describe('Rail', () => {
  it('has the logo, then the six places in order, and the server in the footer', () => {
    seedLive()
    at('/live', <Rail server="homeserver" />)
    const rail = screen.getByRole('navigation', { name: 'Main' })
    expect(linkNames(rail)).toEqual(['', 'Live', 'Looks', 'Map', 'Devices, needs attention', 'Inputs', 'Settings'])
    expect(within(rail).getByRole('link', { name: 'dj-ledfx home' })).toHaveAttribute('href', '/next/live')
    expect(within(rail).getByRole('link', { name: 'Live' })).toHaveAttribute('aria-current', 'page')
    expect(rail).toHaveTextContent('dj-ledfx · homeserver')
  })

  it('marks the section of a nested path as current', () => {
    seedLive()
    at('/devices/tube', <Rail server="homeserver" />)
    const rail = screen.getByRole('navigation', { name: 'Main' })
    expect(within(rail).getByRole('link', { name: 'Devices, needs attention' })).toHaveAttribute('aria-current', 'page')
    expect(within(rail).getByRole('link', { name: 'Live' })).not.toHaveAttribute('aria-current')
  })

  it('puts the dot where the attention is, and nowhere when nothing needs it', () => {
    liveStore.setState({ attention: [attentionAbout('input', 'home-assistant')] })
    at('/live', <Rail server="homeserver" />)
    expect(linkNames(screen.getByRole('navigation'))).toContain('Inputs, needs attention')
    expect(linkNames(screen.getByRole('navigation'))).toContain('Devices')
    act(() => liveStore.setState({ attention: [] }))
    expect(screen.queryByText(', needs attention')).toBeNull()
  })

  it('puts no dot anywhere before the server speaks', () => {
    at('/live', <Rail server="homeserver" />)
    expect(screen.queryByText(', needs attention')).toBeNull()
  })
})

describe('TabBar', () => {
  it('has five tabs, and Tempo opens the phone view of /inputs', () => {
    liveStore.setState({ attention: [attentionAbout('input', 'home-assistant')] })
    at('/inputs', <TabBar />)
    const tabs = screen.getByRole('navigation', { name: 'Main' })
    expect(linkNames(tabs)).toEqual(['Live', 'Looks', 'Devices', 'Tempo, needs attention', 'Settings'])
    const tempo = within(tabs).getByRole('link', { name: 'Tempo, needs attention' })
    expect(tempo).toHaveAttribute('href', '/next/inputs')
    expect(tempo).toHaveAttribute('aria-current', 'page')
  })
})

describe('TopBar', () => {
  it('shows the title, the context and the cluster', () => {
    seedLive()
    at('/live', <TopBar title="Live" context="Wed 23 Sep · 19:14" />)
    const bar = screen.getByRole('banner')
    expect(within(bar).getByRole('heading', { level: 1 })).toHaveTextContent('Live')
    expect(bar).toHaveTextContent('Wed 23 Sep · 19:14')
    expect(within(bar).getByRole('group', { name: 'Tempo' })).toBeInTheDocument()
    expect(within(bar).getByRole('switch', { name: 'Preview only' })).toBeInTheDocument()
    expect(within(bar).getByRole('button', { name: '1 needs attention' })).toBeInTheDocument()
    expect(bar).toHaveTextContent('Live60 fps')
  })

  it('leaves the context out when a page has none', () => {
    at('/settings', <TopBar title="Settings" />)
    // The context line is the title's only sibling.
    expect(screen.getByRole('heading', { level: 1, name: 'Settings' }).nextElementSibling).toBeNull()
  })
})

describe('PhoneHeader', () => {
  it('shows the serif title and context, the eye and the attention count, and no reconnect pill while live', () => {
    seedLive()
    at('/live', <PhoneHeader title="Home" context="Wed 19:14 · sun sets 19:26" />)
    const header = screen.getByRole('banner')
    expect(within(header).getByRole('heading', { level: 1 })).toHaveTextContent('Home')
    expect(within(header).getByRole('heading', { level: 1 })).toHaveClass('font-serif')
    expect(header).toHaveTextContent('Wed 19:14 · sun sets 19:26')
    expect(within(header).getByRole('switch', { name: 'Preview only' })).toBeInTheDocument()
    expect(within(header).getByRole('button', { name: '1 needs attention' })).toBeInTheDocument()
    expect(within(header).queryByText(/Reconnecting/)).toBeNull()
  })

  it('puts the reconnect pill first while reconnecting', () => {
    seedLive()
    liveStore.setState({ connection: { status: 'reconnecting', attempt: 3 } })
    at('/live', <PhoneHeader title="Home" />)
    const pill = screen.getByText('Reconnecting · try 3').parentElement!
    expect(pill).toHaveClass('text-signal')
    expect(pill.compareDocumentPosition(screen.getByRole('switch'))).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
  })

  it('draws its children inside the banner', () => {
    at('/live', (
      <PhoneHeader title="Home">
        <p>strip</p>
      </PhoneHeader>
    ))
    expect(within(screen.getByRole('banner')).getByText('strip')).toBeInTheDocument()
  })
})
```

In `web/src/app/app.test.tsx`:

1. Take `renderApp` from the helper, and seed the hero in the shared `beforeEach`. Change these imports:

```tsx
import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useEffect } from 'react'
import { createMemoryRouter, RouterProvider, type RouteObject } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { setViewportWidth } from '@/test/viewport'
import { routerBasename } from './router'
import { routes } from './routes'
```

to these:

```tsx
import { act, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useEffect } from 'react'
import type { RouteObject } from 'react-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { renderApp } from '@/test/app'
import { seedLive } from '@/test/live'
import { setViewportWidth } from '@/test/viewport'
import { routes } from './routes'
```

2. Delete the local `renderApp` function.

3. Replace the `beforeEach` with this:

```tsx
// The hero moment, with the hero's server already heard; the shared setup puts the real clock back
// and empties the store after each test.
beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(2026, 8, 23, 19, 14))
  seedLive()
})
```

The tests themselves don't change. They still find "121.8", "Devices, needs attention" and "Wed 19:14 · sun sets 19:26", now read from the store.

- [ ] **Step 8: Run the unit tests**

Run: `(cd web && npx vitest run src/chrome/ src/shell/ src/app/ src/pages/)`
Expected: PASS. That is:
- `live.test.tsx`: 5 tests.
- `chrome.test.tsx`: 22 tests.
- `shell.test.tsx`: 10 tests.
- `app.test.tsx` and the rest: as before.

- [ ] **Step 9: Make e2e wait for the data, and hold the beat for the screenshots**

The page now fills in after the socket speaks. In `web/e2e/shell.spec.ts`, `open()` waits for the chrome's first data: the attention count in the banner, and the tempo wherever the chrome shows it. The chrome shows the tempo in the desktop top bar, and in the phone strip on Live. The screenshots hold the beat with `?still`. On desktop they also wait for the measured frame rate, which reaches 60 within about 3 s (decision 3).

Replace `open()`:

```ts
/**
 * Opens a page and waits for the chrome's first data from the mock (the hero, unless the path asks
 * for another scenario): the attention count, and the tempo wherever the chrome shows it.
 */
async function open(page: Page, path: string) {
  await page.goto(path)
  await page.evaluate(() => document.fonts.ready)
  const banner = page.getByRole('banner')
  await expect(banner.getByRole('button', { name: '1 needs attention' })).toBeVisible()
  const phone = (page.viewportSize()?.width ?? 0) < 768
  if (!phone || path.startsWith('/next/live')) {
    await expect(banner.getByRole('group', { name: 'Tempo' })).toBeVisible()
  }
}

/** open(), with the beat held and the frame rate settled, so a screenshot is the same every run. */
async function openStill(page: Page, path: string) {
  await open(page, `${path}?still`)
  if ((page.viewportSize()?.width ?? 0) >= 768) {
    await expect(page.getByRole('banner').getByText('60 fps')).toBeVisible({ timeout: 10_000 })
  }
}
```

The Live screenshot:

```ts
// Done when (spec §13.1 M0): the chrome matches Main.png at 1440 × 900 and Phone-Live.png at 390 × 844.
// Since F1 the chrome is the mock's hero, beat held; the pixels are F0's.
test('Live chrome', async ({ page }) => {
  await openStill(page, '/next/live')
  await expect(page).toHaveScreenshot('live.png')
})
```

The System screenshot:

```ts
  test('System specimen', async ({ page }) => {
    await openStill(page, '/next/system')
    await expect(page.getByText('Always within reach')).toBeVisible()
    await expect(page).toHaveScreenshot('system.png')
  })
```

The other tests keep calling `open()`. The keyboard walk still expects `'Music', 'Tap', 'Preview only', '1 needs attention'`, now from the store. `expectTapInside` still counts 7 Tempo groups on desktop and 6 on phone, because `open()` waits for the top bar's.

- [ ] **Step 10: Run e2e, and keep the screenshots**

Run: `(cd web && npm run e2e 2>&1 | tail -3)`
Expected: `56 passed`, `16 skipped`, with the three committed screenshots matching as they are.

Never pass `--update-snapshots` here. F1 changes where the chrome's values come from, not what it draws. If a screenshot differs, open the diff in `web/test-results/` and find which value changed, then fix that.

- [ ] **Step 11: Gate and commit**

```bash
git add web/src/chrome web/src/shell web/src/app web/src/test/live.ts web/src/test/app.tsx web/src/test/count-renders.ts web/e2e/shell.spec.ts
git commit -m "feat(web): the chrome reads the live store a slice at a time, and claims nothing before the server speaks"
```

---

### Task 13: Done when: 60 fps without re-renders, and the link dropping in the browser

This task implements §13.1 M1's "Done when": "Stores update from the mock at 60 fps without React re-renders (React profiler)". It also covers §14 Resilience in the browser, and §14 Performance's budget. It owns part of review focus 1, the part Playwright pins. Renders: `State-Reconnecting.png`.

**Files:**
- Modify: `web/scripts/check-dist.ts` (the §14 budget)
- Create: `web/e2e/live.spec.ts`
- Test: `web/src/app/live-performance.test.tsx`

**Interfaces:**
- Consumes:
  - From Task 11: `startDataLayer`, `liveClient` and `frames`.
  - From Task 6: `liveStore`.
  - From Task 10: `MockServer` and `inMemorySockets`.
  - From F0: `routes` and `routerBasename`.
  - From Task 12: `HERO_NOW`.
- Produces:
  - Nothing that later tasks call.
  - `npm run build` also fails when the app's JavaScript passes §14's 400 KB gzipped.

- [ ] **Step 1: Read the spec**

Re-read these:
- §13.1's M1 row.
- §14's Resilience and Performance lines.
- §9.4's Reconnecting row.
- Decision 3.

With context7, check React 19's `<Profiler id onRender>`: it calls `onRender` once per commit of its subtree, in development builds too.

- [ ] **Step 2: Write the failing tests**

`web/src/app/live-performance.test.tsx`:

```tsx
import { act, render } from '@testing-library/react'
import { Profiler } from 'react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { frames, liveClient, startDataLayer } from '@/api/live'
import { liveStore } from '@/api/live-store'
import { inMemorySockets } from '@/api/mocks/in-memory-socket'
import { MockServer } from '@/api/mocks/mock-server'
import { HERO_NOW } from '@/test/live'
import { routerBasename } from './router'
import { routes } from './routes'

let server: MockServer | null = null

beforeEach(() => {
  vi.useFakeTimers()
  vi.setSystemTime(HERO_NOW)
})

afterEach(() => {
  liveClient()?.stop()
  server?.stop()
  server = null
})

// Done when (spec §13.1 M1): "Stores update from the mock at 60 fps without React re-renders (React
// profiler)". The hero's beat is held (?still), so for this second the only news is the frames and
// the devices' stats. The app, whole, must commit nothing for either.
it('fills the stores from the mock at 60 fps, and React commits nothing', async () => {
  server = new MockServer({ scenario: 'hero', still: true, clock: () => Date.now(), wallClock: () => Date.now() })
  server.start()
  startDataLayer({ openSocket: inMemorySockets(server), url: 'mock' })
  let commits = 0
  const router = createMemoryRouter(routes, { basename: routerBasename('/next/'), initialEntries: ['/next/live'] })
  render(
    <Profiler id="app" onRender={() => void (commits += 1)}>
      <RouterProvider router={router} />
    </Profiler>,
  )

  // Connect, subscribe, and let the measured frame rate settle (decision 3). Async, because the
  // in-memory socket delivers in microtasks between the timers.
  await act(() => vi.advanceTimersByTimeAsync(3000))
  expect(liveStore.getState().connection).toEqual({ status: 'live', fps: 60 })
  const version = frames.version
  const stats = liveStore.getState().stats
  commits = 0

  await act(() => vi.advanceTimersByTimeAsync(1000))
  // The hero streams to 17 lights: every one of them, about 60 times.
  expect(frames.version - version).toBeGreaterThanOrEqual(59 * 17)
  // The store moved too: the stats arrive once a second.
  expect(liveStore.getState().stats).not.toBe(stats)
  expect(commits).toBe(0)
})
```

`web/e2e/live.spec.ts`:

```ts
import { expect, test } from '@playwright/test'

// Review focus 1 and §14 Resilience, in the browser: the reconnecting scenario drops the link a
// second after it connects, then refuses every retry. The phone header says the same in its pill
// (shell.test.tsx); this needs one project.
test.describe('the link', () => {
  test.skip(({ isMobile }) => isMobile)

  test('says Reconnecting within 2 s of a drop, and counts the retries', async ({ page }) => {
    await page.goto('/next/live?scenario=reconnecting')
    const banner = page.getByRole('banner')
    await expect(banner.getByRole('button', { name: '1 needs attention' })).toBeVisible()
    const connected = Date.now()

    await expect(page.getByRole('status')).toHaveText('Reconnecting')
    // The mock drops the link 1 s after it connects, and §14 allows 2 s from there.
    expect(Date.now() - connected).toBeLessThan(3000)
    await expect(banner.getByText('· try 1')).toBeVisible()
    // The retry 1 s later is refused, so the count moves on.
    await expect(banner.getByText('· try 2')).toBeVisible({ timeout: 5000 })
    // What the server said before it went stays on screen, and nothing claims All good.
    await expect(banner.getByRole('button', { name: '1 needs attention' })).toBeVisible()
  })
})
```

- [ ] **Step 3: Run the unit test**

Run: `(cd web && npx vitest run src/app/live-performance.test.tsx)`
Expected: PASS. Tasks 4 to 12 built what it measures, so it passes the first time. That is the milestone's "done when".

A test that passes the first time must be shown to fail, so break it on purpose:
1. In `web/src/chrome/live.tsx`, make `ChromeConnection` read the whole store instead of its slice: `connection={useLive((state) => state).connection}`, with `useLive` imported from `@/api/live-store`. Now each second's stats message redraws it.
2. Run the test. It must fail on `expect(commits).toBe(0)`.
3. Undo the change and run it again. It passes.

- [ ] **Step 4: Add §14's budget to the build check**

Replace `web/scripts/check-dist.ts`:

```ts
// Fails a build that MSW reached (decision 11), or whose JavaScript passes §14 Performance's budget:
// "first load < 400 KB gzipped JS excluding three.js". It sums every JS file, the lazy chunks too,
// so it's stricter than a first load. F2 excludes three.js's chunk when it adds it. `npm run build`
// runs this over web/dist; pass another directory to check that one.
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { gzipSync } from 'node:zlib'

const MARKERS = ['mockServiceWorker', '[MSW]']
const BUDGET_KB = 400
const dir = resolve(import.meta.dirname, '..', process.argv[2] ?? 'dist')

function files(path: string): string[] {
  return readdirSync(path).flatMap((name) => {
    const full = join(path, name)
    return statSync(full).isDirectory() ? files(full) : [full]
  })
}

const all = files(dir)
const found = all.flatMap((file) => {
  const text = readFileSync(file, 'utf8')
  return MARKERS.filter((marker) => file.includes(marker) || text.includes(marker)).map((marker) => `${file}: ${marker}`)
})
if (found.length > 0) {
  console.error(`MSW reached ${dir}:\n${found.join('\n')}`)
  process.exit(1)
}

const kb = all.filter((file) => file.endsWith('.js')).reduce((sum, file) => sum + gzipSync(readFileSync(file)).length, 0) / 1024
if (kb >= BUDGET_KB) {
  console.error(`${dir}: ${kb.toFixed(1)} KB of gzipped JS, over the ${BUDGET_KB} KB budget (§14)`)
  process.exit(1)
}
console.log(`${dir}: no MSW, ${kb.toFixed(1)} KB of gzipped JS`)
```

Run: `(cd web && npm run build 2>&1 | tail -1)`
Expected: `…/web/dist: no MSW, <n> KB of gzipped JS`, with `<n>` well under 400. Write the number down for the PR body (Task 15).

- [ ] **Step 5: Run the e2e test**

Run: `(cd web && npx playwright test e2e/live.spec.ts)`
Expected: 1 passed, 1 skipped (the phone project).

- [ ] **Step 6: Gate and commit**

Run the gate, and all of e2e: `(cd web && npm run e2e 2>&1 | tail -3)`. Expected: `57 passed`, `17 skipped`.

```bash
git add web/src/app/live-performance.test.tsx web/e2e/live.spec.ts web/scripts/check-dist.ts
git commit -m "test(web): 60 fps from the mock with no React commits, the link dropping in the browser, and the §14 budget"
```

---

### Task 14: Revise CLAUDE.md

CLAUDE.md requires this task: "Add claude md skill as a task to improve and revise claude context, memories etc." The file gains the data layer, its commands and the gotchas this branch found. No design values go in, because CLAUDE.md forbids restating them there.

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Invoke `claude-md-management:revise-claude-md`**

Use it to review what this branch taught. The edits below are the minimum. Keep any other edit it proposes that also follows the no-design-values rule.

- [ ] **Step 2: Commands**

In the `## Commands` code block, replace the `web/` lines for `npm run dev` and `npm run build`, and add three lines after `npm run build`:

```bash
cd web && npm run dev            # Dev server at http://localhost:5174/next/ (proxies /api and /ws to :8080); add ?scenario=<name> to run on the mocks (?still holds the beat, ?protocol=1 speaks as engine M1)
cd web && npm run build          # Type-check and build web/dist; fails if MSW got in or the JS passes §14's budget; FastAPI serves it at /next
cd web && npm run build:mock     # Build web/dist-mock: the app on its mocks (the hero unless ?scenario=), which e2e serves
cd web && npm run api:types      # Regenerate web/src/api/generated/ from the backend's code, after any API change
cd web && npm run api:check      # Fail if the generated types aren't the backend's; `-- --url http://127.0.0.1:8080` also compares a running server (GET only)
```

- [ ] **Step 3: Architecture**

In the `web/` block, replace the `src/chrome/` line and add three lines after it:

```markdown
- `src/chrome/` — the §6.2 always-within-reach cluster; `live.tsx` puts each part on its own slice of the live store (`hooks.ts`) and draws nothing before its data; `state.ts` holds the data types and `HERO_CHROME`, which the specimen draws and which supplies preview only, the server name and the sunset until F3/F6
- `src/api/` — the data layer (§12); components never call `fetch` or touch the socket. `generated/` (the backend's OpenAPI schema and openapi-typescript's types, committed), `contract.ts` (generated aliases, and the pending types later engine milestones serve), `rest.ts` (`api.*`), `live-client.ts` (the one socket: backoff, silence watchdog, resync, frame protocol handshake), `live-store.ts` (zustand; `useLive(selector)`), `frames.ts` (`FrameStore`: reused typed arrays React never watches), `beat.ts` (`BeatClock`), `queries.ts` (TanStack Query), `live.ts` (the app's singletons; `startDataLayer()`)
- `src/api/mocks/` — `MockServer` plays a §12.5 scenario (REST, channels, animated frames) from byte copies of `home.json` and `looks.json`; MSW puts it behind fetch and WebSocket in dev (`?scenario=`) and in `dist-mock`; tests reach it through `inMemorySockets()`
- `scripts/dump_openapi.py` prints the backend's OpenAPI schema from the code, with no server
```

- [ ] **Step 4: Testing and Gotchas**

Append to `## Testing`:

```markdown
- `tests/web/test_openapi_types.py` fails when `web/src/api/generated/openapi.json` isn't the backend's schema; `cd web && npm run api:types` regenerates it
```

In `## Gotchas`, change the line that begins "Web app: `npm run e2e` builds and serves the bundle on :4174". It should begin "Web app: `npm run e2e` builds the mock bundle (`dist-mock`) and serves it on :4174", and the rest of the line stays. Then append:

```markdown
- Web app: a backend API change (a route, a contract model) needs `cd web && npm run api:types` in the same commit, or tests/web/test_openapi_types.py fails; when the backend starts serving a type `contract.ts` wrote by hand, `contract.test.ts` fails `tsc -b` until the hand-written type becomes the generated alias
- Web app: MSW's worker (`web/public/mockServiceWorker.js`) reaches only dev and `dist-mock`; a production build has no public dir, and `scripts/check-dist.ts` fails `npm run build` if MSW gets in
- Web app: the chrome and the pages read the live store a slice at a time (`useLive(selector)`); a selector that builds an object needs `useLiveShallow`, or its component redraws on every message. Frames never go into React state
- Web app: the beat clock and the link's watchdog run on `performance.now()` (`clientNow()`), which Playwright's `page.clock.setFixedTime` leaves running; the mock's times come from `Date`, so a fixed clock still shows the renders' times
- Web app: e2e runs on the mock, so a Playwright test waits for the data (`open()` in e2e/shell.spec.ts), and a screenshot adds `?still` to hold the beat
- Web app: a test running a `MockServer` through `inMemorySockets()` advances fake timers with `await vi.advanceTimersByTimeAsync()`, because the socket delivers in microtasks; `startDataLayer()` stops the client it started before, so there is one socket at a time
- Web app: the shared test setup empties the live store after each test; a component test that needs the server's data seeds it with `seedLive()` from src/test/live.ts
```

- [ ] **Step 5: Check that no design values slipped in**

```bash
git diff CLAUDE.md | grep -nE '^\+.*(#[0-9a-fA-F]{6}|[0-9.]+ ?px|[0-9]+ × [0-9]+)'
```

Expected: no output.

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add the web app's data layer to CLAUDE.md"
```

---

### Task 15: Rebase over master, catch up with engine M2, and open the PR

Engine M2 is planned in parallel and may merge first (Global Constraints). This task brings the branch onto the latest `master`. If M2 is in, the task swaps its pending types for the generated ones, then runs every gate and opens the PR.

**Files:**
- Modify, only if M2 has merged: `web/src/api/generated/*`, `web/src/api/contract.ts`, `web/src/api/rest.ts`, `web/src/api/mocks/*.ts` and their tests.

- [ ] **Step 1: Rebase onto master**

```bash
git fetch origin master && git rebase origin/master
```

The branch hasn't been pushed, so rebasing is safe. If a conflict touches `CLAUDE.md` or `src/dj_ledfx/web/app.py`, keep both sides. Task 1's `include_in_schema=False` must survive in `app.py`.

- [ ] **Step 2: Regenerate the types from the rebased backend**

```bash
test -f src/dj_ledfx/web/router_home.py && echo "M2 merged" || echo "M2 not merged"
uv sync --extra web
(cd web && npm run api:types && git status --short src/api/generated)
uv run pytest tests/web/test_openapi_types.py -q
```

- If M2 has not merged and `git status` shows no change, go to Step 4.
- If the schema changed, whether from M2 or another backend change, commit the regenerated files and go on to Step 3:

```bash
git add web/src/api/generated
git commit -m "chore(web): regenerate the API types from master"
```

- [ ] **Step 3: Swap each pending type the backend now serves for the generated one**

Before Task 1 and Task 2 point here when M2 merged early.

1. Run `(cd web && npx tsc -b 2>&1 | grep -A3 contract.test)`. It names the pending schemas and paths the backend now serves.
2. For each schema it names, say `Home`:
   - Delete the hand-written declaration from `contract.ts`'s pending section.
   - Add `export type Home = Schemas['Home']` to the "Served today" section.
   - Take `'Home'` out of `PendingSchema`.
3. For each path it names:
   - Take the path out of `PendingPath`.
   - Open `paths[path][method]` in `schema.d.ts`. Compare its request body and its answer (the 200 or 201 content) with the `api.*` function in `rest.ts` that calls that path.
   - Where they differ, the generated one is right. Change the function's body type and its `request<T>` answer type to the generated schema.
   - M2 may name a schema differently from §12.2, so step 1's name check can miss it. Read every newly served path's answer, whatever its name.
   - Expect these to arrive this way:
     - `PlacementState`, M2's Spec Ruling 16.
     - The PC's `parts[].id`, Ruling 4.
     - A typed `Light.shape`. Once it's there, `Light` becomes `Schemas['Light']`, and `contract.test.ts` still checks its shape against `LightShape`.
4. Make the mock follow. `(cd web && npx tsc -b && npm test)` shows where its fixtures or replies disagree with the generated types. Change the mock to match them, never the other way round.
5. Check the handshake with `grep -n '"protocol"' src/dj_ledfx/web/ws.py`:
   - M2's `subscribe_frames` ack must carry `"protocol": 2` for a v2 session, as decision 1 says.
   - If it differs, M2 merged first and its handshake wins, as its Spec Ruling 3 says. Change `LiveClient.receiveText`, Task 7's tests and the mock's ack to match.
6. Run `(cd web && npm test && npx tsc -b && npm run lint)`. Then commit:

```bash
git add web/src/api
git commit -m "feat(web): swap engine M2's pending types for the generated ones"
```

If M2 hasn't merged, this step is empty. The M2 plan's last task does the same swap on its side (decision 6), and the PR says so.

- [ ] **Step 4: The whole web gate, from a clean install**

```bash
(cd web && npm ci && npm run api:check && npm test && npx tsc -b && npm run lint && npm run build && npm run e2e)
```

Expected:
- Every step passes.
- `npm run build` ends with `…/web/dist: no MSW, <n> KB of gzipped JS`.
- e2e prints `57 passed` and `17 skipped`.
- The three committed screenshots are unchanged.

The next check is optional and read-only. It compares the deployed server's schema with the committed one. The deployed server runs whatever was last deployed, so a difference is information, not a failure:

```bash
(cd web && npm run api:check -- --url http://127.0.0.1:8080)
```

- [ ] **Step 5: The whole Python gate**

```bash
uv run pytest -q -p no:randomly 2>&1 | tail -1
uv run ruff check .
uv run ruff format --check . 2>&1 | tail -1
uv run mypy src/ 2>&1 | tail -1
```

Expected:
- pytest passes: the baseline count, plus Task 1's 2 tests, plus whatever the rebase brought.
- `ruff check` is clean, and `format --check` has no findings the baseline didn't.
- mypy's count is no higher than the baseline's.

- [ ] **Step 6: Scope and privacy checks**

```bash
git diff --stat origin/master...HEAD -- frontend/ docs/design/
for f in home.json looks.json; do cmp docs/design/web-app/$f web/src/api/mocks/$f || echo "DIFFERS: $f"; done
cmp docs/design/web-app/tokens.css web/src/styles/tokens.css && cmp docs/design/web-app/icons.ts web/src/design/icons.ts && echo "copies identical"
git status --short
```

Expected: no diff under `frontend/` or `docs/design/`, no `DIFFERS`, `copies identical`, and a clean tree.

The repo is public, so check the branch for LAN addresses, MAC addresses and light model names. The model names come from `home.json`, so this plan never has to spell one out:

```bash
git diff origin/master...HEAD -- . ':!web/package-lock.json' | grep -E '^\+' | grep -nE '(192\.168|10\.[0-9]+\.[0-9]+\.[0-9]+|172\.(1[6-9]|2[0-9]|3[01])\.[0-9]+\.[0-9]+)|([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}'
node -e "for (const m of new Set(require('./web/src/api/mocks/home.json').lights.map((l) => l.model))) console.log(m)" > /tmp/f1-models.txt
git diff origin/master...HEAD -- . ':!web/src/api/mocks/home.json' | grep -E '^\+' | grep -nF -f /tmp/f1-models.txt
```

Expected: no output from either. Look at any match by eye. Take out a real address, MAC or model name, and ignore a false alarm, such as a short model name inside another word.

- [ ] **Step 7: Push and open the PR**

Fill in the build's KB figure from Step 4, and whether M2 had merged (Step 2).

```bash
git push -u origin feature/web-f1-data-layer
gh pr create --base master --title "F1: web app data layer" --body-file - <<'EOF'
## Summary

Milestone F1 (the handoff's M1) of the web app rebuild, per docs/superpowers/plans/2026-09-24-f1-data-layer.md.

- `web/src/api/`: types generated from the backend's OpenAPI schema with a drift check (pytest and `npm run api:check`), a REST client, one WebSocket client (backoff, silence watchdog, resync), frame decoders for protocols v1 and v2, a beat clock, and zustand stores that React reads a slice at a time. Frames go to reused typed arrays that React never watches.
- Mocks: a `MockServer` plays every §12.5 scenario, plus preview-only, from byte copies of home.json and looks.json. MSW serves it in dev with `?scenario=`, and in a mock build that Playwright tests. The production build has no MSW; every build checks.
- The chrome's connection, tempo and attention come from the store. Nothing claims "All good", a tempo or "Live" before the server speaks.
- Done when: 60 fps of frames from the mock with zero React commits (src/app/live-performance.test.tsx).
- CLAUDE.md: the data layer, its commands and gotchas.
- Engine M2: <merged before this, and its pending types are swapped for the generated ones | not merged yet; its last task swaps F1's pending types (plan decision 6)>.

## For the owner

The plan's decisions fill gaps in the spec. The ones to check:
- 1: the v2 handshake, the same as M2's Spec Ruling 3.
- 2: the clock offset, and `server_time`'s units for engine M3.
- 8: the mock keeps home.json's "Corridor" where the renders say "Entrance", and State-Nothing-Running's "Start again" has no endpoint yet.
- 10: preview only, the server's name and the sunset stay on the fixture until F3 and F6.

## Test plan

- [x] `cd web && npm test`: the data layer's unit tests, render counts, and 60 fps from the mock with no React commits
- [x] `cd web && npm run api:check` and `uv run pytest tests/web/test_openapi_types.py`: the generated types are the backend's
- [x] `cd web && npm run e2e`: the three screenshots unchanged, now drawn from the mock; axe on every route; the reconnecting scenario
- [x] `cd web && npm run build`: no MSW in dist, <n> KB of gzipped JS against §14's 400
- [x] `uv run pytest`, ruff and mypy: no new findings against the master baseline
- [x] No LAN address, MAC or light model name in the diff

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
```

Expected: `gh` prints the PR's URL. The owner's workflow then runs a @feature-dev:code-architect review and /simplify on the PR (CLAUDE.md). They are not tasks in this plan.

---

## Hand-off

F1 wires the chrome's connection, tempo and attention to the stores (§13.1's M1 row, and the F0 review). The rest is for later milestones. Each item names the F1 piece it builds on.

**F3 (the chrome's rest, and the Running panel)**
- **Pips on the beat clock (§5.4).** Drive the pips from `beatClock.sample(clientNow())` in `requestAnimationFrame`, not from the beat message as F1 does. Hold them still while the link isn't `live`.
  - `?still` stops the mock's beat messages but not the clock's extrapolation. So the screenshot tests must freeze time once the pips run in rAF, for example with Playwright's `page.clock.install()`.
- **TAP.** Add `LiveClient.tap()`, which sends Task 2's `{ action: 'tap', client_time }`. Engine M3 serves it.
- **The tempo source.** Build the popover and the lock (`TempoLock`) through `TempoModule`'s `renderSource`, with data from `queries.inputs()`.
- **Preview only.**
  - Read `useLive((s) => s.previewOnly)`: the `transport` channel already lands there.
  - Write with `api.setPreviewOnly(on)`, holding the new value until the next `transport` message.
  - `usePreviewOnly()`'s fixture goes (decision 10).
- **Attention.**
  - Build the popover (desktop) and the sheet (phone) on `AttentionButton` as the trigger (F0's decision 7), over `useLive((s) => s.attention)`.
  - The item actions: restart is `api.restart(zoneId)`, and details, retry and open go to their pages.
- **The §9.4 Reconnecting card.**
  - "Try now" calls `liveClient()?.retryNow()`.
  - The time of the last frame is `frames.lastFrameAt`.
  - The attempt is in `useConnection()`.
- **"Start again"** (State-Nothing-Running) has no §12.3 endpoint. Raise it with the engine track (decision 8).
- **The Running panel:** `useLive((s) => s.running)`, with `queries.looks()` and `queries.zones()`.

**Sliders (F0 review, for F3's brightness and F4's and F8's controls)**
- Every slider sends throttled updates while it's dragged: at most one request per 100 ms, and always the final value on release.
- It shows its own value while dragged, and the pushed snapshot confirms it.
- F1 adds no slider.

**F2 (the stage)**
- Read `frames.live` in `requestAnimationFrame` whenever `frames.version` has moved. Never copy frames into React state.
- A light's status is `useLive((s) => s.lights)`, and the map is `queries.home()`.
- When three.js arrives, leave its chunk out of `scripts/check-dist.ts`'s sum, since §14's budget excludes it.

**F4 (Put a look on)**
- Previews use `api.startPreview`, `updatePreview` and `stopPreview`, and call `frames.clearPreview()` when one ends.
- F1 subscribes to the live stream only, because engine M2 keeps a preview running while any tab watches its stream (its Spec Ruling 9). So add a `LiveClient` method that re-sends `subscribe_frames` with `streams: ['live', 'preview']` while a preview is open, and without it after.

**F5 and F8 (looks)**
- Read with `queries.looks()` and `queries.look(id)`.
- After a change, call `queryClient.invalidateQueries({ queryKey: ['looks'] })`.

**F6 (devices, inputs, settings)**
- The server's name and today's sunset replace decision 10's fixtures (`useServerName()`, `useSunset()`).
- Inputs come from `useLive((s) => s.inputs)` and `queries.inputs()`, and signals from `liveClient()?.subscribeSignals(names)`.

**F7 (the map)**
- Use `api.home()` and the placement calls. `PlacementState` is the answer (M2's Spec Ruling 16).

**Engine M3**
- Decision 2 assumes two things. Confirm them, or tell F1's owner if they differ:
  - `server_time` is seconds since the Unix epoch, as a float.
  - `beat_in_bar` counts 1–4.

**Every backend change to the API**
- Run `cd web && npm run api:types` in the same commit. Otherwise `tests/web/test_openapi_types.py` fails.

## Coverage

| §13.1 M1, §12, §14 and the F0 review | Task |
|---|---|
| OpenAPI types generated from the backend, and a drift check (committed, and against a running server) | 1 |
| §12.2's types: generated aliases, and M2's, M3's and M6/M7's pending ones | 2 |
| REST client (§12.3) | 3 |
| Frame decoder v1 + v2 (§12.4) | 4 |
| Beat extrapolation and the clock offset (§12.4, §5.4) | 5 |
| zustand stores | 6 |
| WS client: reconnect with backoff (§9.4), resync, no duplicate subscriptions, the v2 handshake | 7 |
| Fixtures from `home.json` and `looks.json`; every §12.5 scenario; attention order (§9.5) | 8 |
| The mock frame generator (§12.5) | 9 |
| MSW handlers and the mock WS (§12.5), speaking v2 and today's M1 protocol | 10 |
| `?scenario=` in dev, the mock build, no MSW in production, TanStack Query, resync of REST data | 11 |
| F0 review: the chrome per slice, and nothing claimed before the first data; §9's first load and Reconnecting | 12 |
| Done when: "Stores update from the mock at 60 fps without React re-renders (React profiler)" | 13 |
| §14 Unit: "frame decoder v1/v2, beat extrapolation, … attention ordering" | 4, 5, 8 |
| §14 Resilience: Reconnecting within 2 s, full resync, no duplicate subscriptions | 7, 13 |
| §14 Performance: < 400 KB gzipped JS | 11, 13 |
| Sliders send throttled updates | Hand-off (F3, F4, F8) |
| CLAUDE.md revised (CLAUDE.md workflow) | 14 |
| Rebase over master, M2's types, PR | 15 |

