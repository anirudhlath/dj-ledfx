# F0 Web App Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the new web app in `web/`, served by FastAPI at `/next`. It gets the handoff's tokens, self-hosted fonts and icons, the §6.1 primitives, the §6.2 always-within-reach cluster, the app shell (rail, top bar, phone header, tab bar) and every §4.3 route as a placeholder.

**Architecture:** `web/` is a fresh Vite + React app beside `frontend/`, which F0 leaves alone. Vite's base is `/next/` and the router's basename is `/next`. The app is styled only through a byte-for-byte copy of the handoff's `tokens.css` (Tailwind v4 `@theme`), and it draws only the handoff's `icons.ts`. A drift test fails if either copy changes. Primitives live in `src/design/`, the cluster in `src/chrome/`, the chrome in `src/shell/`, and routes and per-route page meta in `src/app/`. The chrome reads a static fixture of the spec's hero scenario through `useChrome()`, which F1 and F3 replace with live stores. FastAPI serves `web/dist` at `/next` with an SPA fallback. Those routes are registered before the old UI's catch-all.

**Tech Stack:**
- Vite 8, React 19, TypeScript 5.9 (strict), Tailwind CSS v4 (CSS-first), react-router 7 (data router) and @base-ui/react 1.
- Fontsource for Instrument Sans, Instrument Serif and JetBrains Mono.
- Vitest 5 with jsdom and Testing Library, and Playwright with @axe-core/playwright.
- FastAPI and Starlette on the Python side.

**Spec:** `docs/superpowers/specs/2026-09-23-web-app-rebuild-design.md`, the Claude Design handoff. F0 is its M0 in §13.1; read the reconciliation note above that table. Also read `docs/superpowers/specs/2026-09-23-home-effects-engine-design.md` §10 (how the two tracks meet), and the renders in `/home/anirudhlath/code/private/dj-ledfx/docs/design/web-app/reference/`, which are not in git.

## Global Constraints

Every task's requirements include this section. Quotes are the spec's or CLAUDE.md's own words, with their sections.

**Source of truth**
- CLAUDE.md, "Web App Design": "The Claude Design handoff is the only source of design truth. Don't work from memory, a summary or an earlier conversation."
- Spec §0: the spec "is the source of truth for **behaviour, structure and data**. The reference renders are the source of truth for **look and layout**. When they disagree on behaviour or copy, this document wins. When they disagree on pixels, the renders win".
- CLAUDE.md: "Use `tokens.css`, `icons.ts`, `looks.json` and `home.json` as they are: import them, or copy them byte for byte with a test that fails when the copy differs. Never retype a token, colour, size, icon path or look description, and never restate design values in docs or in this file."
- CLAUDE.md: "Before each web app task, re-read the spec sections and look at the renders that the task names." Each task's first step names them. The renders are only in the main checkout: `/home/anirudhlath/code/private/dj-ledfx/docs/design/web-app/reference/` (`*.png`, and `*.html` pages you can open in a browser).
- CLAUDE.md: "A new handoff replaces `docs/design/web-app/` and the web app spec wholesale. Don't hand-edit the design files."
- The copies `web/src/styles/tokens.css` and `web/src/design/icons.ts` change only by `cp` from `docs/design/web-app/`. Never run a search-and-replace over `web/src` that can reach them. If one does, `cp` them back; Task 1's drift test catches it.
- Where tokens.css has a token for a value, use its utility, never an arbitrary value equal to it. Examples: `text-data`, `text-section`, `text-label`, `rounded-control`, `h-(--touch-min)`, `duration-(--duration-fast)`. Use arbitrary values only for measurements the renders show that have no token.

**Placement and serving** (engine spec §10, and the owner's F0 decisions)
- Engine spec §10: "the new app lives in `web/` and is served at `/next` until it reaches parity. Today's UI keeps working, including M1's look picker, and every F milestone merges to `master` on its own, with no stacked branches. The cut-over (F11) deletes `frontend/` and the old endpoints. This replaces the handoff's "delete `frontend/src`" in F0."
- `frontend/` is not touched in F0.
- Vite's `base` is `/next/`, and the router's basename follows it. The dev server proxies `/api` and `/ws` to :8080, as `frontend/` does.
- Spec §3.2 keeps "FastAPI static serving + SPA fallback in `web/app.py`, Vite dev proxy for `/api` and `/ws`". The file is `src/dj_ledfx/web/app.py`.

**Stack** (spec §3.2–3.3)
- Keep "Vite 8, React 19, TypeScript 5.9 (strict)", "Tailwind CSS v4 (CSS-first `@theme`)" and "react-router 7".
- Keep "@base-ui/react": "Headless, accessible primitives (popover, dialog/sheet, slider, switch, select, tooltip, tabs). We style them ourselves".
- "Add `@fontsource/instrument-sans`, `@fontsource/instrument-serif`, `@fontsource-variable/jetbrains-mono`": "Self-hosted fonts (the server may have no internet)". `tokens.css` imports them itself.
- "Add Playwright (dev) and `@axe-core/playwright`": "Visual and accessibility checks (section 14)".
- "Drop shadcn component copies, `lucide-react`, `next-themes`, Geist font, `sonner`". None of them go into `web/`.
- `zustand`, `@tanstack/react-query`, `openapi-typescript` and `msw` (§3.3) arrive with the data layer in F1, and three.js with the stage in F2. None of them belong in F0.
- Node must be ^22.22.2, ^24.15 or ≥ 26, the floors of Vitest 5 and jsdom 30. Use caret ranges compatible with `frontend/package.json`, with TypeScript pinned `~5.9.3` as there.

**Structure and behaviour**
- §4.1 rail: "logo, then Live, Looks, Map, Devices, Inputs, Settings; a signal dot on Devices or Inputs when something there needs attention". §4.1 top bar: "page title and context on the left; on the right, the always-within-reach cluster: **tempo module**, **Preview only** switch, **Needs attention** button, **connection** indicator."
- §4.2: "A header (page title in serif, context line; right side: preview-only eye button, needs-attention button, and a reconnect indicator when disconnected), a **tempo strip** under it on Live, and a bottom **tab bar**: Live, Looks, Devices, Tempo, Settings. … Leave the top 47 px to the OS (use `env(safe-area-inset-top)`); never draw a fake status bar."
- §4.3: every route in its table exists. §4.4: "< 768 px | Phone layouts (designed at 390 × 844)", "768–1199 px | Desktop structure, … rail stays", "≥ 1200 px | Desktop (designed at 1440 × 900)".
- §5.5: "Build one `<Icon name size />` component. Icon-only buttons always get an `aria-label`. Use the names as given; don't mix in another icon library."
- §6: "Every interactive element is a real `<button>`, `<a>`, `<input>` or base-ui primitive. Touch targets are at least 44 px on phone."
- §5.4: "**Beat-synced motion must follow the real beat clock**, never a CSS timer." F0's pips are still; F3 drives them.
- §1.3: "A light theme. The app is dark only". §2.1: "There is exactly one UI colour, `signal` (orange), and it only ever means "this needs you"."

**Copy** (§10)
- "Words: **look** (never "effect" or "preset" in the UI), **zone**, **light** …, **Off** …, **Stop all**, **Put a look on**, **Preview only**, **Needs attention**."
- "Time: 24 h ("19:14")", "BPM (one decimal …)", "Numbers are mono and tabular.", "Sentence case everywhere except caps labels."

**Quality** (§13.1, §14)
- M0 is done when "Shell matches `Main.png` chrome at 1440 × 900 and `Phone-Live.png` chrome at 390 × 844; axe passes".
- §14 Visual: "Compare against the reference PNGs by eye in review, then commit the app's own screenshots as baselines (the references are guides, not pixel oracles)."
- §14 Accessibility: "`@axe-core/playwright` on every route; … icon buttons labelled; contrast from 5.1 holds."
- §14 Performance: "first load < 400 KB gzipped JS excluding three.js".

**Python and workflow** (CLAUDE.md)
- Use `uv` for everything. Ruff line length is 99 and mypy is strict. "Web tests: `uv sync --extra web` required in worktrees — web tests skip silently without it".
- Never run `uv run ruff format .` over the repo; it rewrites a file F0 doesn't own. Format only the files you touch, and use `--check` for the repo.
- "Use opus for reviewing and simplification stages." "Use haiku for committing." "Use context7 to check latest docs and for external dependencies." "Fix every issue that comes up during the code architect review step." "Fix every issue that comes up during the simplify step."

## Decisions already made

These fill gaps in the spec, and the owner has seen them in the plan's report. Reviewers: don't reverse one without asking.

1. **Copies, not imports, for the design payloads.** `tokens.css` imports the fonts by bare package name, which resolves only from inside `web/`, and Vite and TypeScript both want sources under `web/`. `payload.node.test.ts` compares each copy with the handoff byte for byte, and each handoff file with its `HANDOFF.sha256` pin.
2. **`@import "./tokens.css" theme(static)`** emits every token as a CSS variable, including ones no class uses yet. Later milestones read stage colours at runtime.
3. **`text-size-control`.** tokens.css names both a colour and a font size `control`, and Tailwind resolves `text-control` to the colour. The size gets its own utility.
4. **Normal line height and a pointer cursor.** The reference pages keep the browser's normal line height and give buttons a pointer cursor. `app.css` restores both over Tailwind's preflight; the rail and tab bar then line up with the renders.
5. **Where the renders and §5/§6 disagree on pixels, the renders win (§0):**
   - The phone title uses `text-display-md`, as in Phone-Live.png, not §5.2's compact size.
   - The rail and tab labels, the "BPM" suffix and the rail footer use `text-3` below §5.1's size floor, as drawn.
   - On phone, `Button` sm and md and `IconButton` grow to `--touch-min` with `rounded-tile`, as the phone renders draw them.
6. **The tablet band.** 768–1199 px has no render. It keeps the desktop chrome, and a `tablet:` variant drops the optional text: the tempo source label, "bar 42", the fps, the context line, the separator and the attention label.
7. **Chrome state is a static fixture** of §12.5's hero scenario behind `useChrome()`. F1 and F3 swap in live stores without touching the components. The handlers (`onTap`, `onSourceClick`, `onOpen`, `onChange`) are optional and unwired in F0. The tempo source button and the attention button already declare `aria-haspopup="dialog"` for the popovers F3 attaches.
8. **Data-driven context lines wait for their data.** Header lines that count things ("29 looks · 3 running", "19 lights · 412 LEDs") arrive with that data (F5, F6); F0 shows only the fixed lines.
9. **`/inputs` is Tempo on phone.** §4.2 names that tab Tempo, so the inputs dot sits on the Tempo tab.
10. **Stale tempo** is left to the renders by the spec. For assistive tech, the source reads "…, stale" and the stopped pips leave the accessibility tree.
11. **The logo mark isn't in `icons.ts`.** `logo.tsx` copies it from `reference/Main.html`.
12. **`/system` is an unlinked, lazy-loaded specimen** of the §6.1 primitives and the §6.2 cluster. It exists to compare with System.png and to run axe over every primitive.
13. **Unknown paths and errors stay calm.** An unknown path renders a not-found page inside the shell. A thrown error renders an error page with Reload.
14. **Dates are formatted by hand.** `Intl` in en-GB writes September as "Sept", but the renders write "Sep".
15. **FastAPI caching and errors.**
    - `index.html` is `no-cache`, and hashed assets are cached for a year.
    - A missing asset is a 404, never the index.
    - An unbuilt `web/dist` answers 404 with the build command.
    - The routes stay out of the OpenAPI schema.
    - The old SPA fallback's path traversal is fixed by PR #10, which merges first. The `/next` routes reuse its `_file_within`.
16. **Ports.** The dev server uses 5174 and preview uses 4174, both with `strictPort`, so `frontend/` keeps 5173 and 4173. `--web dev` still starts only `frontend/`.

## Review Focus

1. **`/next` without a trailing slash** (typed or bookmarked) must load the app and land on Live. Pinned in Task 2 (`test_app_paths_get_the_new_index`) and Task 12 (`'%s redirects to Live'`).
2. **Reloading a deep link, mistyping a path, a screen throwing.** Expect, in order: the page itself; a calm not-found page inside the shell, with a way back; a calm error page with Reload, not React Router's developer screen. Pinned in Task 2 (deep paths get the index) and Task 12 (deep link, not-found, error boundary).
3. **A tab left open across a rebuild** asks for an old hashed asset. It must get a 404, so the browser fails cleanly, never `index.html` with a 200. `index.html` itself is never cached. Pinned in Task 2.
4. **Crossing 768 px** (resizing a window, turning a tablet) **and narrow phones.** The chrome must swap in place, without a reload or a remount. From 320 px (the WCAG reflow width) to 1440 px nothing scrolls sideways, and TAP stays inside the tempo strip. Pinned in Task 12 (no remount) and Task 13 (resize, widths, strip).
5. **Clicking the selected Segmented option again.** Base UI's toggle group deselects on a second click, but a segmented control must keep its selection. Pinned in Task 5.

## File Structure

```
web/                                  the new app (F0–F11), beside frontend/
  package.json, package-lock.json     scripts: dev, build, preview, lint, test, e2e
  vite.config.ts                      base /next/, @ alias, dev proxy, Vitest config
  tsconfig.json                       references the two below
  tsconfig.app.json                   src/, except *.node.test.ts
  tsconfig.node.json                  configs, e2e/, *.node.test.ts (Node APIs)
  eslint.config.js, .gitignore, index.html
  playwright.config.ts                desktop and phone projects against vite preview at /next
  e2e/shell.spec.ts                   screenshots, axe on every route, fonts, keyboard, resize, reflow
  e2e/shell.spec.ts-snapshots/        the app's own baselines (committed)
  src/main.tsx                        mounts the router at basename /next
  src/styles/app.css                  the one stylesheet: Tailwind, tokens, a few app-level rules
  src/styles/tokens.css               byte copy of docs/design/web-app/tokens.css
  src/design/                         §6.1 primitives, one file per component family
    icons.ts                          byte copy of docs/design/web-app/icons.ts
    payload.node.test.ts              drift test for both copies
    cx.ts, icon.tsx, button.tsx (Button, ButtonLink, IconButton), switch.tsx, slider.tsx,
    segmented.tsx, select.tsx, field.tsx, chip.tsx (Chip, Tag, Label), toast.tsx,
    overlays.tsx (Tooltip, Popover, Dialog, Sheet)
  src/chrome/                         §6.2 always-within-reach cluster
    state.ts                          ChromeState, the hero fixture, useChrome()
    tempo-module.tsx, preview-only-switch.tsx, attention-button.tsx, connection-indicator.tsx
  src/shell/                          §4.1–4.2 chrome
    logo.tsx, nav.ts, rail.tsx, top-bar.tsx, tab-bar.tsx, phone-header.tsx, app-shell.tsx
  src/app/                            page-meta.ts (per-route titles), routes.tsx (§4.3)
  src/pages/                          placeholder.tsx, not-found.tsx, app-error.tsx, system.tsx
  src/lib/                            format.ts, use-media-query.ts, use-now.ts
  src/test/                           setup.ts, viewport.ts (matchMedia stand-in for jsdom)
src/dj_ledfx/web/app.py               serves web/dist at /next, reusing _file_within from PR #10
tests/web/test_next_static.py
CLAUDE.md                             Commands, Architecture and Gotchas gain web/
```

Tests sit beside the code they test (`*.test.ts(x)`); Playwright specs are in `web/e2e/`.

## Before Task 1

- [ ] **Step 1: Create the worktree from `master`, after the docs PR with the specs has merged**

```bash
git -C /home/anirudhlath/code/private/dj-ledfx fetch origin
git -C /home/anirudhlath/code/private/dj-ledfx worktree add -b feature/web-f0-scaffold /home/anirudhlath/code/.worktrees/dj-ledfx/web-f0 origin/master
W=/home/anirudhlath/code/.worktrees/dj-ledfx/web-f0
cd "$W"
test -f docs/superpowers/specs/2026-09-23-web-app-rebuild-design.md && test -f docs/design/web-app/tokens.css && echo "specs present"
grep -q '^def _file_within' src/dj_ledfx/web/app.py && echo "traversal fix present"
```

Expected: `specs present` and `traversal fix present`. If either is missing, the docs PR or PR #10 (the SPA fallback traversal fix) hasn't merged: stop and tell the owner. Every command in this plan runs from `$W`; commands for the app run in a subshell, `(cd web && …)`.

- [ ] **Step 2: Tools and design files**

```bash
uv sync --extra web
node --version
(cd docs/design/web-app && sha256sum -c --ignore-missing HANDOFF.sha256)
(cd /home/anirudhlath/code/private/dj-ledfx/docs/design/web-app && sha256sum -c --ignore-missing "$W/docs/design/web-app/HANDOFF.sha256" | grep -vc ': OK$')
```

Expected:
- Node is v22.22.2+, v24.15+ or v26+.
- The first check prints `OK` for each payload file.
- The second prints `0`: every render in the main checkout matches its pin.
- If the renders are missing, extract them from `.superpowers/design-handoff/2026-09-23-dj-ledfx-web-handoff.zip` in the main checkout.

- [ ] **Step 3: Record the Python baselines**

```bash
uv run pytest -q -p no:randomly 2>&1 | tail -1
uv run ruff check . && uv run ruff format --check . 2>&1 | tail -1
uv run mypy src/ 2>&1 | tail -1
```

Expected on 2026-09-24's master:
- All tests pass.
- `ruff check` is clean.
- `ruff format --check` flags one file, `src/dj_ledfx/spatial/pipeline_manager.py`, which is pre-existing.
- mypy reports `Found 26 errors in 8 files`, also pre-existing; two of them are in `web/app.py`.

Write the three results down. F0 must not raise any of them. If `master` has moved, record what it says now.

---

### Task 1: Scaffold `web/` with the handoff's tokens, fonts and icons

Implements spec §3.2–3.3 (stack, fonts), §5 ("All values are in `tokens.css`"), §5.5 (`icons.ts`) and CLAUDE.md "Web App Design" (byte copies with a drift test). Render: `System.png`, where the tokens are assembled.

**Files:**
- Create: `web/package.json`, `web/package-lock.json` (npm writes it), `web/vite.config.ts`, `web/tsconfig.json`, `web/tsconfig.app.json`, `web/tsconfig.node.json`, `web/eslint.config.js`, `web/.gitignore`, `web/index.html`, `web/src/main.tsx`, `web/src/styles/app.css`, `web/src/test/setup.ts`
- Create (byte copies, by `cp`): `web/src/styles/tokens.css`, `web/src/design/icons.ts`
- Test: `web/src/design/payload.node.test.ts`

**Interfaces:**
- Consumes: `docs/design/web-app/tokens.css`, `icons.ts`, `HANDOFF.sha256`.
- Produces:
  - The `@/` import alias for `web/src`.
  - npm scripts `dev`, `build`, `preview`, `lint`, `test` and `e2e`.
  - Every utility tokens.css defines (colours such as `bg-raised` and `text-text-3`; sizes such as `text-data` and `text-display-md`; radii such as `rounded-control`; `label-caps`, `num`, `tape`), plus `text-size-control`.
  - `ICONS` and `type IconName` from `@/design/icons`.
  - Vitest on jsdom, with jest-dom matchers and cleanup after each test.

- [ ] **Step 1: Re-read the sources**

Read spec §3.2, §3.3, §5's opening lines and §5.5, the header comment of `docs/design/web-app/tokens.css`, and CLAUDE.md "Web App Design". Look at `System.png`.

- [ ] **Step 2: Check the dependency versions with context7**

Run `resolve-library-id`, then `query-docs`, for vite, react-router, @base-ui/react, tailwindcss, vitest and @playwright/test.
- The ranges below were current on 2026-09-24. They keep the majors the spec names (React Router 7, TypeScript 5.9) and `frontend/`'s ESLint 9.
- Don't move to react-router 8, TypeScript 7 or ESLint 10.
- If a newer minor within these majors carries a breaking note, stop and tell the owner.

- [ ] **Step 3: Write the package and tool configs**

`web/package.json`:

```json
{
  "name": "web",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "lint": "eslint .",
    "test": "vitest run",
    "e2e": "playwright test"
  },
  "dependencies": {
    "@base-ui/react": "^1.8.0",
    "@fontsource-variable/jetbrains-mono": "^5.3.0",
    "@fontsource/instrument-sans": "^5.3.0",
    "@fontsource/instrument-serif": "^5.3.0",
    "react": "^19.3.0",
    "react-dom": "^19.3.0",
    "react-router": "^7.18.4"
  },
  "devDependencies": {
    "@axe-core/playwright": "^4.13.0",
    "@eslint/js": "^9.39.5",
    "@playwright/test": "^1.63.0",
    "@tailwindcss/vite": "^4.3.3",
    "@testing-library/dom": "^10.4.2",
    "@testing-library/jest-dom": "^7.0.1",
    "@testing-library/react": "^16.3.3",
    "@testing-library/user-event": "^14.6.7",
    "@types/node": "^24.13.6",
    "@types/react": "^19.3.0",
    "@types/react-dom": "^19.3.0",
    "@vitejs/plugin-react": "^6.1.1",
    "eslint": "^9.39.5",
    "eslint-plugin-react-hooks": "^7.1.1",
    "eslint-plugin-react-refresh": "^0.5.7",
    "globals": "^17.12.0",
    "jsdom": "^30.1.1",
    "tailwindcss": "^4.3.3",
    "typescript": "~5.9.3",
    "typescript-eslint": "^8.70.1",
    "vite": "^8.3.0",
    "vitest": "^5.0.1"
  }
}
```

`web/vite.config.ts`:

```ts
import { fileURLToPath, URL } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// Served by FastAPI at /next until the F11 cut-over (engine spec §10).
export default defineConfig({
  base: '/next/',
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
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
  },
})
```

`web/tsconfig.json`:

```json
{
  "files": [],
  "references": [{ "path": "./tsconfig.app.json" }, { "path": "./tsconfig.node.json" }]
}
```

`web/tsconfig.app.json`:

```jsonc
{
  "compilerOptions": {
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.app.tsbuildinfo",
    "target": "ES2023",
    "useDefineForClassFields": true,
    "lib": ["ES2023", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "types": ["vite/client", "@testing-library/jest-dom/vitest"],
    "skipLibCheck": true,

    /* Bundler mode */
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "verbatimModuleSyntax": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",

    /* Linting */
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "erasableSyntaxOnly": true,
    "noFallthroughCasesInSwitch": true,
    "noUncheckedSideEffectImports": true,

    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["src"],
  "exclude": ["src/**/*.node.test.ts"]
}
```

`web/tsconfig.node.json`. This covers the Node-side files: the configs, `e2e/`, and `*.node.test.ts`, which read files with `node:fs`.

```jsonc
{
  "compilerOptions": {
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.node.tsbuildinfo",
    "target": "ES2023",
    "lib": ["ES2023", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "types": ["node"],
    "skipLibCheck": true,

    /* Bundler mode */
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "verbatimModuleSyntax": true,
    "moduleDetection": "force",
    "noEmit": true,

    /* Linting */
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "erasableSyntaxOnly": true,
    "noFallthroughCasesInSwitch": true,
    "noUncheckedSideEffectImports": true
  },
  "include": ["vite.config.ts", "playwright.config.ts", "e2e", "src/**/*.node.test.ts"]
}
```

`web/eslint.config.js`. This is `frontend/`'s config, plus Playwright's output folders.

```js
import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import tseslint from 'typescript-eslint'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  globalIgnores(['dist', 'playwright-report', 'test-results']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      tseslint.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
    },
  },
])
```

`web/.gitignore`:

```gitignore
node_modules
dist
test-results
playwright-report
blob-report
*.local
```

`web/index.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
    <meta name="color-scheme" content="dark" />
    <title>dj-ledfx</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 4: Install**

```bash
(cd web && npm install)
```

Expected: `web/package-lock.json` is written and there are no errors.

- [ ] **Step 5: Write the failing drift test and the test setup**

`web/src/test/setup.ts`:

```ts
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(() => {
  cleanup()
})
```

`web/src/design/payload.node.test.ts`:

```ts
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

// CLAUDE.md "Web App Design": the handoff's files are used byte for byte. If this fails, the
// handoff changed or a copy was edited. Copy the file again; never edit either side.
const REPO = resolve(import.meta.dirname, '../../..')
const HANDOFF = 'docs/design/web-app'
const COPIES = [
  { name: 'tokens.css', copy: 'web/src/styles/tokens.css' },
  { name: 'icons.ts', copy: 'web/src/design/icons.ts' },
]

const read = (path: string) => readFileSync(resolve(REPO, path))

describe('design payload copies', () => {
  const pins = read(`${HANDOFF}/HANDOFF.sha256`).toString('utf8')

  for (const { name, copy } of COPIES) {
    it(`${copy} is ${HANDOFF}/${name}, byte for byte`, () => {
      const same = read(copy).equals(read(`${HANDOFF}/${name}`))
      expect(same, `run from the repo root: cp ${HANDOFF}/${name} ${copy}`).toBe(true)
    })

    it(`${HANDOFF}/${name} still matches its HANDOFF.sha256 pin`, () => {
      const hash = createHash('sha256').update(read(`${HANDOFF}/${name}`)).digest('hex')
      expect(pins).toContain(`${hash}  ${name}\n`)
    })
  }
})
```

- [ ] **Step 6: Run it to see it fail**

```bash
(cd web && npm test)
```

Expected: FAIL.
- The two byte-for-byte tests fail with `ENOENT: no such file or directory, open '…/web/src/styles/tokens.css'` and the same error for `icons.ts`.
- The two pin tests pass.

- [ ] **Step 7: Copy the payloads**

```bash
cp docs/design/web-app/tokens.css web/src/styles/tokens.css
cp docs/design/web-app/icons.ts web/src/design/icons.ts
(cd web && npm test)
```

Expected: `Tests  4 passed (4)`.

- [ ] **Step 8: Prove the test catches drift, then restore the copy**

```bash
printf ' ' >> web/src/styles/tokens.css
(cd web && npm test)
cp docs/design/web-app/tokens.css web/src/styles/tokens.css
(cd web && npm test)
```

Expected: the first run fails with `run from the repo root: cp docs/design/web-app/tokens.css web/src/styles/tokens.css`. The second run passes 4 tests.

- [ ] **Step 9: Write the stylesheet and a minimal entry point**

`web/src/styles/app.css`. `tokens.css` imports the fonts itself, so don't add font imports.

```css
/*
 * The app's one stylesheet. Every design value comes from tokens.css, a byte-for-byte copy of
 * docs/design/web-app/tokens.css (src/design/payload.node.test.ts fails if it drifts), which also
 * imports the self-hosted fonts. theme(static) emits every token as a CSS variable, so code can
 * read any token at runtime.
 */
@import "tailwindcss";
@import "./tokens.css" theme(static);

/*
 * tokens.css names both a font size and a colour "control", and Tailwind resolves `text-control` to the
 * colour. This is the font size.
 */
@utility text-size-control {
  font-size: var(--text-control);
  line-height: var(--tw-leading, var(--text-control--line-height));
}

@layer base {
  /* The reference pages keep the browser's normal line height (Tailwind's preflight sets 1.5). */
  html {
    line-height: normal;
  }
  /* The reference pages give buttons a pointer cursor; Tailwind v4's preflight removes it. */
  button:not(:disabled),
  [role="button"]:not(:disabled) {
    cursor: pointer;
  }
}
```

`web/src/main.tsx`. Task 12 replaces this with the router.

```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/app.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <h1 className="p-6 font-serif text-display-lg">dj-ledfx</h1>
  </StrictMode>,
)
```

- [ ] **Step 10: Build and lint**

```bash
(cd web && npm run build && ls dist/assets | grep -c 'woff2$' && grep -c -- '--color-stage-floor' dist/assets/*.css && grep -o '/next/assets/[^"]*' dist/index.html && npm run lint)
```

Expected:
- The build succeeds.
- The woff2 count is non-zero: these are the self-hosted fonts, 17 with the versions above.
- `1`: `theme(static)` emitted a token that no class uses.
- `dist/index.html` loads `/next/assets/index-….js` and `/next/assets/index-….css`.
- Lint prints no problems.

- [ ] **Step 11: Commit**

```bash
git add web
git commit -m "feat: scaffold the new web app with the handoff's tokens, fonts and icons"
```

---

### Task 2: Serve `web/dist` at `/next`

Implements engine spec §10 ("served at `/next` until it reaches parity") and spec §3.2 ("FastAPI static serving + SPA fallback"). No renders.

**Files:**
- Modify `src/dj_ledfx/web/app.py` in three places: new helpers below `_file_within`; one parameter in `create_app`; two routes above the old static block.
- Test: `tests/web/test_next_static.py`

**Interfaces:**
- Consumes: `_file_within(root: Path, relative: str) -> Path | None` from PR #10, already in `web/app.py`. The tests build a fake `dist`.
- Produces:
  - `create_app(..., next_static_dir: Path | None = None)`, which defaults to `<repo>/web/dist`.
  - `GET /next` and `GET /next/{path}`, which serve `web/dist` with an SPA fallback.

The ASGI server decodes `%2e%2e` and `%2f` before routing, so a path like `/next/..%2f..%2fpyproject.toml` would escape `web/dist` if it were joined unchecked. PR #10 fixed the same hole in the old fallback with `_file_within`, and the `/next` routes use it too.

- [ ] **Step 1: Write the failing tests**

`tests/web/test_next_static.py`:

```python
"""F0: the rebuilt web app (web/dist) is served at /next, beside the old UI, until F11."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from dj_ledfx.web.app import create_app

NEW_INDEX = "<!doctype html><title>next</title>"
OLD_INDEX = "<!doctype html><title>old</title>"
SECRET = "not for the web"


def _dist(root: Path, index: str) -> None:
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text(index)
    (root / "assets" / "index-abc123.js").write_text("console.log('built')")
    (root / "favicon.svg").write_text("<svg/>")


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A checkout-like tree: web/dist (new), frontend/dist (old) and a file outside both."""
    (tmp_path / "secret.txt").write_text(SECRET)
    _dist(tmp_path / "web" / "dist", NEW_INDEX)
    _dist(tmp_path / "frontend" / "dist", OLD_INDEX)
    return tmp_path


def _client(tree: Path, next_dir: Path | None = None) -> TestClient:
    app = create_app(
        beat_clock=MagicMock(),
        effect_deck=MagicMock(),
        effect_engine=MagicMock(),
        device_manager=MagicMock(),
        scheduler=MagicMock(),
        preset_store=MagicMock(),
        scene_model=None,
        compositor=None,
        config=MagicMock(web=MagicMock(cors_origins=["*"], static_dir=None)),
        config_path=None,
        web_static_dir=str(tree / "frontend" / "dist"),
        next_static_dir=next_dir or tree / "web" / "dist",
    )
    return TestClient(app)


# Review focus: /next without a trailing slash, and reloaded deep links, load the app.
@pytest.mark.parametrize(
    "path", ["/next", "/next/", "/next/live", "/next/looks/fireflies", "/next/lookz"]
)
def test_app_paths_get_the_new_index(tree: Path, path: str) -> None:
    response = _client(tree).get(path)
    assert response.status_code == 200
    assert response.text == NEW_INDEX
    assert response.headers["cache-control"] == "no-cache"


def test_built_assets_are_served_for_a_year(tree: Path) -> None:
    response = _client(tree).get("/next/assets/index-abc123.js")
    assert response.status_code == 200
    assert response.text == "console.log('built')"
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"


# Review focus: a tab left open across a rebuild asks for an old hash. index.html with a 200
# would break it; a 404 lets the browser fail cleanly.
def test_a_missing_asset_is_a_404_not_the_index(tree: Path) -> None:
    response = _client(tree).get("/next/assets/index-old999.js")
    assert response.status_code == 404


def test_other_files_in_dist_are_served(tree: Path) -> None:
    response = _client(tree).get("/next/favicon.svg")
    assert response.status_code == 200
    assert response.text == "<svg/>"


@pytest.mark.parametrize(
    "path",
    [
        "/next/..%2f..%2fsecret.txt",
        "/next/%2e%2e/%2e%2e/secret.txt",
        "/next/assets/..%2f..%2f..%2fsecret.txt",
    ],
)
def test_next_paths_cannot_leave_dist(tree: Path, path: str) -> None:
    assert SECRET not in _client(tree).get(path).text


def test_the_old_ui_keeps_its_paths(tree: Path) -> None:
    client = _client(tree)
    assert client.get("/").text == OLD_INDEX
    assert client.get("/scene").text == OLD_INDEX
    assert client.get("/assets/index-abc123.js").status_code == 200


def test_an_unbuilt_web_app_says_how_to_build_it(tree: Path) -> None:
    response = _client(tree, next_dir=tree / "missing").get("/next/live")
    assert response.status_code == 404
    assert "npm run build" in response.json()["detail"]
```

- [ ] **Step 2: Run them to see them fail**

```bash
uv run pytest tests/web/test_next_static.py -v -p no:randomly
```

Expected: 13 tests FAIL with `TypeError: create_app() got an unexpected keyword argument 'next_static_dir'`. If they're SKIPPED with "web extra not installed", run `uv sync --extra web` first.

- [ ] **Step 3: Add the helpers**

In `src/dj_ledfx/web/app.py`, insert this directly below `_file_within` (PR #10), after its two trailing blank lines and above `def _resolve_static_dir(`, followed by two blank lines:

```python
# The rebuilt web app (web/), served at /next beside the old UI until the F11 cut-over.
_NEXT_DIST = Path(__file__).resolve().parents[3] / "web" / "dist"
_IMMUTABLE = "public, max-age=31536000, immutable"


def _next_response(dist: Path, path: str) -> FileResponse:
    """A file from web/dist, or its index.html for the app's own routes."""
    index = _file_within(dist, "index.html")
    if index is None:
        raise HTTPException(
            status_code=404, detail="The new web app isn't built: cd web && npm run build"
        )
    if path:
        found = _file_within(dist, path)
        if found is not None:
            cache = _IMMUTABLE if path.startswith("assets/") else "no-cache"
            return FileResponse(found, headers={"Cache-Control": cache})
        if path.startswith("assets/"):
            raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(index, headers={"Cache-Control": "no-cache"})
```

- [ ] **Step 4: Add the parameter**

In `create_app`'s keyword-only parameters, directly after `web_static_dir: str | None = None,`, add:

```python
    next_static_dir: Path | None = None,
```

- [ ] **Step 5: Register `/next` before the old catch-all**

Directly above `static_dir = _resolve_static_dir(web_static_dir, config.web.static_dir)` in `create_app`, insert this, followed by one blank line:

```python
    next_dist = next_static_dir or _NEXT_DIST

    # Registered before the old UI's catch-all below, which would otherwise answer /next.
    @app.get("/next", include_in_schema=False)
    async def next_index() -> FileResponse:
        return _next_response(next_dist, "")

    @app.get("/next/{path:path}", include_in_schema=False)
    async def next_app(path: str) -> FileResponse:
        return _next_response(next_dist, path)
```

- [ ] **Step 6: Run the tests**

```bash
uv run pytest tests/web/test_next_static.py -v -p no:randomly
uv run pytest tests/web -q -p no:randomly
```

Expected: 13 passed, then the whole web suite passes.

- [ ] **Step 7: Lint, format and type-check**

```bash
uv run ruff check src/dj_ledfx/web/app.py tests/web/test_next_static.py
uv run ruff format src/dj_ledfx/web/app.py tests/web/test_next_static.py
uv run mypy src/ 2>&1 | tail -1
```

Expected:
- ruff is clean.
- `2 files left unchanged`.
- mypy prints the same count as the baseline from Before Task 1. The two errors in `app.py` predate F0.

- [ ] **Step 8: Commit**

```bash
git add src/dj_ledfx/web/app.py tests/web/test_next_static.py
git commit -m "feat: serve the new web app at /next"
```

---

### Task 3: `Icon`

Implements spec §5.5 and the render recipe in the header comment of `icons.ts`. Render: `System.png`'s icon grid.

**Files:**
- Create: `web/src/design/cx.ts`, `web/src/design/icon.tsx`
- Test: `web/src/design/icon.test.tsx`

**Interfaces:**
- Consumes: `ICONS` and `IconName` from `./icons` (Task 1).
- Produces:
  - `cx(...classes: Array<string | false | null | undefined>): string`.
  - `Icon({ name, size = 16, strokeWidth = 1.6, className }: IconProps)`, with `IconProps = { name: IconName; size?: number; strokeWidth?: number; className?: string }`. It renders an `aria-hidden` svg that draws `ICONS[name]`.

- [ ] **Step 1: Re-read the sources**

Read spec §5.5 and the first three lines of `web/src/design/icons.ts`. Look at the icon grid in `System.png`.

- [ ] **Step 2: Write the failing test**

`web/src/design/icon.test.tsx`:

```tsx
import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Icon } from './icon'
import { ICONS, type IconName } from './icons'

function payload(name: IconName): string {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
  svg.innerHTML = ICONS[name]
  return svg.innerHTML
}

describe('Icon', () => {
  it('draws the payload for its name, hidden from assistive tech', () => {
    const { container } = render(<Icon name="live" size={20} />)
    const svg = container.querySelector('svg')!
    expect(svg.innerHTML).toBe(payload('live'))
    expect(svg).toHaveAttribute('aria-hidden', 'true')
    expect(svg).toHaveAttribute('width', '20')
    expect(svg).toHaveAttribute('stroke', 'currentColor')
    expect(svg).toHaveAttribute('stroke-width', '1.6')
  })

  it('draws every icon in the handoff', () => {
    const names = Object.keys(ICONS) as IconName[]
    expect(names).toHaveLength(65)
    for (const name of names) {
      const { container, unmount } = render(<Icon name={name} />)
      expect(container.querySelector('svg')!.childElementCount, name).toBeGreaterThan(0)
      unmount()
    }
  })
})
```

- [ ] **Step 3: Run it to see it fail**

```bash
(cd web && npx vitest run src/design/icon.test.tsx)
```

Expected: FAIL with `Failed to resolve import "./icon"`.

- [ ] **Step 4: Implement**

`web/src/design/cx.ts`:

```ts
/** Joins class names, skipping falsy ones. */
export function cx(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(' ')
}
```

`web/src/design/icon.tsx`:

```tsx
import { ICONS, type IconName } from './icons'

export interface IconProps {
  name: IconName
  /** Pixel size of the 24 px grid (spec §5.5). */
  size?: number
  strokeWidth?: number
  className?: string
}

/** One of the handoff's 65 icons, drawn as icons.ts says: stroke currentColor, round caps and joins. */
export function Icon({ name, size = 16, strokeWidth = 1.6, className }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      className={className ? `block shrink-0 ${className}` : 'block shrink-0'}
      dangerouslySetInnerHTML={{ __html: ICONS[name] }}
    />
  )
}
```

- [ ] **Step 5: Run it to see it pass**

```bash
(cd web && npx vitest run src/design/icon.test.tsx && npx tsc -b && npm run lint)
```

Expected: 2 passed; tsc and lint are clean.

- [ ] **Step 6: Commit**

```bash
git add web/src/design/cx.ts web/src/design/icon.tsx web/src/design/icon.test.tsx
git commit -m "feat: add Icon, drawing the handoff's icons as delivered"
```

---

### Task 4: `Button`, `ButtonLink` and `IconButton`

Implements spec §6.1 (`Button`, `IconButton`) and §6's touch-target rule. Renders:
- `System.png`: the buttons.
- `Phone-Live.png`: the "Put a look on" CTA.
- `Phone-State-Nothing-Running.png`: the phone buttons and icon buttons.

**Files:**
- Create: `web/src/design/button.tsx`
- Test: `web/src/design/button.test.tsx`

**Interfaces:**
- Consumes: `cx`, `Icon` and `IconName`.
- Produces:
  - `type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger'`.
  - `type ButtonSize = 'sm' | 'md' | 'lg' | 'cta'`.
  - `Button(props: ButtonProps)`. It takes `variant` (default `'secondary'`), `size` (default `'md'`), `icon`, `trailingIcon`, `className`, `children`, and any `<button>` attribute; `type` defaults to `'button'`.
  - `ButtonLink(props: ButtonLinkProps)`: the same look props on a react-router `Link`.
  - `IconButton({ icon, label, active, ...buttonProps }: IconButtonProps)`. `label` is the accessible name, and `active?: boolean` is exposed as `aria-pressed`.

- [ ] **Step 1: Re-read the sources**

Read spec §6's opening paragraph and the `Button` and `IconButton` rows of §6.1. Look at the buttons in `System.png`, the CTA in `Phone-Live.png` and the buttons in `Phone-State-Nothing-Running.png`.

- [ ] **Step 2: Write the failing test**

`web/src/design/button.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { describe, expect, it, vi } from 'vitest'
import { Button, ButtonLink, IconButton } from './button'

describe('Button', () => {
  it('is a real button that runs its action', async () => {
    const onClick = vi.fn()
    render(<Button onClick={onClick}>Stop all</Button>)
    const button = screen.getByRole('button', { name: 'Stop all' })
    expect(button).toHaveAttribute('type', 'button')
    await userEvent.click(button)
    expect(onClick).toHaveBeenCalledOnce()
  })

  it('draws the variant and size classes', () => {
    render(<Button variant="primary" size="cta" icon="plus">Put a look on</Button>)
    const button = screen.getByRole('button', { name: 'Put a look on' })
    expect(button).toHaveClass('bg-text', 'text-on-text', 'h-13', 'w-full')
    expect(button.querySelector('svg')).toHaveAttribute('width', '18')
  })

  it('grows sm and md to the touch minimum on phone', () => {
    render(
      <>
        <Button size="sm">Stop ripple</Button>
        <Button>Change</Button>
      </>,
    )
    expect(screen.getByRole('button', { name: 'Stop ripple' })).toHaveClass('h-7.5', 'max-md:h-(--touch-min)')
    expect(screen.getByRole('button', { name: 'Change' })).toHaveClass('h-9', 'max-md:h-(--touch-min)')
  })

  it('does nothing while disabled', async () => {
    const onClick = vi.fn()
    render(<Button disabled onClick={onClick}>Restart</Button>)
    await userEvent.click(screen.getByRole('button', { name: 'Restart' }))
    expect(onClick).not.toHaveBeenCalled()
  })

  it('renders as a link when it navigates', () => {
    render(
      <MemoryRouter basename="/next" initialEntries={['/next/looks']}>
        <ButtonLink to="/live" variant="outline">Go to Live</ButtonLink>
      </MemoryRouter>,
    )
    expect(screen.getByRole('link', { name: 'Go to Live' })).toHaveAttribute('href', '/next/live')
  })
})

describe('IconButton', () => {
  it('is named by its label and exposes active as pressed', () => {
    const { rerender } = render(<IconButton icon="plan" label="Plan view" />)
    const button = screen.getByRole('button', { name: 'Plan view' })
    expect(button).not.toHaveAttribute('aria-pressed')
    expect(button).toHaveClass('size-8', 'max-md:size-(--touch-min)')
    rerender(<IconButton icon="plan" label="Plan view" active />)
    expect(button).toHaveAttribute('aria-pressed', 'true')
    expect(button).toHaveClass('bg-text', 'text-on-text')
  })
})
```

- [ ] **Step 3: Run it to see it fail**

```bash
(cd web && npx vitest run src/design/button.test.tsx)
```

Expected: FAIL with `Failed to resolve import "./button"`.

- [ ] **Step 4: Implement**

`web/src/design/button.tsx`:

```tsx
import type { ComponentPropsWithoutRef, ReactNode } from 'react'
import { Link, type LinkProps } from 'react-router'
import { cx } from './cx'
import { Icon } from './icon'
import type { IconName } from './icons'

export type ButtonVariant = 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger'
export type ButtonSize = 'sm' | 'md' | 'lg' | 'cta'

interface ButtonLook {
  variant?: ButtonVariant
  size?: ButtonSize
  icon?: IconName
  trailingIcon?: IconName
  className?: string
  children: ReactNode
}

export type ButtonProps = ButtonLook & Omit<ComponentPropsWithoutRef<'button'>, keyof ButtonLook>
export type ButtonLinkProps = ButtonLook & Omit<LinkProps, keyof ButtonLook>

// §6.1 Button; sizes from System.png. On phone, sm and md grow to the 44 px touch minimum.
const VARIANT: Record<ButtonVariant, string> = {
  primary: 'border-text bg-text text-on-text',
  secondary: 'border-line bg-control text-text hover:bg-control-hover',
  outline: 'border-line-strong bg-transparent text-text hover:bg-control',
  ghost: 'border-transparent bg-transparent text-text-2 hover:bg-control hover:text-text',
  danger: 'border-signal-line bg-transparent text-signal hover:bg-signal-bg',
}

const SIZE: Record<ButtonSize, string> = {
  sm: 'h-7.5 px-2.5 text-data max-md:h-(--touch-min) max-md:rounded-tile max-md:px-3.5 max-md:text-size-control',
  md: 'h-9 px-3.5 text-body max-md:h-(--touch-min) max-md:rounded-tile max-md:text-size-control',
  lg: 'h-12 px-5 text-section',
  cta: 'h-13 w-full px-5 text-section',
}

const ICON_SIZE: Record<ButtonSize, number> = { sm: 16, md: 16, lg: 18, cta: 18 }

function buttonClass(variant: ButtonVariant, size: ButtonSize, className?: string) {
  return cx(
    'inline-flex shrink-0 items-center justify-center gap-2 rounded-control border font-semibold tracking-[0.005em] whitespace-nowrap',
    'transition-colors duration-(--duration-fast) ease-out disabled:pointer-events-none disabled:opacity-45',
    VARIANT[variant],
    SIZE[size],
    className,
  )
}

function Content({ size, icon, trailingIcon, children }: Pick<ButtonLook, 'icon' | 'trailingIcon' | 'children'> & { size: ButtonSize }) {
  return (
    <>
      {icon && <Icon name={icon} size={ICON_SIZE[size]} />}
      {children}
      {trailingIcon && <Icon name={trailingIcon} size={ICON_SIZE[size]} />}
    </>
  )
}

export function Button({ variant = 'secondary', size = 'md', icon, trailingIcon, className, children, type = 'button', ...rest }: ButtonProps) {
  return (
    <button type={type} className={buttonClass(variant, size, className)} {...rest}>
      <Content size={size} icon={icon} trailingIcon={trailingIcon}>{children}</Content>
    </button>
  )
}

/** §6.1: a Button that navigates renders as a link. */
export function ButtonLink({ variant = 'secondary', size = 'md', icon, trailingIcon, className, children, ...rest }: ButtonLinkProps) {
  return (
    <Link className={buttonClass(variant, size, className)} {...rest}>
      <Content size={size} icon={icon} trailingIcon={trailingIcon}>{children}</Content>
    </Link>
  )
}

export interface IconButtonProps extends Omit<ComponentPropsWithoutRef<'button'>, 'children' | 'aria-label' | 'aria-pressed'> {
  icon: IconName
  /** The accessible name. Icon-only buttons always get one (spec §5.5). */
  label: string
  /** §6.1: an active IconButton inverts to the text fill; it's exposed as aria-pressed. */
  active?: boolean
}

export function IconButton({ icon, label, active, className, type = 'button', ...rest }: IconButtonProps) {
  return (
    <button
      type={type}
      aria-label={label}
      aria-pressed={active}
      className={cx(
        'inline-flex size-8 shrink-0 items-center justify-center rounded-control border transition-colors duration-(--duration-fast) ease-out',
        'disabled:pointer-events-none disabled:opacity-45 max-md:size-(--touch-min) max-md:rounded-tile',
        active ? 'border-text bg-text text-on-text' : 'border-line bg-control text-text-2 hover:bg-control-hover hover:text-text max-md:text-text',
        className,
      )}
      {...rest}
    >
      <Icon name={icon} size={16} className="max-md:size-4.5" />
    </button>
  )
}
```

- [ ] **Step 5: Run it to see it pass**

```bash
(cd web && npx vitest run src/design/button.test.tsx && npx tsc -b && npm run lint)
```

Expected: 6 passed; tsc and lint are clean.

- [ ] **Step 6: Commit**

```bash
git add web/src/design/button.tsx web/src/design/button.test.tsx
git commit -m "feat: add Button, ButtonLink and IconButton"
```

---

### Task 5: `Switch`, `Slider` and `Segmented`

Implements spec §6.1 (`Switch`, `Slider`, `Segmented`) and §5.6: when on, the Preview only switch's track turns to tape. Renders:
- `System.png`: the controls.
- `Main.png`: the Preview only switch, off.
- `State-Preview-Only.png`: the switch on, with tape.

**Files:**
- Create: `web/src/design/switch.tsx`, `web/src/design/slider.tsx`, `web/src/design/segmented.tsx`
- Modify: `web/src/styles/app.css` (append the slider's track and thumb)
- Test: `web/src/design/controls.test.tsx`

**Interfaces:**
- Consumes: `cx`, `Icon` and `IconName`.
- Produces:
  - `Switch({ checked, onCheckedChange?, label, tape?, className? })`: a native `<button role="switch">`.
  - `Slider({ label, value, onValueChange, min = 0, max = 100, step = 1, format = String, className? })`: a real `<input type="range">` with a visually hidden label and `aria-valuetext`.
  - `Segmented<T extends string>({ label, value, options: readonly SegmentedOption<T>[], onValueChange, className? })`, with `SegmentedOption<T> = { value: T; label: string; icon?: IconName }`.

- [ ] **Step 1: Re-read the sources**

Read the `Switch`, `Slider` and `Segmented` rows of spec §6.1, and §5.6. Look at the controls in `System.png`, the switch in `Main.png`'s top bar, and the tape track in `State-Preview-Only.png`.

- [ ] **Step 2: Write the failing test**

`web/src/design/controls.test.tsx`. The last test is Review Focus 5.

```tsx
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { Segmented } from './segmented'
import { Slider } from './slider'
import { Switch } from './switch'

describe('Switch', () => {
  it('is a switch that reports the flipped value', async () => {
    const onCheckedChange = vi.fn()
    render(<Switch checked={false} onCheckedChange={onCheckedChange} label="Preview only" tape />)
    const control = screen.getByRole('switch', { name: 'Preview only' })
    expect(control).toHaveAttribute('aria-checked', 'false')
    await userEvent.click(control)
    expect(onCheckedChange).toHaveBeenCalledWith(true)
  })

  it('draws tape on the track only when on', () => {
    const { container, rerender } = render(<Switch checked={false} label="Preview only" tape />)
    expect(container.querySelector('.tape')).toBeNull()
    rerender(<Switch checked label="Preview only" tape />)
    expect(screen.getByRole('switch')).toHaveAttribute('aria-checked', 'true')
    expect(container.querySelector('.tape')).not.toBeNull()
  })
})

describe('Slider', () => {
  it('is a labelled range input whose value reads as its readout', () => {
    const onValueChange = vi.fn()
    render(<Slider label="Brightness" value={70} onValueChange={onValueChange} format={(v) => `${v}%`} />)
    const slider = screen.getByRole('slider', { name: 'Brightness' })
    expect(slider).toHaveAttribute('aria-valuetext', '70%')
    expect(slider).toHaveStyle({ '--v': '70%' })
    fireEvent.change(slider, { target: { value: '40' } })
    expect(onValueChange).toHaveBeenCalledWith(40)
  })

  it('fills the share of its own range', () => {
    render(<Slider label="Height" value={1.5} min={1} max={3} step={0.1} onValueChange={() => {}} />)
    expect(screen.getByRole('slider', { name: 'Height' })).toHaveStyle({ '--v': '25%' })
  })
})

function View() {
  const [view, setView] = useState<'3d' | 'plan'>('3d')
  return (
    <>
      <Segmented
        label="View"
        value={view}
        options={[
          { value: '3d', label: '3D', icon: 'cube' },
          { value: 'plan', label: 'Plan', icon: 'plan' },
        ]}
        onValueChange={setView}
      />
      <output>{view}</output>
    </>
  )
}

describe('Segmented', () => {
  it('selects the clicked option', async () => {
    render(<View />)
    expect(screen.getByRole('button', { name: '3D' })).toHaveAttribute('aria-pressed', 'true')
    await userEvent.click(screen.getByRole('button', { name: 'Plan' }))
    expect(screen.getByRole('button', { name: 'Plan' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: '3D' })).toHaveAttribute('aria-pressed', 'false')
  })

  // Review focus: clicking the selected option again must not leave nothing selected.
  it('keeps the selection when the selected option is clicked again', async () => {
    render(<View />)
    await userEvent.click(screen.getByRole('button', { name: '3D' }))
    expect(screen.getByRole('button', { name: '3D' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('status')).toHaveTextContent('3d')
  })
})
```

- [ ] **Step 3: Run it to see it fail**

```bash
(cd web && npx vitest run src/design/controls.test.tsx)
```

Expected: FAIL with `Failed to resolve import "./segmented"`.

- [ ] **Step 4: Implement**

`web/src/design/switch.tsx`:

```tsx
import { cx } from './cx'

export interface SwitchProps {
  checked: boolean
  onCheckedChange?: (checked: boolean) => void
  label: string
  /** §5.6: the track turns to tape when on. Only Preview only uses it. */
  tape?: boolean
  className?: string
}

/** §6.1 Switch: a native button with role="switch". */
export function Switch({ checked, onCheckedChange, label, tape = false, className }: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onCheckedChange?.(!checked)}
      className={cx('inline-flex items-center gap-2.5', className)}
    >
      <span
        aria-hidden="true"
        className={cx(
          'relative inline-block h-5 w-8.5 shrink-0 rounded-pill border transition-colors duration-(--duration-fast) ease-out',
          !checked && 'border-line bg-control-hover',
          checked && (tape ? 'tape border-text' : 'border-text bg-text'),
        )}
      >
        <span
          className={cx(
            'absolute top-0.5 size-3.5 rounded-full shadow-[0_1px_2px_rgb(0_0_0/0.5)] transition-[left] duration-(--duration-fast) ease-out',
            checked ? 'left-4 bg-on-text' : 'left-0.5 bg-text-2',
          )}
        />
      </span>
      <span className={cx('text-size-control font-medium', checked ? 'text-text' : 'text-text-2')}>{label}</span>
    </button>
  )
}
```

`web/src/design/slider.tsx`:

```tsx
import { useId, type CSSProperties } from 'react'
import { cx } from './cx'

export interface SliderProps {
  label: string
  value: number
  onValueChange: (value: number) => void
  min?: number
  max?: number
  step?: number
  /** The readout and the value read to assistive tech, e.g. (v) => `${v}%`. */
  format?: (value: number) => string
  className?: string
}

/** §6.1 Slider: a real range input with a mono readout on the right. */
export function Slider({ label, value, onValueChange, min = 0, max = 100, step = 1, format = String, className }: SliderProps) {
  const id = useId()
  const text = format(value)
  const fill = { '--v': `${((value - min) / (max - min)) * 100}%` } as CSSProperties
  return (
    <div className={cx('flex items-center gap-2.5', className)}>
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        aria-valuetext={text}
        onChange={(event) => onValueChange(event.currentTarget.valueAsNumber)}
        className="slider min-w-0 flex-1"
        style={fill}
      />
      <span aria-hidden="true" className="num min-w-9 text-right text-meta text-text-2">
        {text}
      </span>
    </div>
  )
}
```

`web/src/design/segmented.tsx`:

```tsx
import { Toggle } from '@base-ui/react/toggle'
import { ToggleGroup } from '@base-ui/react/toggle-group'
import { cx } from './cx'
import { Icon } from './icon'
import type { IconName } from './icons'

export interface SegmentedOption<T extends string> {
  value: T
  label: string
  icon?: IconName
}

export interface SegmentedProps<T extends string> {
  /** Names the group for assistive tech. */
  label: string
  value: T
  options: readonly SegmentedOption<T>[]
  onValueChange: (value: T) => void
  className?: string
}

/** §6.1 Segmented: exactly one option is always selected. */
export function Segmented<T extends string>({ label, value, options, onValueChange, className }: SegmentedProps<T>) {
  return (
    <ToggleGroup
      aria-label={label}
      value={[value]}
      onValueChange={(next) => {
        // Base UI deselects on a second click; a segmented control never ends up empty.
        const picked = next[0] as T | undefined
        if (picked !== undefined) onValueChange(picked)
      }}
      className={cx('inline-flex gap-0.5 rounded-control border border-line bg-raised p-0.5', className)}
    >
      {options.map((option) => (
        <Toggle
          key={option.value}
          value={option.value}
          className="inline-flex h-6.5 items-center gap-1.5 rounded-chip px-2.75 text-data font-semibold text-text-3 transition-colors duration-(--duration-fast) ease-out hover:text-text-2 data-[pressed]:bg-control-hover data-[pressed]:text-text"
        >
          {option.icon && <Icon name={option.icon} size={15} />}
          {option.label}
        </Toggle>
      ))}
    </ToggleGroup>
  )
}
```

Append to `web/src/styles/app.css`, after one blank line. A range input's track and thumb can only be styled with pseudo-elements, so they live in CSS.

```css
/* §6.1 Slider: a real range input. <Slider> sets --v to the filled share. */
@layer components {
  .slider {
    appearance: none;
    background: transparent;
    height: 20px;
    margin: 0;
    cursor: pointer;
  }
  .slider::-webkit-slider-runnable-track {
    height: 4px;
    border-radius: 2px;
    background: linear-gradient(
      to right,
      var(--color-text) 0 var(--v),
      var(--color-control-hover) var(--v) 100%
    );
  }
  .slider::-webkit-slider-thumb {
    appearance: none;
    width: 14px;
    height: 14px;
    margin-top: -5px;
    border-radius: 50%;
    background: var(--color-text);
    box-shadow: 0 0 0 3px var(--color-bg);
  }
  .slider::-moz-range-track {
    height: 4px;
    border-radius: 2px;
    background: linear-gradient(
      to right,
      var(--color-text) 0 var(--v),
      var(--color-control-hover) var(--v) 100%
    );
  }
  .slider::-moz-range-thumb {
    width: 14px;
    height: 14px;
    border: 0;
    border-radius: 50%;
    background: var(--color-text);
  }
}
```

- [ ] **Step 5: Run it to see it pass**

```bash
(cd web && npx vitest run src/design/controls.test.tsx && npx tsc -b && npm run lint)
```

Expected: 6 passed; tsc and lint are clean. If "keeps the selection when the selected option is clicked again" fails, the `picked !== undefined` guard in `Segmented` is missing.

- [ ] **Step 6: Commit**

```bash
git add web/src/design/switch.tsx web/src/design/slider.tsx web/src/design/segmented.tsx web/src/design/controls.test.tsx web/src/styles/app.css
git commit -m "feat: add Switch, Slider and Segmented"
```

---

### Task 6: `Select` and `Field`

Implements the `SelectTrigger` and `Field` rows of spec §6.1. Renders: `System.png`, and `Settings.png` for fields and selects in use.

**Files:**
- Create: `web/src/design/select.tsx`, `web/src/design/field.tsx`
- Test: `web/src/design/inputs.test.tsx`

**Interfaces:**
- Consumes: `cx` and `Icon`.
- Produces:
  - `Select<T extends string>({ label, value, items: Record<T, string>, onValueChange, className? })`. The trigger has `role="combobox"` and is named by `label`; the list comes from Base UI.
  - `Field({ label, unit?, className?, ...inputProps })`: a labelled `<input>` with an optional unit suffix.

- [ ] **Step 1: Re-read the sources**

Read the `SelectTrigger` and `Field` rows of spec §6.1. Look at `System.png`, and at the selects and fields in `Settings.png`.

- [ ] **Step 2: Write the failing test**

`web/src/design/inputs.test.tsx`:

```tsx
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { Field } from './field'
import { Select } from './select'

const TRANSITIONS = { cut: 'Cut', fade: 'Fade · 1 s', dissolve: 'Dissolve · 3 s' }

function Transition() {
  const [value, setValue] = useState<keyof typeof TRANSITIONS>('dissolve')
  return (
    <>
      <Select label="Transition" value={value} items={TRANSITIONS} onValueChange={setValue} />
      <output>{value}</output>
    </>
  )
}

describe('Select', () => {
  it('shows the label of the current value and picks another', async () => {
    render(<Transition />)
    const trigger = screen.getByRole('combobox', { name: 'Transition' })
    expect(trigger).toHaveTextContent('Dissolve · 3 s')
    await userEvent.click(trigger)
    await userEvent.click(await screen.findByRole('option', { name: 'Cut' }))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('cut'))
    expect(trigger).toHaveTextContent('Cut')
  })
})

describe('Field', () => {
  it('labels its input and shows the unit', async () => {
    const onChange = vi.fn()
    render(<Field label="Height" unit="m" defaultValue="1.20" onChange={onChange} />)
    const input = screen.getByLabelText('Height')
    expect(input).toHaveValue('1.20')
    expect(screen.getByText('m')).toBeInTheDocument()
    await userEvent.type(input, '5')
    expect(onChange).toHaveBeenCalled()
  })
})
```

- [ ] **Step 3: Run it to see it fail**

```bash
(cd web && npx vitest run src/design/inputs.test.tsx)
```

Expected: FAIL with `Failed to resolve import "./field"`.

- [ ] **Step 4: Implement**

`web/src/design/select.tsx`:

```tsx
import { Select as BaseSelect } from '@base-ui/react/select'
import { cx } from './cx'
import { Icon } from './icon'

export interface SelectProps<T extends string> {
  /** The accessible name of the trigger. */
  label: string
  value: T
  /** Value → label, in display order. */
  items: Record<T, string>
  onValueChange: (value: T) => void
  className?: string
}

/** §6.1 SelectTrigger, opening a Base UI select list. */
export function Select<T extends string>({ label, value, items, onValueChange, className }: SelectProps<T>) {
  return (
    <BaseSelect.Root
      items={items}
      value={value}
      onValueChange={(next) => {
        if (next !== null) onValueChange(next as T)
      }}
    >
      <BaseSelect.Trigger
        aria-label={label}
        className={cx(
          'inline-flex h-8 min-w-0 items-center justify-between gap-2 rounded-control border border-line bg-control px-2.5 text-size-control font-medium text-text',
          className,
        )}
      >
        <BaseSelect.Value className="truncate" />
        <Icon name="down" size={14} className="text-text-3" />
      </BaseSelect.Trigger>
      <BaseSelect.Portal>
        <BaseSelect.Positioner sideOffset={4} alignItemWithTrigger={false} className="z-50">
          <BaseSelect.Popup className="min-w-(--anchor-width) rounded-card border border-line-strong bg-raised py-1 shadow-pop outline-none">
            <BaseSelect.List>
              {(Object.keys(items) as T[]).map((key) => (
                <BaseSelect.Item
                  key={key}
                  value={key}
                  className="flex h-8 cursor-pointer items-center justify-between gap-6 px-2.5 text-size-control text-text-2 outline-none select-none data-[highlighted]:bg-control data-[highlighted]:text-text data-[selected]:text-text"
                >
                  <BaseSelect.ItemText>{items[key]}</BaseSelect.ItemText>
                  <BaseSelect.ItemIndicator>
                    <Icon name="check" size={14} />
                  </BaseSelect.ItemIndicator>
                </BaseSelect.Item>
              ))}
            </BaseSelect.List>
          </BaseSelect.Popup>
        </BaseSelect.Positioner>
      </BaseSelect.Portal>
    </BaseSelect.Root>
  )
}
```

`web/src/design/field.tsx`:

```tsx
import { useId, type ComponentPropsWithoutRef } from 'react'
import { cx } from './cx'

export interface FieldProps extends Omit<ComponentPropsWithoutRef<'input'>, 'id' | 'className'> {
  label: string
  /** A unit suffix, e.g. "m" or "ms". */
  unit?: string
  className?: string
}

/** §6.1 Field: a label above a 32 px box holding a mono value and an optional unit. */
export function Field({ label, unit, className, ...input }: FieldProps) {
  const id = useId()
  return (
    <div className={cx('flex flex-col gap-1.25', className)}>
      <label htmlFor={id} className="text-[11.5px] font-medium text-text-3">
        {label}
      </label>
      <div className="flex h-8 items-center gap-1.5 rounded-control border border-line bg-control px-2.5 focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-text">
        <input id={id} className="num min-w-0 flex-1 bg-transparent text-size-control text-text outline-none" {...input} />
        {unit && <span className="text-meta text-text-3">{unit}</span>}
      </div>
    </div>
  )
}
```

- [ ] **Step 5: Run it to see it pass**

```bash
(cd web && npx vitest run src/design/inputs.test.tsx && npx tsc -b && npm run lint)
```

Expected: 2 passed; tsc and lint are clean.

- [ ] **Step 6: Commit**

```bash
git add web/src/design/select.tsx web/src/design/field.tsx web/src/design/inputs.test.tsx
git commit -m "feat: add Select and Field"
```

---

### Task 7: `Chip`, `Tag`, `Label` and `Toast`

Implements spec §6.1 (`Chip`, `Label`, `Tag`, `Toast`) and §5.1's rule that the doorbell card "uses the ring's gold because it is showing the look's colour, not a UI accent". Renders:
- `System.png`.
- `Live-Doorbell.png`: the toast.
- `Main.png`: the tags on the stage.

**Files:**
- Create: `web/src/design/chip.tsx` (Chip, Tag, Label), `web/src/design/toast.tsx`
- Test: `web/src/design/display.test.tsx`

**Interfaces:**
- Consumes: `cx`, `Icon` and `IconName`.
- Produces:
  - `type ChipVariant = 'input' | 'mod' | 'quiet' | 'signal' | 'solid'` and `type TagVariant = 'plain' | 'signal' | 'solid'`.
  - `Chip({ variant = 'input', icon?, children, className? })` and `Tag({ variant = 'plain', icon?, children, className? })`.
  - `Label({ children, className? })`, which uses tokens.css's `label-caps`.
  - `Toast({ title, detail?, readout?, icon?, tint?, action? })`: a `role="status"` pill. `tint` is a light's colour and tints the border and the readout.

- [ ] **Step 1: Re-read the sources**

Read the `Chip`, `Label`, `Tag` and `Toast` rows of spec §6.1, and §5.1's rules. Look at `System.png`, the doorbell toast in `Live-Doorbell.png`, and the tags on the stage in `Main.png`.

- [ ] **Step 2: Write the failing test**

`web/src/design/display.test.tsx`:

```tsx
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Chip, Label, Tag } from './chip'
import { Toast } from './toast'

describe('Chip, Tag and Label', () => {
  it('draw their variants', () => {
    render(
      <>
        <Chip variant="signal" icon="music">Music · 42 s</Chip>
        <Tag variant="plain">OFFLINE</Tag>
        <Label>Running</Label>
      </>,
    )
    expect(screen.getByText('Music · 42 s')).toHaveClass('bg-signal-bg', 'text-signal', 'h-5.5')
    expect(screen.getByText('Music · 42 s').querySelector('svg')).toHaveAttribute('width', '13')
    expect(screen.getByText('OFFLINE')).toHaveClass('bg-bg/88', 'h-6.5')
    expect(screen.getByText('Running')).toHaveClass('label-caps')
  })
})

describe('Toast', () => {
  it('is a polite status tinted by the light it is about', () => {
    render(<Toast icon="bell" title="Doorbell" detail="Front door · 19:16" readout="1.8 s" tint="rgb(255, 207, 92)" />)
    const toast = screen.getByRole('status')
    expect(toast).toHaveTextContent('DoorbellFront door · 19:161.8 s')
    expect(toast.style.borderColor).toContain('rgb(255, 207, 92)')
    expect(screen.getByText('1.8 s')).toHaveStyle({ color: 'rgb(255, 207, 92)' })
  })

  it('keeps the neutral border and readout without a tint', () => {
    render(<Toast title="Saved" readout="2 s" />)
    expect(screen.getByRole('status').getAttribute('style')).toBeNull()
    expect(screen.getByText('2 s').getAttribute('style')).toBeNull()
  })
})
```

- [ ] **Step 3: Run it to see it fail**

```bash
(cd web && npx vitest run src/design/display.test.tsx)
```

Expected: FAIL with `Failed to resolve import "./chip"`.

- [ ] **Step 4: Implement**

`web/src/design/chip.tsx`:

```tsx
import type { ReactNode } from 'react'
import { cx } from './cx'
import { Icon } from './icon'
import type { IconName } from './icons'

export type ChipVariant = 'input' | 'mod' | 'quiet' | 'signal' | 'solid'
export type TagVariant = 'plain' | 'signal' | 'solid'

const CHIP: Record<ChipVariant, string> = {
  input: 'border-line bg-control text-text-2',
  mod: 'border-line-strong bg-transparent text-text-2',
  quiet: 'border-line bg-transparent text-text-3',
  signal: 'border-signal-line bg-signal-bg text-signal',
  solid: 'border-text bg-text text-on-text',
}

const TAG: Record<TagVariant, string> = {
  plain: 'border-line bg-bg/88 text-text',
  signal: 'border-signal-line bg-signal-ink/92 text-signal',
  solid: 'border-text bg-text text-on-text',
}

interface BadgeProps {
  icon?: IconName
  children: ReactNode
  className?: string
}

/** §6.1 Chip: inputs a look uses, modifiers, states. */
export function Chip({ variant = 'input', icon, children, className }: BadgeProps & { variant?: ChipVariant }) {
  return (
    <span
      className={cx(
        'inline-flex h-5.5 items-center gap-1.25 rounded-pill border px-2 text-[11.5px] font-semibold whitespace-nowrap',
        CHIP[variant],
        className,
      )}
    >
      {icon && <Icon name={icon} size={13} strokeWidth={1.8} />}
      {children}
    </span>
  )
}

/** §6.1 Tag: a pill drawn on the stage. */
export function Tag({ variant = 'plain', icon, children, className }: BadgeProps & { variant?: TagVariant }) {
  return (
    <span
      className={cx(
        'inline-flex h-6.5 items-center gap-1.5 rounded-pill border px-2.25 text-[11.5px] font-bold tracking-[0.03em] whitespace-nowrap',
        TAG[variant],
        className,
      )}
    >
      {icon && <Icon name={icon} size={13} strokeWidth={1.8} />}
      {children}
    </span>
  )
}

/** §6.1 Label: 11/600 caps (the label-caps utility from tokens.css). */
export function Label({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cx('label-caps', className)}>{children}</span>
}
```

`web/src/design/toast.tsx`:

```tsx
import type { ReactNode } from 'react'
import { Icon } from './icon'
import type { IconName } from './icons'

export interface ToastProps {
  title: string
  detail?: string
  /** A short mono value on the right, e.g. "1.8 s". */
  readout?: string
  icon?: IconName
  /**
   * The colour of the light the moment is about (the doorbell uses the ring's gold). It tints the
   * border and the readout; the UI adds no colour of its own (spec §5.1).
   */
  tint?: string
  action?: ReactNode
}

/** §6.1 Toast: a 44 px pill for moments, not errors. Announced politely. */
export function Toast({ title, detail, readout, icon, tint, action }: ToastProps) {
  return (
    <div
      role="status"
      className="inline-flex h-11 items-center gap-3 rounded-pill border border-line-strong bg-raised/95 pr-2 pl-3.5 whitespace-nowrap shadow-tip"
      // Live-Doorbell.png: the border is the tint mixed about a third into bg.
      style={tint ? { borderColor: `color-mix(in srgb, ${tint} 32%, var(--color-bg))` } : undefined}
    >
      {icon && <Icon name={icon} size={16} />}
      <span className="text-size-control font-semibold">{title}</span>
      {detail && <span className="text-data text-text-2">{detail}</span>}
      {readout && (
        <span className="num text-meta" style={tint ? { color: tint } : undefined}>
          {readout}
        </span>
      )}
      {action}
    </div>
  )
}
```

- [ ] **Step 5: Run it to see it pass**

```bash
(cd web && npx vitest run src/design/display.test.tsx && npx tsc -b && npm run lint)
```

Expected: 3 passed; tsc and lint are clean.

- [ ] **Step 6: Commit**

```bash
git add web/src/design/chip.tsx web/src/design/toast.tsx web/src/design/display.test.tsx
git commit -m "feat: add Chip, Tag, Label and Toast"
```

---

### Task 8: `Tooltip`, `Popover`, `Dialog` and `Sheet`

Implements the `Tooltip` and `Popover / Dialog / Sheet` rows of spec §6.1. Renders:
- `System.png`.
- `State-Problems.png`: a popover anchored under its button.
- `Phone-State-Problems.png`: a sheet with its grabber.

**Files:**
- Create: `web/src/design/overlays.tsx`
- Test: `web/src/design/overlays.test.tsx`

**Interfaces:**
- Consumes: `IconButton`, which is the Dialog's Close button.
- Produces:
  - `Tooltip({ content, children, side = 'top' })`. `children` is the trigger element. It is visual only, so icon-only triggers keep their `aria-label`.
  - `Popover({ trigger, title, children?, open?, onOpenChange?, align = 'center' })`.
  - `Dialog({ trigger, title, children?, open?, onOpenChange? })`.
  - `Sheet({ trigger, title, children?, open?, onOpenChange? })`.
  - `trigger` is the element that opens the overlay (Base UI wires its events and ARIA). `title` names the overlay and heads it.

- [ ] **Step 1: Re-read the sources**

Read the `Tooltip` and `Popover / Dialog / Sheet` rows of spec §6.1. Look at the overlays in `System.png`, the popover in `State-Problems.png` and the sheet in `Phone-State-Problems.png`.

- [ ] **Step 2: Write the failing test**

`web/src/design/overlays.test.tsx`:

```tsx
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { Button } from './button'
import { Dialog, Popover, Sheet, Tooltip } from './overlays'

describe('overlays', () => {
  it('Tooltip shows on keyboard focus', async () => {
    render(
      <Tooltip content="Fit the home">
        <button type="button" aria-label="Fit">x</button>
      </Tooltip>,
    )
    await userEvent.tab()
    expect(await screen.findByText('Fit the home')).toBeVisible()
  })

  it('Popover opens as a named dialog and closes on Escape', async () => {
    render(
      <Popover trigger={<Button>Open</Button>} title="Needs attention">
        <p>Rope is offline</p>
      </Popover>,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Open' }))
    expect(await screen.findByRole('dialog', { name: 'Needs attention' })).toBeInTheDocument()
    await userEvent.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('Dialog closes from its Close button and returns focus', async () => {
    render(
      <Dialog trigger={<Button>Restore</Button>} title="Restore from a file">
        <p>Everything is replaced.</p>
      </Dialog>,
    )
    const opener = screen.getByRole('button', { name: 'Restore' })
    await userEvent.click(opener)
    expect(await screen.findByRole('dialog', { name: 'Restore from a file' })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Close' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(opener).toHaveFocus()
  })

  it('Sheet opens as a named dialog', async () => {
    render(
      <Sheet trigger={<Button>Where</Button>} title="Put a look on">
        <p>Pick a zone</p>
      </Sheet>,
    )
    await userEvent.click(screen.getByRole('button', { name: 'Where' }))
    expect(await screen.findByRole('dialog', { name: 'Put a look on' })).toBeInTheDocument()
  })
})
```

- [ ] **Step 3: Run it to see it fail**

```bash
(cd web && npx vitest run src/design/overlays.test.tsx)
```

Expected: FAIL with `Failed to resolve import "./overlays"`.

- [ ] **Step 4: Implement**

`web/src/design/overlays.tsx`:

```tsx
import { Dialog as BaseDialog } from '@base-ui/react/dialog'
import { Popover as BasePopover } from '@base-ui/react/popover'
import { Tooltip as BaseTooltip } from '@base-ui/react/tooltip'
import type { ReactElement, ReactNode } from 'react'
import { IconButton } from './button'

interface OverlayProps {
  /** The element that opens it; Base UI wires its events and ARIA. */
  trigger: ReactElement
  /** Names the overlay for assistive tech and heads it. */
  title: string
  children?: ReactNode
  open?: boolean
  onOpenChange?: (open: boolean) => void
}

export interface TooltipProps {
  content: ReactNode
  /** The element it describes. Give icon-only triggers an aria-label: the tooltip is visual only. */
  children: ReactElement
  side?: 'top' | 'right' | 'bottom' | 'left'
}

/** §6.1 Tooltip. */
export function Tooltip({ content, children, side = 'top' }: TooltipProps) {
  return (
    <BaseTooltip.Root>
      <BaseTooltip.Trigger render={children} />
      <BaseTooltip.Portal>
        <BaseTooltip.Positioner side={side} sideOffset={6} className="z-50">
          <BaseTooltip.Popup className="flex max-w-72 flex-col gap-1.25 rounded-tile border border-line-strong bg-raised/94 px-3 py-2.5 text-meta text-text shadow-tip">
            {content}
          </BaseTooltip.Popup>
        </BaseTooltip.Positioner>
      </BaseTooltip.Portal>
    </BaseTooltip.Root>
  )
}

const SURFACE = 'rounded-card border border-line-strong bg-raised shadow-pop outline-none'
const HEAD = 'text-section font-semibold text-text'

/** §6.1 Popover: anchored to its trigger. */
export function Popover({ trigger, title, children, open, onOpenChange, align = 'center' }: OverlayProps & { align?: 'start' | 'center' | 'end' }) {
  return (
    <BasePopover.Root open={open} onOpenChange={onOpenChange}>
      <BasePopover.Trigger render={trigger} />
      <BasePopover.Portal>
        <BasePopover.Positioner sideOffset={8} align={align} className="z-50">
          <BasePopover.Popup className={`overflow-hidden ${SURFACE}`}>
            <BasePopover.Title className={`px-3.5 py-3 ${HEAD}`}>{title}</BasePopover.Title>
            {children}
          </BasePopover.Popup>
        </BasePopover.Positioner>
      </BasePopover.Portal>
    </BasePopover.Root>
  )
}

/** §6.1 Dialog: centred and modal. */
export function Dialog({ trigger, title, children, open, onOpenChange }: OverlayProps) {
  return (
    <BaseDialog.Root open={open} onOpenChange={onOpenChange}>
      <BaseDialog.Trigger render={trigger} />
      <BaseDialog.Portal>
        <BaseDialog.Backdrop className="fixed inset-0 z-40 bg-bg/50" />
        <BaseDialog.Popup className={`fixed top-1/2 left-1/2 z-50 flex w-[min(28rem,calc(100vw-2rem))] -translate-1/2 flex-col gap-3 p-5 ${SURFACE}`}>
          <div className="flex items-start justify-between gap-4">
            <BaseDialog.Title className={HEAD}>{title}</BaseDialog.Title>
            <BaseDialog.Close render={<IconButton icon="x" label="Close" />} />
          </div>
          {children}
        </BaseDialog.Popup>
      </BaseDialog.Portal>
    </BaseDialog.Root>
  )
}

/** §6.1 Sheet: the phone's bottom sheet, with a grabber. */
export function Sheet({ trigger, title, children, open, onOpenChange }: OverlayProps) {
  return (
    <BaseDialog.Root open={open} onOpenChange={onOpenChange}>
      <BaseDialog.Trigger render={trigger} />
      <BaseDialog.Portal>
        <BaseDialog.Backdrop className="fixed inset-0 z-40 bg-bg/50" />
        <BaseDialog.Popup className="fixed inset-x-0 bottom-0 z-50 flex max-h-[85dvh] flex-col gap-1 overflow-y-auto rounded-t-sheet border-t border-line bg-panel px-4 pt-2 pb-[max(1rem,env(safe-area-inset-bottom))] shadow-sheet outline-none">
          <span aria-hidden="true" className="mx-auto mb-1.5 h-1.25 w-10 shrink-0 rounded-[3px] bg-line-strong" />
          <BaseDialog.Title className={HEAD}>{title}</BaseDialog.Title>
          {children}
        </BaseDialog.Popup>
      </BaseDialog.Portal>
    </BaseDialog.Root>
  )
}
```

- [ ] **Step 5: Run it to see it pass**

```bash
(cd web && npx vitest run src/design/overlays.test.tsx && npx tsc -b && npm run lint)
```

Expected: 4 passed; tsc and lint are clean.

- [ ] **Step 6: Commit**

```bash
git add web/src/design/overlays.tsx web/src/design/overlays.test.tsx
git commit -m "feat: add Tooltip, Popover, Dialog and Sheet"
```

---

### Task 9: Formatters and viewport hooks

Implements spec §10 (24 h times, BPM to one decimal) and §4.4 (the phone breakpoint). Renders:
- `Main.png`: the top bar's clock.
- `Phone-Live.png`: the header's context line.
- `Phone-Tempo.png`: the header's date.

**Files:**
- Create: `web/src/lib/format.ts`, `web/src/lib/use-media-query.ts`, `web/src/lib/use-now.ts`, `web/src/test/viewport.ts`
- Modify: `web/src/test/setup.ts` (install the matchMedia stand-in; every test starts at 1440 px)
- Test: `web/src/lib/format.test.ts`, `web/src/lib/hooks.test.tsx`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `formatTime(date): string` ("19:14"), `formatDayTime(date): string` ("Wed 19:14"), `formatDayDateTime(date): string` ("Wed 23 Sep · 19:14") and `formatBpm(bpm: number): string` ("121.8").
  - `PHONE_QUERY = '(width < 48rem)'`, `useMediaQuery(query: string): boolean` and `useIsPhone(): boolean`.
  - `useNow(): Date`, which updates on each minute boundary.
  - Test helpers `installMatchMedia(): void` and `setViewportWidth(px: number): void` from `@/test/viewport`.

- [ ] **Step 1: Re-read the sources**

Read spec §10 and §4.4. Look at the top bar's clock in `Main.png`, the header context in `Phone-Live.png` and the header date in `Phone-Tempo.png`.

- [ ] **Step 2: Write the failing tests**

`web/src/lib/format.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { formatBpm, formatDayDateTime, formatDayTime, formatTime } from './format'

describe('format', () => {
  const hero = new Date(2026, 8, 23, 19, 14)

  it('writes the clocks the chrome shows', () => {
    expect(formatDayDateTime(hero)).toBe('Wed 23 Sep · 19:14')
    expect(formatDayTime(hero)).toBe('Wed 19:14')
    expect(formatDayDateTime(new Date(2025, 8, 20, 23, 40))).toBe('Sat 20 Sep · 23:40')
  })

  it('uses a 24 h clock with padded minutes', () => {
    expect(formatTime(new Date(2026, 0, 5, 0, 5))).toBe('00:05')
    expect(formatDayDateTime(new Date(2026, 0, 5, 9, 7))).toBe('Mon 5 Jan · 09:07')
  })

  it('writes BPM with one decimal', () => {
    expect(formatBpm(121.8)).toBe('121.8')
    expect(formatBpm(124)).toBe('124.0')
    expect(formatBpm(125.46)).toBe('125.5')
  })
})
```

`web/src/lib/hooks.test.tsx`:

```tsx
import { act, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { setViewportWidth } from '@/test/viewport'
import { formatTime } from './format'
import { useIsPhone } from './use-media-query'
import { useNow } from './use-now'

function Layout() {
  return <p>{useIsPhone() ? 'phone' : 'desktop'}</p>
}

function Clock() {
  return <p>{formatTime(useNow())}</p>
}

describe('useIsPhone', () => {
  it('follows the 768 px breakpoint as the viewport changes', () => {
    render(<Layout />)
    expect(screen.getByText('desktop')).toBeInTheDocument()
    act(() => setViewportWidth(767))
    expect(screen.getByText('phone')).toBeInTheDocument()
    act(() => setViewportWidth(768))
    expect(screen.getByText('desktop')).toBeInTheDocument()
  })
})

describe('useNow', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('ticks over on the minute', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 8, 23, 19, 14, 30))
    render(<Clock />)
    expect(screen.getByText('19:14')).toBeInTheDocument()
    act(() => vi.advanceTimersByTime(30_000))
    expect(screen.getByText('19:15')).toBeInTheDocument()
    act(() => vi.advanceTimersByTime(60_000))
    expect(screen.getByText('19:16')).toBeInTheDocument()
  })
})
```

- [ ] **Step 3: Run them to see them fail**

```bash
(cd web && npx vitest run src/lib)
```

Expected: FAIL with `Failed to resolve import "./format"` and `Failed to resolve import "@/test/viewport"`.

- [ ] **Step 4: Implement**

`web/src/lib/format.ts`:

```ts
// Copy rules, spec §10: 24 h time, BPM with one decimal. English names are spelled out rather
// than taken from Intl: en-GB abbreviates September as "Sept", and the renders say "Sep".
const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

const pad = (n: number) => String(n).padStart(2, '0')

/** "19:14" */
export function formatTime(date: Date): string {
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`
}

/** "Wed 19:14", the phone header's clock. */
export function formatDayTime(date: Date): string {
  return `${DAYS[date.getDay()]} ${formatTime(date)}`
}

/** "Wed 23 Sep · 19:14", the desktop top bar's clock. */
export function formatDayDateTime(date: Date): string {
  return `${DAYS[date.getDay()]} ${date.getDate()} ${MONTHS[date.getMonth()]} · ${formatTime(date)}`
}

/** "121.8" */
export function formatBpm(bpm: number): string {
  return bpm.toFixed(1)
}
```

`web/src/lib/use-media-query.ts`:

```ts
import { useCallback, useMemo, useSyncExternalStore } from 'react'

/** Below Tailwind's `md` (48rem = 768 px) the app uses the phone layouts (spec §4.4). */
export const PHONE_QUERY = '(width < 48rem)'

export function useMediaQuery(query: string): boolean {
  const list = useMemo(() => window.matchMedia(query), [query])
  const subscribe = useCallback(
    (onChange: () => void) => {
      list.addEventListener('change', onChange)
      return () => list.removeEventListener('change', onChange)
    },
    [list],
  )
  return useSyncExternalStore(subscribe, () => list.matches)
}

export function useIsPhone(): boolean {
  return useMediaQuery(PHONE_QUERY)
}
```

`web/src/lib/use-now.ts`:

```ts
import { useEffect, useState } from 'react'

const untilNextMinute = (date: Date) => 60_000 - (date.getSeconds() * 1000 + date.getMilliseconds())

/** The current time, refreshed on each minute boundary: the chrome's clocks show minutes. */
export function useNow(): Date {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    let timer = setTimeout(function tick() {
      const current = new Date()
      setNow(current)
      timer = setTimeout(tick, untilNextMinute(current))
    }, untilNextMinute(new Date()))
    return () => clearTimeout(timer)
  }, [])
  return now
}
```

`web/src/test/viewport.ts`. jsdom has no `matchMedia`.

```ts
// jsdom has no matchMedia. This stand-in evaluates the width queries the app uses,
// "(width < Nrem)" and "(width >= Nrem)", and fires "change" when a test resizes.
type Listener = () => void

let width = 1440
const subscribed = new Map<string, Set<Listener>>()

function evaluate(query: string): boolean {
  const match = /^\(width (<|>=) ([\d.]+)rem\)$/.exec(query)
  if (!match) throw new Error(`the test matchMedia can't evaluate "${query}"`)
  const px = Number(match[2]) * 16
  return match[1] === '<' ? width < px : width >= px
}

export function installMatchMedia(): void {
  window.matchMedia = (query: string) =>
    ({
      media: query,
      get matches() {
        return evaluate(query)
      },
      onchange: null,
      addEventListener: (_type: string, listener: Listener) => {
        const set = subscribed.get(query) ?? new Set<Listener>()
        set.add(listener)
        subscribed.set(query, set)
      },
      removeEventListener: (_type: string, listener: Listener) => {
        subscribed.get(query)?.delete(listener)
      },
      addListener: () => {},
      removeListener: () => {},
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList
}

/** Resize the fake viewport; listeners run only for queries whose answer changed. */
export function setViewportWidth(next: number): void {
  const before = new Map([...subscribed.keys()].map((q) => [q, evaluate(q)]))
  width = next
  for (const [query, listeners] of subscribed) {
    if (evaluate(query) !== before.get(query)) listeners.forEach((listener) => listener())
  }
}
```

Replace `web/src/test/setup.ts` with:

```ts
import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, beforeEach } from 'vitest'
import { installMatchMedia, setViewportWidth } from './viewport'

installMatchMedia()

beforeEach(() => {
  setViewportWidth(1440)
})

afterEach(() => {
  cleanup()
})
```

- [ ] **Step 5: Run them to see them pass**

```bash
(cd web && npm test && npx tsc -b && npm run lint)
```

Expected: all tests pass, including 5 new ones; tsc and lint are clean.

- [ ] **Step 6: Commit**

```bash
git add web/src/lib web/src/test
git commit -m "feat: add the clock and BPM formatters and the viewport hooks"
```

---

### Task 10: The always-within-reach cluster

Implements spec §6.2 (`TempoModule`, `PreviewOnlySwitch`, `AttentionButton`, `ConnectionIndicator`), §2.3, §5.6 (the phone eye turns to a tape disc), §9.5 (which dot goes where), §12.5 (the hero scenario, as a fixture) and §4.4 (the tablet band). Renders:
- `Main.png`: the top-bar cluster.
- `Phone-Live.png`: the strip and the header buttons.
- `State-Preview-Only.png` and `Phone-State-Preview-Only.png`: Preview only on.
- `State-Problems.png`: attention.
- `State-Reconnecting.png` and `Phone-State-Reconnecting.png`: reconnecting.
- `System.png`.

**Files:**
- Create: `web/src/chrome/state.ts`, `web/src/chrome/tempo-module.tsx`, `web/src/chrome/preview-only-switch.tsx`, `web/src/chrome/attention-button.tsx`, `web/src/chrome/connection-indicator.tsx`
- Modify: `web/src/styles/app.css` (append the `tablet` variant and the two keyframes)
- Test: `web/src/chrome/chrome.test.tsx`

**Interfaces:**
- Consumes: `cx`, `Icon`, `IconName`, `Switch` and `formatBpm`.
- Produces:
  - `type TempoSource = 'prodjlink' | 'music' | 'internal'` and `interface TempoState { source: TempoSource; bpm: number; beat: number; bar: number; stale: boolean }`.
  - `TempoModule({ variant: 'bar' | 'strip', ...TempoState, onSourceClick?, onTap? })`.
  - `PreviewOnlySwitch({ on, onChange?, variant: 'bar' | 'header' })`.
  - `AttentionButton({ count, variant: 'bar' | 'header', onOpen? })`.
  - `type Connection = { status: 'live'; fps: number } | { status: 'reconnecting'; attempt: number }` and `ConnectionIndicator({ connection, variant: 'bar' | 'header' })`.
  - `interface AttentionCounts { total: number; lights: number; inputs: number }`.
  - `interface ChromeState { tempo: TempoState; previewOnly: boolean; attention: AttentionCounts; connection: Connection; server: string; sunset: string }`.
  - `HERO_CHROME: ChromeState` and `useChrome(): ChromeState`.
  - A `tablet:` Tailwind variant.

- [ ] **Step 1: Re-read the sources**

Read spec §2.3, §5.4, §5.6, §6.2, §9.5 and §12.5's hero scenario.
- Look at the top bar in `Main.png` and the strip and header in `Phone-Live.png`.
- Look at the switch on in `State-Preview-Only.png` and `Phone-State-Preview-Only.png`.
- Look at the attention button in `State-Problems.png`, and the reconnect indicator in `State-Reconnecting.png` and `Phone-State-Reconnecting.png`.
- Open `Phone-State-Reconnecting.html`: the reconnect pill comes before the eye button.

- [ ] **Step 2: Write the failing test**

`web/src/chrome/chrome.test.tsx`:

```tsx
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { AttentionButton } from './attention-button'
import { ConnectionIndicator } from './connection-indicator'
import { HERO_CHROME } from './state'
import { PreviewOnlySwitch } from './preview-only-switch'
import { TempoModule } from './tempo-module'

describe('TempoModule', () => {
  it('shows source, BPM, the beat and the bar (desktop)', async () => {
    const onTap = vi.fn()
    render(<TempoModule variant="bar" {...HERO_CHROME.tempo} onTap={onTap} />)
    const tempo = screen.getByRole('group', { name: 'Tempo' })
    expect(within(tempo).getByRole('button', { name: 'Music' })).toHaveAttribute('aria-haspopup', 'dialog')
    expect(tempo).toHaveTextContent('121.8BPM')
    expect(within(tempo).getByRole('img', { name: 'Beat 2 of 4' })).toBeInTheDocument()
    expect(tempo).toHaveTextContent('bar 42')
    await userEvent.click(within(tempo).getByRole('button', { name: 'Tap' }))
    expect(onTap).toHaveBeenCalledOnce()
  })

  it('drops the source button and the bar on the phone strip', () => {
    render(<TempoModule variant="strip" {...HERO_CHROME.tempo} />)
    const tempo = screen.getByRole('group', { name: 'Tempo' })
    expect(within(tempo).queryByRole('button', { name: 'Music' })).toBeNull()
    expect(tempo).toHaveTextContent('Music')
    expect(tempo).not.toHaveTextContent('bar 42')
    expect(within(tempo).getByRole('button', { name: 'Tap' })).toHaveClass('h-10')
  })

  it('stale: the source turns signal, is named stale, and the pips stop', () => {
    render(<TempoModule variant="bar" source="internal" bpm={118} beat={2} bar={7} stale />)
    const source = screen.getByRole('button', { name: 'Internal, stale' })
    expect(source).toHaveClass('text-signal')
    expect(screen.queryByRole('img')).toBeNull()
    expect(screen.getByRole('group', { name: 'Tempo' })).toHaveTextContent('118.0')
  })
})

describe('PreviewOnlySwitch', () => {
  it('is a labelled tape switch on desktop', () => {
    render(<PreviewOnlySwitch variant="bar" on={false} />)
    expect(screen.getByRole('switch', { name: 'Preview only' })).toHaveAttribute('aria-checked', 'false')
  })

  it('is a 44 px eye button on phone that turns to tape when on', async () => {
    const onChange = vi.fn()
    const { rerender } = render(<PreviewOnlySwitch variant="header" on={false} onChange={onChange} />)
    const eye = screen.getByRole('switch', { name: 'Preview only' })
    expect(eye).toHaveClass('size-(--touch-min)')
    await userEvent.click(eye)
    expect(onChange).toHaveBeenCalledWith(true)
    rerender(<PreviewOnlySwitch variant="header" on onChange={onChange} />)
    expect(eye).toHaveClass('tape')
  })
})

describe('AttentionButton', () => {
  it('counts what needs attention', () => {
    render(<AttentionButton variant="bar" count={1} />)
    const button = screen.getByRole('button', { name: '1 needs attention' })
    expect(button).toHaveTextContent('Needs attention1')
    expect(button).toHaveClass('text-signal')
  })

  it('says All good at zero on desktop and hides on phone', () => {
    const { rerender } = render(<AttentionButton variant="bar" count={0} />)
    expect(screen.getByRole('button', { name: 'All good' })).toHaveClass('text-text-3')
    rerender(<AttentionButton variant="header" count={0} />)
    expect(screen.queryByRole('button')).toBeNull()
  })

  it('agrees in number', () => {
    render(<AttentionButton variant="header" count={3} />)
    expect(screen.getByRole('button', { name: '3 need attention' })).toHaveTextContent('3')
  })
})

describe('ConnectionIndicator', () => {
  it('shows Live with the frame rate', () => {
    render(<ConnectionIndicator variant="bar" connection={{ status: 'live', fps: 60 }} />)
    expect(screen.getByText('Live')).toBeInTheDocument()
    expect(screen.getByText('60 fps')).toHaveClass('num')
  })

  it('shows Reconnecting with the attempt, in signal', () => {
    render(<ConnectionIndicator variant="bar" connection={{ status: 'reconnecting', attempt: 3 }} />)
    const status = screen.getByRole('status')
    expect(status).toHaveTextContent('Reconnecting· try 3')
    expect(status).toHaveClass('text-signal')
  })

  it('shows nothing on phone while live, and a reconnect pill otherwise', () => {
    const { container, rerender } = render(<ConnectionIndicator variant="header" connection={{ status: 'live', fps: 60 }} />)
    expect(container).toBeEmptyDOMElement()
    rerender(<ConnectionIndicator variant="header" connection={{ status: 'reconnecting', attempt: 3 }} />)
    expect(screen.getByRole('status')).toHaveTextContent('Reconnecting · try 3')
  })
})
```

- [ ] **Step 3: Run it to see it fail**

```bash
(cd web && npx vitest run src/chrome)
```

Expected: FAIL with `Failed to resolve import "./attention-button"`.

- [ ] **Step 4: Implement**

`web/src/chrome/tempo-module.tsx`:

```tsx
import { cx } from '@/design/cx'
import { Icon } from '@/design/icon'
import type { IconName } from '@/design/icons'
import { formatBpm } from '@/lib/format'

export type TempoSource = 'prodjlink' | 'music' | 'internal'

export interface TempoState {
  source: TempoSource
  bpm: number
  /** Beat in the bar, 1–4. */
  beat: number
  bar: number
  /** §6.2: the source stopped updating; its label turns signal and the pips stop. */
  stale: boolean
}

export interface TempoModuleProps extends TempoState {
  /** "bar": the desktop top bar. "strip": the phone strip under the header on Live. */
  variant: 'bar' | 'strip'
  onSourceClick?: () => void
  onTap?: () => void
}

const SOURCE: Record<TempoSource, { label: string; icon: IconName }> = {
  prodjlink: { label: 'Pro DJ Link', icon: 'deck' },
  music: { label: 'Music', icon: 'music' },
  internal: { label: 'Internal', icon: 'tempo' },
}

/** §6.2 TempoModule. F0 draws a still beat; F3 drives the pips from the beat clock (§5.4). */
export function TempoModule({ variant, source, bpm, beat, bar, stale, onSourceClick, onTap }: TempoModuleProps) {
  const { label, icon } = SOURCE[source]
  const staleNote = stale && <span className="sr-only">, stale</span>
  const pips = <Pips beat={stale ? null : beat} variant={variant} />

  if (variant === 'strip') {
    return (
      <div
        role="group"
        aria-label="Tempo"
        // At 320 px (the WCAG reflow width) the gaps tighten so TAP stays inside the strip.
        className="flex h-(--phone-tempo-h) items-center gap-3 rounded-card border border-line bg-raised pr-1 pl-3 max-[22.5rem]:gap-2"
      >
        <span className={cx('inline-flex items-center gap-1.5 text-data font-semibold', stale ? 'text-signal' : 'text-text-2')}>
          <Icon name={icon} size={16} />
          {label}
          {staleNote}
        </span>
        <span className="num text-bpm font-semibold tracking-[-0.02em]">
          {formatBpm(bpm)}
          <span className="sr-only"> BPM</span>
        </span>
        {pips}
        <button
          type="button"
          onClick={onTap}
          className="h-10 rounded-[9px] border border-line-strong bg-control-hover px-4 text-size-control font-bold tracking-[0.06em] uppercase"
        >
          Tap
        </button>
      </div>
    )
  }

  return (
    <div
      role="group"
      aria-label="Tempo"
      className="flex h-10 w-95 items-center justify-between gap-3 rounded-tile border border-line bg-raised px-1.5 tablet:w-auto"
    >
      <button
        type="button"
        aria-haspopup="dialog"
        onClick={onSourceClick}
        className={cx('inline-flex h-7 items-center gap-1.5 rounded-chip bg-control px-2 text-meta font-semibold', stale ? 'text-signal' : 'text-text-2')}
      >
        <Icon name={icon} size={14} />
        <span className="tablet:sr-only">{label}</span>
        {staleNote}
        <Icon name="down" size={12} className="text-text-3" />
      </button>
      <span className="flex items-baseline gap-1.25">
        <span className="num text-bpm font-semibold tracking-[-0.02em] text-text">{formatBpm(bpm)}</span>
        <span className="text-[10px] font-semibold tracking-[0.08em] text-text-3">BPM</span>
      </span>
      {pips}
      <span className="num text-[11.5px] whitespace-nowrap text-text-3 tablet:hidden">bar {bar}</span>
      <button
        type="button"
        onClick={onTap}
        className="h-7 rounded-chip border border-line-strong bg-control-hover px-3 text-meta font-bold tracking-[0.06em] text-text uppercase"
      >
        Tap
      </button>
    </div>
  )
}

/** Four beat pips; the downbeat is wider. `beat` null means stopped. */
function Pips({ beat, variant }: { beat: number | null; variant: 'bar' | 'strip' }) {
  const strip = variant === 'strip'
  return (
    <span
      role={beat === null ? undefined : 'img'}
      aria-label={beat === null ? undefined : `Beat ${beat} of 4`}
      aria-hidden={beat === null ? true : undefined}
      className={cx('flex items-center gap-1.25', strip && 'flex-1')}
    >
      {[1, 2, 3, 4].map((n) => (
        <span
          key={n}
          className={cx(
            strip ? 'h-3 rounded-[3px]' : 'h-2.5 rounded-[2px]',
            n === 1 ? (strip ? 'w-4' : 'w-3.5') : strip ? 'w-3' : 'w-2.5',
            n === beat ? 'bg-text shadow-[0_0_10px] shadow-text/55' : 'bg-control-hover',
          )}
        />
      ))}
    </span>
  )
}
```

`web/src/chrome/preview-only-switch.tsx`:

```tsx
import { cx } from '@/design/cx'
import { Icon } from '@/design/icon'
import { Switch } from '@/design/switch'

export interface PreviewOnlySwitchProps {
  on: boolean
  onChange?: (on: boolean) => void
  /** "bar": labelled tape switch (desktop). "header": 44 px eye button (phone). */
  variant: 'bar' | 'header'
}

/** §6.2 PreviewOnlySwitch; §5.6 tape. */
export function PreviewOnlySwitch({ on, onChange, variant }: PreviewOnlySwitchProps) {
  if (variant === 'bar') {
    return <Switch checked={on} onCheckedChange={onChange} label="Preview only" tape />
  }
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label="Preview only"
      onClick={() => onChange?.(!on)}
      className={cx('inline-flex size-(--touch-min) items-center justify-center rounded-pill border', on ? 'tape border-text' : 'border-line bg-control')}
    >
      <span className={cx('inline-flex size-7 items-center justify-center rounded-pill', on ? 'bg-bg text-text' : 'text-text-2')}>
        <Icon name="eye" size={18} />
      </span>
    </button>
  )
}
```

`web/src/chrome/attention-button.tsx`:

```tsx
import { Icon } from '@/design/icon'

export interface AttentionButtonProps {
  /** How many things need attention (spec §9.5). */
  count: number
  /** "bar": the desktop top bar. "header": the phone header, which hides it at zero. */
  variant: 'bar' | 'header'
  onOpen?: () => void
}

const name = (count: number) => `${count} ${count === 1 ? 'needs' : 'need'} attention`

/** §6.2 AttentionButton. F3 adds AttentionPopover (desktop) and AttentionSheet (phone). */
export function AttentionButton({ count, variant, onOpen }: AttentionButtonProps) {
  if (variant === 'header') {
    if (count === 0) return null
    return (
      <button
        type="button"
        aria-haspopup="dialog"
        aria-label={name(count)}
        onClick={onOpen}
        className="num inline-flex h-(--touch-min) items-center gap-1.5 rounded-pill border border-signal-line bg-signal-bg px-3.5 text-size-control font-bold text-signal"
      >
        <Icon name="alert" size={16} />
        {count}
      </button>
    )
  }

  if (count === 0) {
    return (
      <button
        type="button"
        aria-haspopup="dialog"
        onClick={onOpen}
        className="inline-flex h-9 items-center gap-1.75 rounded-control border border-line px-3 text-data font-semibold text-text-3"
      >
        <Icon name="check" size={15} />
        <span className="tablet:sr-only">All good</span>
      </button>
    )
  }

  return (
    <button
      type="button"
      aria-haspopup="dialog"
      aria-label={name(count)}
      onClick={onOpen}
      className="inline-flex h-9 items-center gap-2 rounded-control border border-signal-line bg-signal-bg pr-3 pl-2.5 text-data font-semibold whitespace-nowrap text-signal"
    >
      <Icon name="alert" size={15} />
      <span className="tablet:hidden">Needs attention</span>
      <span className="num inline-flex h-4.5 min-w-4.5 items-center justify-center rounded-pill bg-signal px-1.25 text-label font-bold text-signal-ink">
        {count}
      </span>
    </button>
  )
}
```

`web/src/chrome/connection-indicator.tsx`:

```tsx
import { Icon } from '@/design/icon'

export type Connection = { status: 'live'; fps: number } | { status: 'reconnecting'; attempt: number }

export interface ConnectionIndicatorProps {
  connection: Connection
  /** "bar": always shown (desktop). "header": only while reconnecting (phone). */
  variant: 'bar' | 'header'
}

const SPIN = 'animate-[reconnect-spin_1.4s_linear_infinite]'

/** §6.2 ConnectionIndicator: "● Live 60 fps" or "⟳ Reconnecting · try 3". */
export function ConnectionIndicator({ connection, variant }: ConnectionIndicatorProps) {
  if (connection.status === 'live') {
    if (variant === 'header') return null
    return (
      <span className="inline-flex items-center gap-1.75 text-meta whitespace-nowrap text-text-2">
        <span aria-hidden="true" className="size-1.75 rounded-full bg-text animate-[livedot_2s_ease-in-out_infinite]" />
        Live
        <span className="num text-text-3 tablet:hidden">{connection.fps} fps</span>
      </span>
    )
  }

  if (variant === 'header') {
    return (
      <span
        role="status"
        className="inline-flex h-(--touch-min) items-center rounded-pill border border-signal-line bg-signal-bg px-3 text-signal"
      >
        <Icon name="refresh" size={15} className={SPIN} />
        <span className="sr-only">Reconnecting · try {connection.attempt}</span>
      </span>
    )
  }

  return (
    <span role="status" className="inline-flex items-center gap-1.75 text-meta font-semibold whitespace-nowrap text-signal">
      <Icon name="refresh" size={14} className={SPIN} />
      Reconnecting
      <span className="num font-normal">· try {connection.attempt}</span>
    </span>
  )
}
```

`web/src/chrome/state.ts`:

```ts
import type { Connection } from './connection-indicator'
import type { TempoState } from './tempo-module'

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
 * The §12.5 "hero" scenario, as drawn in Main.png and Phone-Live.png: tempo from Music at 121.8,
 * Rope offline (one light needs attention), connected at 60 fps.
 */
export const HERO_CHROME: ChromeState = {
  tempo: { source: 'music', bpm: 121.8, beat: 2, bar: 42, stale: false },
  previewOnly: false,
  attention: { total: 1, lights: 1, inputs: 0 },
  connection: { status: 'live', fps: 60 },
  server: 'homeserver',
  sunset: '19:26',
}

/** F0 shows the hero fixture. F1 and F3 replace this with the live stores. */
export function useChrome(): ChromeState {
  return HERO_CHROME
}
```

Append to `web/src/styles/app.css`, after one blank line. The keyframes are the reference pages' own, and tokens.css's `prefers-reduced-motion` block already stops them.

```css
/* Spec §4.4's middle band keeps the desktop structure, so the top bar drops its optional text. */
@custom-variant tablet (@media (width >= 48rem) and (width < 75rem));

/* §6.2 ConnectionIndicator: the live dot's pulse and the reconnect spinner, as in the reference pages. */
@keyframes livedot {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.35;
  }
}

@keyframes reconnect-spin {
  to {
    transform: rotate(360deg);
  }
}
```

- [ ] **Step 5: Run it to see it pass**

```bash
(cd web && npx vitest run src/chrome && npx tsc -b && npm run lint)
```

Expected: 11 passed; tsc and lint are clean.

- [ ] **Step 6: Commit**

```bash
git add web/src/chrome web/src/styles/app.css
git commit -m "feat: add the tempo module, Preview only switch, attention button and connection indicator"
```

---

### Task 11: Rail, top bar, tab bar and phone header

Implements spec §4.1 (rail, top bar), §4.2 (phone header, tab bar) and §9.5 (the rail's signal dots). Renders:
- `Main.png`: the rail and top bar.
- `Phone-Live.png`: the header and tab bar.
- `Phone-State-Reconnecting.png`: the reconnect pill in the header.
- `Devices.png`: the rail with Devices current.

**Files:**
- Create: `web/src/shell/logo.tsx`, `web/src/shell/nav.ts`, `web/src/shell/rail.tsx`, `web/src/shell/tab-bar.tsx`, `web/src/shell/top-bar.tsx`, `web/src/shell/phone-header.tsx`
- Test: `web/src/shell/shell.test.tsx`

**Interfaces:**
- Consumes: `Icon`, `IconName`, `TempoModule`, `PreviewOnlySwitch`, `AttentionButton`, `ConnectionIndicator`, `ChromeState`, `AttentionCounts` and `HERO_CHROME` (in the test only).
- Produces:
  - `Logo()`.
  - `interface NavItem { to: string; label: string; icon: IconName; dot?: 'lights' | 'inputs' }`, `RAIL_ITEMS`, `TAB_ITEMS` and `hasDot(item, attention): boolean`.
  - `Rail({ attention, server })` and `TabBar({ attention })`. Each is a `<nav aria-label="Main">`.
  - `TopBar({ title, context?, chrome })`, a `<header>`.
  - `PhoneHeader({ title, context?, chrome, children? })`, a `<header>`. `children` is drawn inside the banner, under the title row: the tempo strip on Live.

- [ ] **Step 1: Re-read the sources**

Read spec §4.1, §4.2 and §9.5.
- Look at the rail and top bar in `Main.png`, and the header and tab bar in `Phone-Live.png`.
- Look at the reconnect pill in `Phone-State-Reconnecting.png`, and the rail in `Devices.png`, where Devices is current on `/devices/tube`.
- Open `reference/Main.html`: the logo's SVG is in the rail's markup. `logo.tsx` below is that SVG with its fixed colour swapped for `currentColor`; check it against the page.

- [ ] **Step 2: Write the failing test**

`web/src/shell/shell.test.tsx`:

```tsx
import { render, screen, within } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router'
import { describe, expect, it } from 'vitest'
import { HERO_CHROME } from '@/chrome/state'
import { PhoneHeader } from './phone-header'
import { Rail } from './rail'
import { TabBar } from './tab-bar'
import { TopBar } from './top-bar'

/** Renders `ui` as if the app were at /next{path}. */
function at(path: string, ui: ReactNode) {
  return render(
    <MemoryRouter basename="/next" initialEntries={[`/next${path}`]}>
      {ui}
    </MemoryRouter>,
  )
}

const linkNames = (nav: HTMLElement) => within(nav).getAllByRole('link').map((link) => link.textContent)

describe('Rail', () => {
  it('has the logo, then the six places in order, and the server in the footer', () => {
    at('/live', <Rail attention={HERO_CHROME.attention} server="homeserver" />)
    const rail = screen.getByRole('navigation', { name: 'Main' })
    expect(linkNames(rail)).toEqual(['', 'Live', 'Looks', 'Map', 'Devices, needs attention', 'Inputs', 'Settings'])
    expect(within(rail).getByRole('link', { name: 'dj-ledfx home' })).toHaveAttribute('href', '/next/live')
    expect(within(rail).getByRole('link', { name: 'Live' })).toHaveAttribute('aria-current', 'page')
    expect(rail).toHaveTextContent('dj-ledfx · homeserver')
  })

  it('marks the section of a nested path as current', () => {
    at('/devices/tube', <Rail attention={HERO_CHROME.attention} server="homeserver" />)
    const rail = screen.getByRole('navigation', { name: 'Main' })
    expect(within(rail).getByRole('link', { name: 'Devices, needs attention' })).toHaveAttribute('aria-current', 'page')
    expect(within(rail).getByRole('link', { name: 'Live' })).not.toHaveAttribute('aria-current')
  })

  it('puts the dot where the attention is, and nowhere when nothing needs it', () => {
    const { unmount } = at('/live', <Rail attention={{ total: 1, lights: 0, inputs: 1 }} server="homeserver" />)
    expect(linkNames(screen.getByRole('navigation'))).toContain('Inputs, needs attention')
    expect(linkNames(screen.getByRole('navigation'))).toContain('Devices')
    unmount()
    at('/live', <Rail attention={{ total: 0, lights: 0, inputs: 0 }} server="homeserver" />)
    expect(screen.queryByText(', needs attention')).toBeNull()
  })
})

describe('TabBar', () => {
  it('has five tabs, and Tempo opens the phone view of /inputs', () => {
    at('/inputs', <TabBar attention={{ total: 1, lights: 0, inputs: 1 }} />)
    const tabs = screen.getByRole('navigation', { name: 'Main' })
    expect(linkNames(tabs)).toEqual(['Live', 'Looks', 'Devices', 'Tempo, needs attention', 'Settings'])
    const tempo = within(tabs).getByRole('link', { name: 'Tempo, needs attention' })
    expect(tempo).toHaveAttribute('href', '/next/inputs')
    expect(tempo).toHaveAttribute('aria-current', 'page')
  })
})

describe('TopBar', () => {
  it('shows the title, the context and the cluster', () => {
    at('/live', <TopBar title="Live" context="Wed 23 Sep · 19:14" chrome={HERO_CHROME} />)
    const bar = screen.getByRole('banner')
    expect(within(bar).getByRole('heading', { level: 1 })).toHaveTextContent('Live')
    expect(bar).toHaveTextContent('Wed 23 Sep · 19:14')
    expect(within(bar).getByRole('group', { name: 'Tempo' })).toBeInTheDocument()
    expect(within(bar).getByRole('switch', { name: 'Preview only' })).toBeInTheDocument()
    expect(within(bar).getByRole('button', { name: '1 needs attention' })).toBeInTheDocument()
    expect(bar).toHaveTextContent('Live60 fps')
  })

  it('leaves the context out when a page has none', () => {
    at('/settings', <TopBar title="Settings" chrome={HERO_CHROME} />)
    // The context line is the title's only sibling.
    expect(screen.getByRole('heading', { level: 1, name: 'Settings' }).nextElementSibling).toBeNull()
  })
})

describe('PhoneHeader', () => {
  it('shows the serif title and context, the eye and the attention count, and no reconnect pill while live', () => {
    at('/live', <PhoneHeader title="Home" context="Wed 19:14 · sun sets 19:26" chrome={HERO_CHROME} />)
    const header = screen.getByRole('banner')
    expect(within(header).getByRole('heading', { level: 1 })).toHaveTextContent('Home')
    expect(within(header).getByRole('heading', { level: 1 })).toHaveClass('font-serif')
    expect(header).toHaveTextContent('Wed 19:14 · sun sets 19:26')
    expect(within(header).getByRole('switch', { name: 'Preview only' })).toBeInTheDocument()
    expect(within(header).getByRole('button', { name: '1 needs attention' })).toBeInTheDocument()
    expect(within(header).queryByRole('status')).toBeNull()
  })

  it('puts the reconnect pill first while reconnecting', () => {
    const chrome = { ...HERO_CHROME, connection: { status: 'reconnecting', attempt: 3 } as const }
    at('/live', <PhoneHeader title="Home" chrome={chrome} />)
    const pill = screen.getByRole('status')
    expect(pill).toHaveTextContent('Reconnecting · try 3')
    expect(pill.compareDocumentPosition(screen.getByRole('switch'))).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
  })

  it('draws its children inside the banner', () => {
    at('/live', (
      <PhoneHeader title="Home" chrome={HERO_CHROME}>
        <p>strip</p>
      </PhoneHeader>
    ))
    expect(within(screen.getByRole('banner')).getByText('strip')).toBeInTheDocument()
  })
})
```

- [ ] **Step 3: Run it to see it fail**

```bash
(cd web && npx vitest run src/shell)
```

Expected: FAIL with `Failed to resolve import "./phone-header"`.

- [ ] **Step 4: Implement**

`web/src/shell/logo.tsx`:

```tsx
/**
 * The dj-ledfx mark, copied from the rail in reference/Main.html (it isn't in icons.ts),
 * with its fixed colour swapped for currentColor.
 */
export function Logo() {
  return (
    <svg width="30" height="30" viewBox="0 0 32 32" aria-hidden="true" focusable="false" className="block shrink-0">
      <path d="M16 3 28 9.5v13L16 29 4 22.5v-13z" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M4 9.5 16 16l12-6.5M16 16v13" fill="none" stroke="currentColor" strokeOpacity="0.35" strokeWidth="1.2" />
      <circle cx="16" cy="16" r="5.5" fill="currentColor" fillOpacity="0.16" />
      <circle cx="16" cy="16" r="2.6" fill="currentColor" />
    </svg>
  )
}
```

`web/src/shell/nav.ts`:

```ts
import type { AttentionCounts } from '@/chrome/state'
import type { IconName } from '@/design/icons'

export interface NavItem {
  to: string
  label: string
  icon: IconName
  /** The attention count that puts a signal dot on this item (spec §9.5). */
  dot?: keyof Omit<AttentionCounts, 'total'>
}

/** §4.1: the desktop rail. */
export const RAIL_ITEMS: readonly NavItem[] = [
  { to: '/live', label: 'Live', icon: 'live' },
  { to: '/looks', label: 'Looks', icon: 'looks' },
  { to: '/map', label: 'Map', icon: 'map' },
  { to: '/devices', label: 'Devices', icon: 'devices', dot: 'lights' },
  { to: '/inputs', label: 'Inputs', icon: 'inputs', dot: 'inputs' },
  { to: '/settings', label: 'Settings', icon: 'settings' },
]

/** §4.2: the phone tab bar. The map is reached from Devices; Tempo is the phone's /inputs. */
export const TAB_ITEMS: readonly NavItem[] = [
  { to: '/live', label: 'Live', icon: 'live' },
  { to: '/looks', label: 'Looks', icon: 'looks' },
  { to: '/devices', label: 'Devices', icon: 'devices', dot: 'lights' },
  { to: '/inputs', label: 'Tempo', icon: 'tempo', dot: 'inputs' },
  { to: '/settings', label: 'Settings', icon: 'settings' },
]

export function hasDot(item: NavItem, attention: AttentionCounts): boolean {
  return item.dot !== undefined && attention[item.dot] > 0
}
```

`web/src/shell/rail.tsx`:

```tsx
import { Link, NavLink } from 'react-router'
import type { AttentionCounts } from '@/chrome/state'
import { Icon } from '@/design/icon'
import { Logo } from './logo'
import { RAIL_ITEMS, hasDot } from './nav'

export interface RailProps {
  attention: AttentionCounts
  server: string
}

/** §4.1 rail (Main.png). */
export function Rail({ attention, server }: RailProps) {
  return (
    <nav
      aria-label="Main"
      className="flex h-full w-(--rail-w) flex-col items-center gap-1.5 border-r border-line-soft bg-bg pt-3.5"
    >
      <Link to="/live" aria-label="dj-ledfx home" className="mb-3.5 flex size-11 items-center justify-center text-text">
        <Logo />
      </Link>
      {RAIL_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          className="relative flex size-14 flex-col items-center justify-center gap-1.25 rounded-tile text-[10.5px] font-semibold tracking-[0.02em] text-text-3 transition-colors duration-(--duration-fast) ease-out hover:text-text-2 aria-[current=page]:bg-control aria-[current=page]:text-text"
        >
          <Icon name={item.icon} size={20} />
          <span>{item.label}</span>
          {hasDot(item, attention) && (
            <>
              <span aria-hidden="true" className="absolute top-1.5 right-3 size-1.75 rounded-full bg-signal shadow-[0_0_0_2px_var(--color-bg)]" />
              <span className="sr-only">, needs attention</span>
            </>
          )}
        </NavLink>
      ))}
      <div className="flex-1" />
      <p className="num rotate-180 pb-4 text-[9.5px] tracking-[0.08em] text-text-3 [writing-mode:vertical-rl]">
        dj-ledfx · {server}
      </p>
    </nav>
  )
}
```

`web/src/shell/tab-bar.tsx`:

```tsx
import { NavLink } from 'react-router'
import type { AttentionCounts } from '@/chrome/state'
import { Icon } from '@/design/icon'
import { TAB_ITEMS, hasDot } from './nav'

/** §4.2 tab bar (Phone-Live.png). The OS home indicator gets env(safe-area-inset-bottom). */
export function TabBar({ attention }: { attention: AttentionCounts }) {
  return (
    <nav
      aria-label="Main"
      className="flex h-[calc(var(--tabbar-h)+env(safe-area-inset-bottom))] shrink-0 border-t border-line-soft bg-bg px-2 pt-1 pb-[env(safe-area-inset-bottom)]"
    >
      {TAB_ITEMS.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          className="relative flex h-14 flex-1 basis-0 flex-col items-center justify-center gap-1 text-[10.5px] font-semibold text-text-3 aria-[current=page]:text-text"
        >
          <Icon name={item.icon} size={22} />
          <span>{item.label}</span>
          {hasDot(item, attention) && (
            <>
              <span aria-hidden="true" className="absolute top-1.5 left-1/2 ml-2 size-1.75 rounded-full bg-signal" />
              <span className="sr-only">, needs attention</span>
            </>
          )}
        </NavLink>
      ))}
    </nav>
  )
}
```

`web/src/shell/top-bar.tsx`:

```tsx
import { AttentionButton } from '@/chrome/attention-button'
import { ConnectionIndicator } from '@/chrome/connection-indicator'
import type { ChromeState } from '@/chrome/state'
import { PreviewOnlySwitch } from '@/chrome/preview-only-switch'
import { TempoModule } from '@/chrome/tempo-module'

export interface TopBarProps {
  title: string
  context?: string
  chrome: ChromeState
}

/** §4.1 top bar (Main.png): title and context, then the always-within-reach cluster (§6.2). */
export function TopBar({ title, context, chrome }: TopBarProps) {
  return (
    <header className="flex h-(--topbar-h) min-w-0 items-center justify-between gap-4 border-b border-line-soft bg-bg pr-5 pl-6">
      <div className="flex min-w-0 items-baseline gap-3">
        <h1 className="truncate text-title font-semibold tracking-[-0.005em]">{title}</h1>
        {context && <span className="text-data whitespace-nowrap text-text-3 tablet:hidden">{context}</span>}
      </div>
      <div className="flex shrink-0 items-center gap-3.5 tablet:gap-2.5">
        <TempoModule variant="bar" {...chrome.tempo} />
        <span aria-hidden="true" className="h-6 w-px bg-line tablet:hidden" />
        <PreviewOnlySwitch variant="bar" on={chrome.previewOnly} />
        <AttentionButton variant="bar" count={chrome.attention.total} />
        <ConnectionIndicator variant="bar" connection={chrome.connection} />
      </div>
    </header>
  )
}
```

`web/src/shell/phone-header.tsx`:

```tsx
import type { ReactNode } from 'react'
import { AttentionButton } from '@/chrome/attention-button'
import { ConnectionIndicator } from '@/chrome/connection-indicator'
import type { ChromeState } from '@/chrome/state'
import { PreviewOnlySwitch } from '@/chrome/preview-only-switch'

export interface PhoneHeaderProps {
  title: string
  context?: string
  chrome: ChromeState
  /** Drawn under the title row, inside the banner: the tempo strip on Live. */
  children?: ReactNode
}

/** §4.2 phone header (Phone-Live.png): serif title and context; reconnect, eye and attention. */
export function PhoneHeader({ title, context, chrome, children }: PhoneHeaderProps) {
  return (
    <header className="shrink-0">
      <div className="flex h-(--phone-header-h) items-center justify-between gap-2 px-4">
        <div className="flex min-w-0 flex-col">
          <h1 className="truncate font-serif text-display-md leading-none">{title}</h1>
          {context && <span className="mt-0.75 truncate text-meta text-text-3">{context}</span>}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <ConnectionIndicator variant="header" connection={chrome.connection} />
          <PreviewOnlySwitch variant="header" on={chrome.previewOnly} />
          <AttentionButton variant="header" count={chrome.attention.total} />
        </div>
      </div>
      {children}
    </header>
  )
}
```

- [ ] **Step 5: Run it to see it pass**

```bash
(cd web && npx vitest run src/shell && npx tsc -b && npm run lint)
```

Expected: 9 passed; tsc and lint are clean.

- [ ] **Step 6: Commit**

```bash
git add web/src/shell
git commit -m "feat: add the rail, top bar, tab bar and phone header"
```

---

### Task 12: App shell, routes and pages

Implements spec §4.1–4.4, every §4.3 route as a placeholder, §8.10's phone Live header, §10's copy for the not-found and error pages, and Review Focus 1, 2 and 4.

Renders:
- `Main.png` and `Phone-Live.png`: the whole chrome.
- For each page's title and context line: `Looks.png`, `Home-Map.png`, `Devices.png`, `Inputs.png` and `Settings.png`, and their phone twins `Phone-Looks.png`, `Phone-Map.png`, `Phone-Devices.png`, `Phone-Tempo.png` and `Phone-Settings.png`.

**Files:**
- Create: `web/src/app/page-meta.ts`, `web/src/app/routes.tsx`, `web/src/shell/app-shell.tsx`, `web/src/pages/placeholder.tsx`, `web/src/pages/not-found.tsx`, `web/src/pages/app-error.tsx`
- Modify: `web/src/main.tsx` (replace it: mount the router)
- Test: `web/src/app/app.test.tsx`

**Interfaces:**
- Consumes: everything in `src/shell/` and `src/chrome/`, `useIsPhone`, `useNow`, the formatters, `Button` and `ButtonLink`.
- Produces:
  - `interface MetaContext { now: Date; chrome: ChromeState }`.
  - `interface PageMeta { title: string; context?: (at: MetaContext) => string; phoneTitle?: string; phoneContext?: (at: MetaContext) => string; tempoStrip?: boolean }`, set as each route's `handle`.
  - `usePageMeta(): PageMeta`.
  - `routes: RouteObject[]`: the paths are relative to basename `/next`, and the root route renders `AppShell` with `AppError` as its error element.
  - `AppShell()`, `Placeholder({ name, milestone })`, `NotFound()` and `AppError()`.

- [ ] **Step 1: Re-read the sources**

Read spec §4.1–4.4, the Live row of §8.10 and §10.
- Look at `Main.png` and `Phone-Live.png` whole.
- Look at the title and context line of each render listed above.
- Titles and contexts that count data ("29 looks · 3 running") stay out until their milestones, as Decision 8 says.

- [ ] **Step 2: Write the failing test**

`web/src/app/app.test.tsx`. The routes block pins Review Focus 1 and 2, and the last test pins Review Focus 4.

```tsx
import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useEffect } from 'react'
import { createMemoryRouter, RouterProvider, type RouteObject } from 'react-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { AppError } from '@/pages/app-error'
import { AppShell } from '@/shell/app-shell'
import { setViewportWidth } from '@/test/viewport'
import { routes } from './routes'

/** The real shell around test-only pages. */
const inShell = (children: RouteObject[]): RouteObject[] => [{ element: <AppShell />, errorElement: <AppError />, children }]

function renderApp(path: string, routeList: RouteObject[] = routes) {
  const router = createMemoryRouter(routeList, { basename: '/next', initialEntries: [path] })
  render(<RouterProvider router={router} />)
  return router
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(2026, 8, 23, 19, 14))
})

afterEach(() => {
  vi.useRealTimers()
})

describe('routes', () => {
  // Review focus: /next without a trailing slash lands on Live, like /next/.
  it.each(['/next', '/next/'])('%s redirects to Live', async (path) => {
    const router = renderApp(path)
    expect(await screen.findByRole('heading', { level: 1, name: 'Live' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/next/live')
    expect(document.title).toBe('Live · dj-ledfx')
  })

  // Review focus: a reloaded deep link renders its page.
  it('opens a deep link directly', async () => {
    renderApp('/next/looks/fireflies')
    expect(await screen.findByRole('heading', { level: 1, name: 'Looks' })).toBeInTheDocument()
    expect(screen.getByText('Look editor')).toBeInTheDocument()
  })

  // Review focus: a mistyped path stays in the shell with a way back.
  it('shows a calm not-found page inside the shell', async () => {
    const router = renderApp('/next/lookz')
    expect(await screen.findByText('Nothing here')).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Main' })).toBeInTheDocument()
    expect(screen.getByText('/lookz')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('link', { name: 'Go to Live' }))
    expect(router.state.location.pathname).toBe('/next/live')
  })

  it('shows its own error page when a screen throws', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    function Broken(): never {
      throw new Error('boom')
    }
    renderApp('/next/broken', inShell([{ path: 'broken', element: <Broken /> }]))
    expect(await screen.findByRole('heading', { name: 'Something broke' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reload' })).toBeInTheDocument()
  })
})

describe('desktop chrome (Main.png)', () => {
  it('has the rail, the page title and context, and the cluster', async () => {
    renderApp('/next/live')
    const rail = await screen.findByRole('navigation', { name: 'Main' })
    const links = within(rail).getAllByRole('link')
    expect(links.map((link) => link.textContent)).toEqual([
      '',
      'Live',
      'Looks',
      'Map',
      'Devices, needs attention',
      'Inputs',
      'Settings',
    ])
    expect(within(rail).getByRole('link', { name: 'dj-ledfx home' })).toHaveAttribute('href', '/next/live')
    expect(within(rail).getByRole('link', { name: 'Live' })).toHaveAttribute('aria-current', 'page')
    expect(rail).toHaveTextContent('dj-ledfx · homeserver')

    const header = screen.getByRole('banner')
    expect(within(header).getByRole('heading', { level: 1 })).toHaveTextContent('Live')
    expect(header).toHaveTextContent('Wed 23 Sep · 19:14')
    expect(within(header).getByRole('group', { name: 'Tempo' })).toHaveTextContent('121.8')
    expect(within(header).getByRole('switch', { name: 'Preview only' })).toBeInTheDocument()
    expect(within(header).getByRole('button', { name: '1 needs attention' })).toBeInTheDocument()
    expect(header).toHaveTextContent('Live60 fps')
  })

  it('moves the current page with navigation', async () => {
    renderApp('/next/live')
    const rail = await screen.findByRole('navigation', { name: 'Main' })
    await userEvent.click(within(rail).getByRole('link', { name: 'Map' }))
    expect(screen.getByRole('heading', { level: 1, name: 'Map' })).toBeInTheDocument()
    expect(screen.getByText('Place lights, anchors and sub-zones')).toBeInTheDocument()
    expect(within(rail).getByRole('link', { name: 'Map' })).toHaveAttribute('aria-current', 'page')
    expect(within(rail).getByRole('link', { name: 'Live' })).not.toHaveAttribute('aria-current')
  })
})

describe('phone chrome (Phone-Live.png)', () => {
  beforeEach(() => {
    setViewportWidth(390)
  })

  it('has the header, the tempo strip on Live, and the tab bar', async () => {
    renderApp('/next/live')
    const header = await screen.findByRole('banner')
    expect(within(header).getByRole('heading', { level: 1 })).toHaveTextContent('Home')
    expect(header).toHaveTextContent('Wed 19:14 · sun sets 19:26')
    expect(within(header).getByRole('switch', { name: 'Preview only' })).toBeInTheDocument()
    expect(within(header).getByRole('button', { name: '1 needs attention' })).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Tempo' })).toBeInTheDocument()

    const tabs = screen.getByRole('navigation', { name: 'Main' })
    expect(within(tabs).getAllByRole('link').map((link) => link.textContent)).toEqual([
      'Live',
      'Looks',
      'Devices, needs attention',
      'Tempo',
      'Settings',
    ])
    expect(within(tabs).getByRole('link', { name: 'Tempo' })).toHaveAttribute('href', '/next/inputs')
    expect(screen.queryByRole('link', { name: 'dj-ledfx home' })).toBeNull()
  })

  it('shows the tempo strip on Live only', async () => {
    renderApp('/next/looks')
    expect(await screen.findByRole('heading', { level: 1, name: 'Looks' })).toBeInTheDocument()
    expect(screen.queryByRole('group', { name: 'Tempo' })).toBeNull()
  })

  it('names /inputs Tempo on the phone', async () => {
    renderApp('/next/inputs')
    expect(await screen.findByRole('heading', { level: 1, name: 'Tempo' })).toBeInTheDocument()
    expect(screen.getByRole('banner')).toHaveTextContent('Wed 23 Sep · 19:14')
  })
})

// Review focus: crossing 768 px swaps the chrome in place; the page is not remounted.
it('swaps the chrome live across the breakpoint without remounting the page', async () => {
  let mounts = 0
  function Probe() {
    useEffect(() => {
      mounts += 1
    }, [])
    return <p>probe</p>
  }
  renderApp('/next/live', inShell([{ path: 'live', element: <Probe /> }]))
  expect(await screen.findByText('probe')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'dj-ledfx home' })).toBeInTheDocument()

  act(() => setViewportWidth(390))
  expect(screen.queryByRole('link', { name: 'dj-ledfx home' })).toBeNull()
  expect(within(screen.getByRole('navigation', { name: 'Main' })).getAllByRole('link')).toHaveLength(5)

  act(() => setViewportWidth(1024))
  expect(screen.getByRole('link', { name: 'dj-ledfx home' })).toBeInTheDocument()
  expect(mounts).toBe(1)
})
```

- [ ] **Step 3: Run it to see it fail**

```bash
(cd web && npx vitest run src/app)
```

Expected: FAIL with `Failed to resolve import "@/pages/app-error"`.

- [ ] **Step 4: Implement**

`web/src/app/page-meta.ts`:

```ts
import { useMatches } from 'react-router'
import type { ChromeState } from '@/chrome/state'

export interface MetaContext {
  now: Date
  chrome: ChromeState
}

/** What the chrome shows for a route (spec §4.1, §4.2). Set as the route's `handle`. */
export interface PageMeta {
  /** The top bar title and the document title. */
  title: string
  /** The line beside the title on desktop. */
  context?: (at: MetaContext) => string
  /** The phone header's serif title, when it differs ("Home" on Live). */
  phoneTitle?: string
  /** The line under the phone title. Phones show no context without it. */
  phoneContext?: (at: MetaContext) => string
  /** Phone only: the tempo strip under the header (Live). */
  tempoStrip?: boolean
}

const FALLBACK: PageMeta = { title: 'dj-ledfx' }

/** The meta of the deepest matched route that has one. */
export function usePageMeta(): PageMeta {
  const matches = useMatches()
  for (let i = matches.length - 1; i >= 0; i--) {
    const meta = matches[i].handle as PageMeta | undefined
    if (meta?.title) return meta
  }
  return FALLBACK
}
```

`web/src/app/routes.tsx`:

```tsx
import { Navigate, type RouteObject } from 'react-router'
import { formatDayDateTime, formatDayTime } from '@/lib/format'
import { AppError } from '@/pages/app-error'
import { NotFound } from '@/pages/not-found'
import { Placeholder } from '@/pages/placeholder'
import { AppShell } from '@/shell/app-shell'
import type { PageMeta } from './page-meta'

// Titles and context lines are the renders' (Main, Looks, Home-Map, Devices, Inputs, Settings and
// their Phone-* twins). Lines that count data ("29 looks · 3 running") arrive with that data.
const LIVE: PageMeta = {
  title: 'Live',
  context: ({ now }) => formatDayDateTime(now),
  phoneTitle: 'Home',
  phoneContext: ({ now, chrome }) => `${formatDayTime(now)} · sun sets ${chrome.sunset}`,
  tempoStrip: true,
}
const LOOKS: PageMeta = { title: 'Looks' }
const MAP: PageMeta = {
  title: 'Map',
  context: () => 'Place lights, anchors and sub-zones',
  phoneContext: () => 'Confirm guessed positions',
}
const DEVICES: PageMeta = { title: 'Devices', context: () => 'Lights and PC parts' }
const INPUTS: PageMeta = {
  title: 'Inputs',
  context: () => 'Tempo, music, Home Assistant, the sun',
  phoneTitle: 'Tempo',
  phoneContext: ({ now }) => formatDayDateTime(now),
}
const SETTINGS: PageMeta = { title: 'Settings' }

/** Spec §4.3. Paths are relative to the router's basename (/next until F11). */
export const routes: RouteObject[] = [
  {
    element: <AppShell />,
    errorElement: <AppError />,
    children: [
      { index: true, element: <Navigate to="/live" replace /> },
      { path: 'live', handle: LIVE, element: <Placeholder name="Stage and Running panel" milestone="F2 and F3" /> },
      { path: 'live/put', handle: LIVE, element: <Placeholder name="Put a look on" milestone="F4" /> },
      { path: 'live/zones/:zoneId', handle: LIVE, element: <Placeholder name="Zone" milestone="F3" /> },
      { path: 'looks', handle: LOOKS, element: <Placeholder name="Looks" milestone="F5" /> },
      { path: 'looks/:lookId', handle: LOOKS, element: <Placeholder name="Look editor" milestone="F8" /> },
      { path: 'map', handle: MAP, element: <Placeholder name="Home map" milestone="F7" /> },
      { path: 'map/:thingId', handle: MAP, element: <Placeholder name="Home map" milestone="F7" /> },
      { path: 'devices', handle: DEVICES, element: <Placeholder name="Devices" milestone="F6" /> },
      { path: 'devices/:deviceId', handle: DEVICES, element: <Placeholder name="Devices" milestone="F6" /> },
      { path: 'inputs', handle: INPUTS, element: <Placeholder name="Inputs" milestone="F6" /> },
      { path: 'settings', handle: SETTINGS, element: <Placeholder name="Settings" milestone="F6" /> },
      { path: '*', handle: { title: 'Not found' } satisfies PageMeta, element: <NotFound /> },
    ],
  },
]
```

`web/src/shell/app-shell.tsx`:

```tsx
import { Outlet } from 'react-router'
import { usePageMeta } from '@/app/page-meta'
import { useChrome } from '@/chrome/state'
import { TempoModule } from '@/chrome/tempo-module'
import { useIsPhone } from '@/lib/use-media-query'
import { useNow } from '@/lib/use-now'
import { PhoneHeader } from './phone-header'
import { Rail } from './rail'
import { TabBar } from './tab-bar'
import { TopBar } from './top-bar'

/**
 * §4.1–4.2: rail and top bar on desktop; header (with the tempo strip on Live) and tab bar on phone.
 * `<main>` keeps its place in the tree, so crossing the breakpoint swaps the chrome without
 * remounting the page.
 */
export function AppShell() {
  const isPhone = useIsPhone()
  const meta = usePageMeta()
  const chrome = useChrome()
  const now = useNow()
  const at = { now, chrome }

  return (
    <div
      className={
        isPhone
          ? 'flex h-dvh flex-col pt-[env(safe-area-inset-top)]'
          : 'grid h-dvh grid-cols-[var(--rail-w)_minmax(0,1fr)] grid-rows-[var(--topbar-h)_minmax(0,1fr)]'
      }
    >
      <title>{`${meta.title} · dj-ledfx`}</title>
      {isPhone ? (
        <PhoneHeader title={meta.phoneTitle ?? meta.title} context={meta.phoneContext?.(at)} chrome={chrome}>
          {meta.tempoStrip && (
            <div className="mx-4 mt-1.5">
              <TempoModule variant="strip" {...chrome.tempo} />
            </div>
          )}
        </PhoneHeader>
      ) : (
        <div className="row-span-2">
          <Rail attention={chrome.attention} server={chrome.server} />
        </div>
      )}
      {!isPhone && <TopBar title={meta.title} context={meta.context?.(at)} chrome={chrome} />}
      <main className="min-h-0 flex-1 overflow-y-auto">
        <Outlet />
      </main>
      {isPhone && <TabBar attention={chrome.attention} />}
    </div>
  )
}
```

`web/src/pages/placeholder.tsx`:

```tsx
export interface PlaceholderProps {
  /** What this page becomes. */
  name: string
  /** The milestone that builds it (engine spec §10). */
  milestone: string
}

/** F0 stands in for every page with a calm empty state (spec §4.3 routes). */
export function Placeholder({ name, milestone }: PlaceholderProps) {
  return (
    <div className="grid h-full place-items-center p-6">
      <div className="flex max-w-sm flex-col items-center gap-2 text-center">
        <p className="font-serif text-display-lg">{name}</p>
        <p className="text-body text-text-2">Built in {milestone}.</p>
      </div>
    </div>
  )
}
```

`web/src/pages/not-found.tsx`:

```tsx
import { useLocation } from 'react-router'
import { ButtonLink } from '@/design/button'

/** Unknown paths stay inside the shell, with a way back to Live. */
export function NotFound() {
  const { pathname } = useLocation()
  return (
    <div className="grid h-full place-items-center p-6">
      <div className="flex max-w-sm flex-col items-center gap-3 text-center">
        <p className="font-serif text-display-lg">Nothing here</p>
        <p className="text-body text-text-2">
          There's no page at <span className="num text-text">{pathname}</span>.
        </p>
        <ButtonLink to="/live" variant="outline" icon="live">
          Go to Live
        </ButtonLink>
      </div>
    </div>
  )
}
```

`web/src/pages/app-error.tsx`:

```tsx
import { Button } from '@/design/button'

/** The root error boundary: calm copy instead of React Router's developer screen. */
export function AppError() {
  return (
    <div className="grid h-dvh place-items-center p-6">
      <title>Something broke · dj-ledfx</title>
      <div className="flex max-w-sm flex-col items-center gap-3 text-center">
        <h1 className="font-serif text-display-lg">Something broke</h1>
        <p className="text-body text-text-2">This screen hit an error. Your looks keep running on the server.</p>
        <Button variant="outline" icon="refresh" onClick={() => window.location.reload()}>
          Reload
        </Button>
      </div>
    </div>
  )
}
```

Replace `web/src/main.tsx` with:

```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router'
import { routes } from './app/routes'
import './styles/app.css'

// Vite's base is /next/; the basename drops the slash so a bare /next matches too.
const router = createBrowserRouter(routes, { basename: import.meta.env.BASE_URL.replace(/\/$/, '') })

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <RouterProvider router={router} />
  </StrictMode>,
)
```

- [ ] **Step 5: Run it to see it pass, then build**

```bash
(cd web && npx vitest run src/app && npm test && npx tsc -b && npm run lint && npm run build)
```

Expected:
- 11 passed, then the whole suite passes.
- tsc and lint are clean.
- The build prints the main chunk at about 106 kB gzipped, far under §14's first-load budget.

- [ ] **Step 6: Commit**

```bash
git add web/src/app web/src/shell/app-shell.tsx web/src/pages web/src/main.tsx
git commit -m "feat: add the app shell and every route as a placeholder"
```

---

### Task 13: The `/system` specimen and the Playwright checks

Implements §13.1 M0's done-when, §14 Visual and §14 Accessibility, and Review Focus 4 at real widths. Renders: `Main.png`, `Phone-Live.png` and `System.png`.

**Files:**
- Create: `web/src/pages/system.tsx`, `web/playwright.config.ts`, `web/e2e/shell.spec.ts`
- Create (Playwright writes them): `web/e2e/shell.spec.ts-snapshots/live-desktop-linux.png`, `live-phone-linux.png`, `system-desktop-linux.png`
- Modify: `web/src/app/routes.tsx` (add the lazy `system` route)

**Interfaces:**
- Consumes: every primitive, the cluster, `HERO_CHROME` and `routes`.
- Produces:
  - `SystemPage()`, lazy-loaded at `/next/system`.
  - `npm run e2e`, with a `desktop` project (1440 × 900) and a `phone` project (390 × 844, touch). Both run against `vite preview` at `http://localhost:4174/next/`.

- [ ] **Step 1: Re-read the sources**

Read spec §13.1's M0 row and §14's Visual and Accessibility lines. Look at `Main.png`, `Phone-Live.png` and `System.png` whole. You'll compare against them in Step 6.

- [ ] **Step 2: Write the specimen and its route**

`web/src/pages/system.tsx`:

```tsx
import { useState, type ReactNode } from 'react'
import { AttentionButton } from '@/chrome/attention-button'
import { ConnectionIndicator } from '@/chrome/connection-indicator'
import { HERO_CHROME } from '@/chrome/state'
import { PreviewOnlySwitch } from '@/chrome/preview-only-switch'
import { TempoModule } from '@/chrome/tempo-module'
import { Button, IconButton } from '@/design/button'
import { Chip, Label, Tag } from '@/design/chip'
import { Field } from '@/design/field'
import { Dialog, Popover, Sheet, Tooltip } from '@/design/overlays'
import { Segmented } from '@/design/segmented'
import { Select } from '@/design/select'
import { Slider } from '@/design/slider'
import { Switch } from '@/design/switch'
import { Toast } from '@/design/toast'

const TRANSITIONS = { cut: 'Cut', fade: 'Fade · 1 s', dissolve: 'Dissolve · 3 s' }

function Row({ label, children }: { label: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <Label>{label}</Label>
      <div className="flex flex-wrap items-center gap-3">{children}</div>
    </section>
  )
}

/** An unlinked specimen of the §6.1 primitives and §6.2 cluster, for comparing with System.png. */
export function SystemPage() {
  const [on, setOn] = useState(true)
  const [level, setLevel] = useState(70)
  const [view, setView] = useState<'3d' | 'plan'>('3d')
  const [transition, setTransition] = useState<keyof typeof TRANSITIONS>('dissolve')
  const tempo = HERO_CHROME.tempo

  return (
    <div className="flex flex-col gap-8 p-6">
      <Row label="Buttons">
        <Button variant="primary" icon="plus">Put a look on</Button>
        <Button>Change</Button>
        <Button variant="outline">Tweak</Button>
        <Button variant="ghost">Cancel</Button>
        <Button variant="danger" icon="power">Off</Button>
        <Button size="sm">Stop ripple</Button>
        <Button variant="primary" size="lg">Start</Button>
        <Button disabled>Restart</Button>
        <IconButton icon="refresh" label="Refresh" />
        <IconButton icon="plan" label="Plan view" active />
      </Row>
      <Row label="Controls">
        <Switch checked={on} onCheckedChange={setOn} label="Evening" />
        <Switch checked={on} onCheckedChange={setOn} label="Preview only" tape />
        <Slider className="w-55" label="Brightness" value={level} onValueChange={setLevel} format={(v) => `${v}%`} />
        <Segmented
          label="View"
          value={view}
          onValueChange={setView}
          options={[
            { value: '3d', label: '3D', icon: 'cube' },
            { value: 'plan', label: 'Plan', icon: 'plan' },
          ]}
        />
        <Select className="w-40" label="Transition" value={transition} items={TRANSITIONS} onValueChange={setTransition} />
        <Field className="w-30" label="Height" unit="m" defaultValue="1.20" />
      </Row>
      <Row label="Chips, tags and labels">
        <Chip icon="music">Music</Chip>
        <Chip variant="mod">Evening</Chip>
        <Chip variant="quiet">No DJ</Chip>
        <Chip variant="signal" icon="music">Music · 42 s</Chip>
        <Chip variant="solid">Glow</Chip>
        <Tag>Living room</Tag>
        <Tag variant="signal" icon="alert">OFFLINE</Tag>
        <Tag variant="solid">PREVIEW</Tag>
        <Label>Running</Label>
      </Row>
      <Row label="Overlays">
        <Tooltip content="Fit the home">
          <IconButton icon="crosshair" label="Fit" />
        </Tooltip>
        <Popover trigger={<Button>Popover</Button>} title="Needs attention">
          <p className="px-3.5 pb-3 text-body text-text-2">Rope is offline since 17:02.</p>
        </Popover>
        <Dialog trigger={<Button>Dialog</Button>} title="Restore from a file">
          <p className="text-body text-text-2">Everything is replaced by the file.</p>
        </Dialog>
        <Sheet trigger={<Button>Sheet</Button>} title="Put a look on">
          <p className="pb-2 text-body text-text-2">Where, then what.</p>
        </Sheet>
        <Toast
          icon="bell"
          title="Doorbell"
          detail="Front door · 19:16"
          readout="1.8 s"
          tint="#ffcf5c"
          action={<Button size="sm">Stop ripple</Button>}
        />
      </Row>
      <Row label="Always within reach">
        <TempoModule variant="bar" {...tempo} />
        <TempoModule variant="bar" source="internal" bpm={118} beat={2} bar={7} stale />
        <div className="w-89.5">
          <TempoModule variant="strip" {...tempo} />
        </div>
        <PreviewOnlySwitch variant="bar" on={false} />
        <PreviewOnlySwitch variant="bar" on />
        <PreviewOnlySwitch variant="header" on={false} />
        <PreviewOnlySwitch variant="header" on />
        <AttentionButton variant="bar" count={2} />
        <AttentionButton variant="bar" count={0} />
        <AttentionButton variant="header" count={1} />
        <ConnectionIndicator variant="bar" connection={{ status: 'live', fps: 60 }} />
        <ConnectionIndicator variant="bar" connection={{ status: 'reconnecting', attempt: 3 }} />
        <ConnectionIndicator variant="header" connection={{ status: 'reconnecting', attempt: 3 }} />
      </Row>
    </div>
  )
}
```

In `web/src/app/routes.tsx`, add this route directly above the `'*'` route:

```tsx
      // The primitives specimen loads on demand, keeping Base UI out of the first load.
      {
        path: 'system',
        handle: { title: 'System' } satisfies PageMeta,
        lazy: async () => ({ Component: (await import('@/pages/system')).SystemPage }),
      },
```

- [ ] **Step 3: Write the Playwright config and spec**

`web/playwright.config.ts`:

```ts
import { defineConfig } from '@playwright/test'

// Runs against the production bundle (vite preview), at /next, the way FastAPI serves it.
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  reporter: 'list',
  use: {
    baseURL: 'http://localhost:4174',
    timezoneId: 'America/Chicago',
    colorScheme: 'dark',
  },
  projects: [
    // Spec §4.4: designed at 1440 × 900 and 390 × 844.
    { name: 'desktop', use: { browserName: 'chromium', viewport: { width: 1440, height: 900 } } },
    {
      name: 'phone',
      use: { browserName: 'chromium', viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 1 },
    },
  ],
  webServer: {
    command: 'npm run build && npm run preview',
    url: 'http://localhost:4174/next/',
    reuseExistingServer: false,
  },
})
```

`web/e2e/shell.spec.ts`:

```ts
import AxeBuilder from '@axe-core/playwright'
import { expect, test, type Page } from '@playwright/test'

// The hero moment (spec §12.5): Wednesday 23 September, 19:14 in Dallas (timezoneId in the config).
const HERO_TIME = new Date('2026-09-23T19:14:00-05:00')

// Every §4.3 route, the specimen, and a mistyped path.
const ROUTES = [
  '/next/live',
  '/next/live/put?zone=living&look=embers',
  '/next/live/zones/living',
  '/next/looks?cat=calm&q=fire',
  '/next/looks/fireflies',
  '/next/map',
  '/next/map/tube',
  '/next/devices',
  '/next/devices/tube',
  '/next/inputs',
  '/next/settings#backup',
  '/next/system',
  '/next/lookz',
]

async function open(page: Page, path: string) {
  await page.goto(path)
  await page.evaluate(() => document.fonts.ready)
}

test.beforeEach(async ({ page }) => {
  await page.clock.setFixedTime(HERO_TIME)
})

// Done when (spec §13.1 M0): the chrome matches Main.png at 1440 × 900 and Phone-Live.png at 390 × 844.
test('Live chrome', async ({ page }) => {
  await open(page, '/next/live')
  await expect(page).toHaveScreenshot('live.png')
})

// §6.1 primitives and §6.2 cluster, laid out like System.png. The phone page scrolls inside <main>,
// so a phone screenshot would show only its top; axe still checks the whole phone page below.
test('System specimen', async ({ page }, { project }) => {
  test.skip(project.name !== 'desktop', 'the specimen fits one desktop screen')
  await open(page, '/next/system')
  await expect(page.getByText('Always within reach')).toBeVisible()
  await expect(page).toHaveScreenshot('system.png')
})

for (const path of ROUTES) {
  test(`axe passes on ${path}`, async ({ page }) => {
    await open(page, path)
    await expect(page.locator('h1')).toBeVisible()
    const { violations } = await new AxeBuilder({ page }).analyze()
    expect(violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(' | ')}`)).toEqual([])
  })
}

test('fonts are self-hosted and load', async ({ page, baseURL }) => {
  const elsewhere: string[] = []
  page.on('request', (request) => {
    if (!request.url().startsWith(`${baseURL}/`)) elsewhere.push(request.url())
  })
  await open(page, '/next/live')
  expect(elsewhere).toEqual([])
  const loaded = await page.evaluate(() =>
    [...document.fonts].filter((face) => face.status === 'loaded').map((face) => face.family.replaceAll('"', '')),
  )
  expect(new Set(loaded)).toEqual(new Set(['Instrument Sans', 'Instrument Serif', 'JetBrains Mono Variable']))
})

test('the keyboard walks the rail, then the cluster', async ({ page }, { project }) => {
  test.skip(project.name !== 'desktop', 'the rail is desktop chrome')
  await open(page, '/next/live')
  const names: string[] = []
  for (let i = 0; i < 11; i += 1) {
    await page.keyboard.press('Tab')
    names.push(await page.evaluate(() => {
      const el = document.activeElement
      return el?.getAttribute('aria-label') ?? el?.textContent?.trim() ?? ''
    }))
  }
  expect(names).toEqual([
    'dj-ledfx home',
    'Live',
    'Looks',
    'Map',
    'Devices, needs attention',
    'Inputs',
    'Settings',
    'Music',
    'Tap',
    'Preview only',
    '1 needs attention',
  ])
  for (let i = 0; i < 4; i += 1) await page.keyboard.press('Shift+Tab')
  await expect(page.getByRole('link', { name: 'Settings' })).toBeFocused()
  await page.keyboard.press('Enter')
  await expect(page).toHaveURL(/\/next\/settings$/)
  await expect(page.getByRole('heading', { level: 1, name: 'Settings' })).toBeVisible()
})

// Review focus: crossing 768 px (a window resize, a tablet rotating) swaps the chrome in place.
test('resizing across 768 px swaps the chrome without a reload', async ({ page }, { project }) => {
  test.skip(project.name !== 'desktop', 'one project is enough; this test sets the width')
  await open(page, '/next/live')
  await page.evaluate(() => Object.assign(window, { stillHere: true }))
  await page.setViewportSize({ width: 767, height: 900 })
  await expect(page.getByRole('link', { name: 'Tempo' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'dj-ledfx home' })).toHaveCount(0)
  await page.setViewportSize({ width: 768, height: 900 })
  await expect(page.getByRole('link', { name: 'dj-ledfx home' })).toBeVisible()
  expect(await page.evaluate(() => 'stillHere' in window)).toBe(true)
})

for (const width of [320, 360, 390, 768, 1024, 1199, 1440]) {
  test(`nothing scrolls sideways at ${width} px`, async ({ page }, { project }) => {
    test.skip(project.name !== 'desktop', 'one project is enough; this test sets the width')
    await page.setViewportSize({ width, height: 900 })
    await open(page, '/next/live')
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(width)
    if (width < 768) {
      // The phone tempo strip is fluid: TAP must stay inside it down to 320 px (WCAG reflow).
      const spill = await page.getByRole('group', { name: 'Tempo' }).evaluate((group) => {
        const rights = [...group.children].map((child) => child.getBoundingClientRect().right)
        return Math.max(...rights) - group.getBoundingClientRect().right
      })
      expect(spill).toBeLessThanOrEqual(0)
    }
  })
}
```

- [ ] **Step 4: Install the browser and type-check**

```bash
(cd web && npx playwright install chromium && npx tsc -b && npm run lint)
```

Expected: Chromium installs. On CachyOS Playwright warns that the OS isn't officially supported and falls back to its ubuntu24.04 build, which works. tsc and lint are clean.

- [ ] **Step 5: Run it; the screenshot tests fail because no baselines exist yet**

```bash
(cd web && npm run e2e)
```

Expected: `3 failed`, `37 passed`, `10 skipped`. The three failures read `A snapshot doesn't exist at …/live-desktop-linux.png, writing actual.`, and the same for `live-phone-linux.png` and `system-desktop-linux.png`. Playwright writes all three into `web/e2e/shell.spec.ts-snapshots/`.

Every axe, font, keyboard, resize and width test must already pass. If axe fails, fix the component, never the test or the axe rules.

- [ ] **Step 6: Compare the app with the renders by eye**

Look at each new baseline beside its reference.
- `live-desktop-linux.png` beside `Main.png`: compare the rail and the top bar. The stage and the Running panel are F2 and F3; F0 has a placeholder there.
- `live-phone-linux.png` beside `Phone-Live.png`: compare the header, the tempo strip and the tab bar.
  - The render leaves the top 47 px to the OS (§4.2). Chromium reports no safe-area inset, so the app's header starts at the top edge.
  - The render's live dot was caught mid-pulse, and its lit pip doesn't match its own beat label. Ignore both.
- `system-desktop-linux.png` beside `System.png`'s components: compare the buttons, controls, chips, tags and labels, the toast and the cluster.

If an element differs visibly in position, size, weight or colour, fix the code, delete that baseline and run Step 5 again. Note what you compared for the PR.

- [ ] **Step 7: Run it again to see it pass, twice**

```bash
(cd web && npm run e2e && npm run e2e)
```

Expected: `40 passed`, `10 skipped` both times. The phone project skips the desktop-only tests.

- [ ] **Step 8: Commit**

```bash
git add web/src/pages/system.tsx web/src/app/routes.tsx web/playwright.config.ts web/e2e
git commit -m "test: add the /system specimen and Playwright screenshots, axe, keyboard and reflow checks"
```

---

### Task 14: Code-architect review

Required by CLAUDE.md's skill guidelines: "Add @feature-dev:code-architect review step as a task for each plan you implement. Fix every issue that comes up during the code architect review step."

**Files:** whatever the findings touch.

- [ ] **Step 1: Dispatch the review**

Dispatch the `feature-dev:code-architect` agent with `model: "opus"` and this prompt:

```text
Review branch feature/web-f0-scaffold (git diff origin/master...HEAD) in /home/anirudhlath/code/.worktrees/dj-ledfx/web-f0.
It implements docs/superpowers/plans/2026-09-23-f0-web-app-scaffold.md: milestone F0 (M0) of
docs/superpowers/specs/2026-09-23-web-app-rebuild-design.md, plus engine spec §10 (the app lives in web/, served at /next).
Read the plan's Global Constraints, Decisions and Review Focus first. The Decisions are settled; don't reopen them.
Check:
- Architecture and boundaries between src/design, src/chrome, src/shell, src/app, src/pages and src/lib, so F1 (data
  layer) and F2/F3 (stage, Live) can build on them.
- CLAUDE.md "Web App Design": no retyped token values, and no arbitrary value equal to a token in tokens.css. The
  copies web/src/styles/tokens.css and web/src/design/icons.ts are byte-identical to docs/design/web-app.
- Accessibility: real buttons and links, names on icon-only controls, the keyboard path, landmarks, and touch targets on phone.
- The FastAPI /next routes: route order, path containment and cache headers.
- Test quality: every test fails for the right reason, and the Review Focus items are pinned.
Report every finding with file:line, severity and a concrete fix.
```

- [ ] **Step 2: Fix every finding, Minor included**

For each finding that changes behaviour, first write a test that fails, then fix. For a finding you believe is wrong, don't skip it. Explain why in the PR description, and ask the owner.

A note from planning: Vitest ran more than 200 times while this plan was written. Once, on a cold first run with the machine under load, one test failed, and the output wasn't kept. If you see a failure that passes on a rerun, keep the verbose log (`npx vitest run --reporter=verbose`), find the cause and fix it. Don't just raise timeouts.

- [ ] **Step 3: Re-run the gates**

```bash
(cd web && npm test && npx tsc -b && npm run lint && npm run e2e)
uv run pytest tests/web -q -p no:randomly
uv run mypy src/ 2>&1 | tail -1
```

Expected: everything passes, and the mypy count still equals the baseline. If a screenshot changed on purpose, compare it with the render again (Task 13, Step 6) before running `(cd web && npm run e2e -- --update-snapshots)`.

- [ ] **Step 4: Commit**

```bash
git add -A web src tests
git commit -m "fix: address code architect review findings"
```

---

### Task 15: Simplify pass

Required by CLAUDE.md: "Add /simplify skill step as a task for each plan you implement. Fix every issue that comes up during the simplify step." CLAUDE.md also says to use opus for it.

- [ ] **Step 1: Run `/simplify` over the branch**

Invoke the `simplify` skill on `git diff origin/master...HEAD`. If it dispatches agents, give them `model: "opus"`.

- [ ] **Step 2: Fix every finding**

These guardrails come from the Global Constraints:
- Never edit the payload copies.
- Never replace a token utility with an arbitrary value.
- Keep every Review Focus test.
- Keep the `bar`/`strip`/`header` variants' accessible names and roles as the tests pin them.

- [ ] **Step 3: Re-run the gates**

```bash
(cd web && npm test && npx tsc -b && npm run lint && npm run e2e)
uv run pytest tests/web -q -p no:randomly
```

Expected: everything passes. If a screenshot changed, check it by eye before updating it.

- [ ] **Step 4: Commit**

```bash
git add -A web src tests
git commit -m "refactor: address simplify review findings"
```

---

### Task 16: Revise CLAUDE.md

Required by CLAUDE.md: "Add claude md skill as a task to improve and revise claude context, memories etc." The Commands and Architecture sections gain `web/`. No design values go into the file: CLAUDE.md forbids restating them there.

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Invoke `claude-md-management:revise-claude-md`**

Use it to review what this branch taught. The edits below are the minimum; keep any others it proposes that meet the same no-design-values rule.

- [ ] **Step 2: Commands**

In the `## Commands` code block, after `cd frontend && npm run dev ...`, add:

```bash
cd web && npm install            # New web app (F0–F11): install dependencies
cd web && npm run dev            # Dev server at http://localhost:5174/next/ (proxies /api and /ws to :8080)
cd web && npm run build          # Type-check and build web/dist; FastAPI serves it at /next
cd web && npm test               # Vitest: unit and component tests
cd web && npm run lint           # ESLint (npx tsc -b type-checks)
cd web && npx playwright install chromium  # Once per machine
cd web && npm run e2e            # Playwright: screenshots, axe on every route, keyboard, reflow
```

- [ ] **Step 3: Architecture**

After the `frontend/` block, add:

```markdown
web/ (the rebuilt app, F0–F11: Vite + React 19 + TypeScript + Tailwind CSS v4 + Base UI; served at /next until F11):
- `src/styles/tokens.css`, `src/design/icons.ts` — byte copies of `docs/design/web-app/`; `src/design/payload.node.test.ts` fails if either drifts
- `src/design/` — the spec's §6.1 primitives and `Icon`
- `src/chrome/` — the §6.2 always-within-reach cluster; `state.ts` holds `ChromeState` and `useChrome()` (a hero fixture until F1/F3)
- `src/shell/` — rail, top bar, tab bar, phone header; `AppShell` swaps desktop and phone chrome at the phone breakpoint without remounting the page
- `src/app/` — routes (§4.3), each with a `PageMeta` handle for its titles and context lines
- `src/pages/` — placeholders, not-found and error pages, and the unlinked `/system` specimen
- `e2e/` — Playwright specs and the committed screenshot baselines
- `src/dj_ledfx/web/app.py` serves `web/dist` at `/next` (SPA fallback), registered before the old UI's catch-all
```

- [ ] **Step 4: Code Style and Gotchas**

In `## Code Style`, change two lines:
- "Frontend uses shadcn/ui components (based on @base-ui/react, NOT Radix — different APIs)" becomes "`frontend/` uses shadcn/ui components (based on @base-ui/react, NOT Radix — different APIs); `web/` uses @base-ui/react directly behind its own primitives in `src/design/`".
- "Frontend hooks in `src/hooks/`, one per domain (...)" starts with "`frontend/` hooks" instead of "Frontend hooks".

Append to `## Gotchas`:

```markdown
- Web app: tokens.css names both a colour and a font size `control`; `text-control` is the colour, `text-size-control` the size
- Web app: `web/src/styles/tokens.css` and `web/src/design/icons.ts` change only by `cp` from `docs/design/web-app/`; keep search-and-replace away from them
- Web app: where tokens.css has a token, use its utility (`text-data`, `h-(--touch-min)`), never an arbitrary value equal to it
- Web app: `@import "./tokens.css" theme(static)` keeps every token as a CSS variable, even ones no class uses
- Web app: Vite's dev and preview servers only answer below `/next/` — a bare `/next` is a 404 there and a missing asset gets index.html; FastAPI handles both (tests/web/test_next_static.py)
- Web app: Base UI tooltips are visual only; icon-only triggers still need `aria-label`
- Web app: jsdom has no `matchMedia`; component tests resize with `setViewportWidth()` from `src/test/viewport.ts`
- Web app: Playwright baselines are per OS (`*-linux.png`); re-record with `npm run e2e -- --update-snapshots` only after comparing with the reference renders by eye
```

- [ ] **Step 5: Check that no design values slipped in**

```bash
git diff CLAUDE.md | grep -nE '^\+.*(#[0-9a-fA-F]{6}|[0-9.]+ ?px|[0-9]+ × [0-9]+)'
```

Expected: no output.

- [ ] **Step 6: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add the new web app to CLAUDE.md"
```

---

### Task 17: Final gate and pull request

- [ ] **Step 1: The whole web gate, from a clean install**

```bash
(cd web && npm ci && npm test && npx tsc -b && npm run lint && npm run build && npm run e2e)
```

Expected: every step passes, and e2e prints `40 passed` and `10 skipped`.

- [ ] **Step 2: The whole Python gate**

```bash
uv run pytest -q -p no:randomly 2>&1 | tail -1
uv run ruff check .
uv run ruff format --check . 2>&1 | tail -1
uv run mypy src/ 2>&1 | tail -1
```

Expected:
- All tests pass: the baseline count plus Task 2's 15.
- `ruff check` is clean.
- `format --check` flags only the file it flagged at baseline.
- mypy prints the baseline count.

- [ ] **Step 3: Scope checks**

```bash
git diff --stat origin/master...HEAD -- frontend/ docs/design/
cmp docs/design/web-app/tokens.css web/src/styles/tokens.css && cmp docs/design/web-app/icons.ts web/src/design/icons.ts && echo "copies identical"
git status --short
```

Expected: no diff under `frontend/` or `docs/design/`; `copies identical`; a clean tree.

- [ ] **Step 4: Push and open the PR**

```bash
git push -u origin feature/web-f0-scaffold
gh pr create --base master --title "F0: web app scaffold, served at /next" --body-file - <<'EOF'
## Summary

Milestone F0 (the handoff's M0) of the web app rebuild, per docs/superpowers/plans/2026-09-23-f0-web-app-scaffold.md.

- `web/`: a fresh Vite + React 19 + TypeScript + Tailwind v4 app beside `frontend/`, which is untouched.
- The handoff's `tokens.css` and `icons.ts` are used as delivered, through byte copies with a drift test. The fonts are self-hosted.
- `Icon`, the §6.1 primitives, the §6.2 always-within-reach cluster, and the app shell (rail, top bar, phone header, tab bar).
- Every §4.3 route has a placeholder. There's a not-found page, an error page, and an unlinked `/system` specimen.
- FastAPI serves `web/dist` at `/next` with an SPA fallback. The old UI's fallback no longer follows `..` out of `frontend/dist`.
- CLAUDE.md gains `web/` in Commands, Architecture and Gotchas.

## Test plan

- [x] `cd web && npm test`: Vitest unit and component tests
- [x] `cd web && npm run e2e`: screenshots at 1440 × 900 and 390 × 844, axe on every route, self-hosted fonts, keyboard path, resize across 768 px, no sideways scroll from 320 to 1440 px
- [x] Baselines compared by eye with Main.png, Phone-Live.png and System.png
- [x] `uv run pytest`: including tests/web/test_next_static.py (/next, deep links, cache headers, missing assets, traversal)
- [x] ruff and mypy: no new findings against the master baseline

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
```

Expected: `gh` prints the PR's URL. Before creating it, add anything Task 14 or 15 left for the owner (Step 2 of Task 14) under a "For the owner" heading in the body.

---

## Coverage

| M0 (§13.1) and engine §10 | Task |
|---|---|
| Fresh Vite app, beside `frontend/` | 1 |
| Tokens (byte copy and drift test), fonts (self-hosted) | 1; fonts load in 13 |
| `Icon` | 3 |
| §6.1 primitives | 4, 5, 6, 7, 8 |
| §6.2 cluster, which the top bar and the phone header hold | 10 |
| App shell: rail, top bar, tab bar, phone header | 11, 12 |
| Routes with placeholders (§4.3) | 12 |
| Served at `/next` with an SPA fallback | 2 |
| Chrome matches `Main.png` at 1440 × 900 and `Phone-Live.png` at 390 × 844 | 13 |
| axe passes | 13 |
| Review, simplify, CLAUDE.md, PR (CLAUDE.md workflow) | 14, 15, 16, 17 |
