# Frontend — dj-ledfx Web UI

SvelteKit 2 + Svelte 5 (runes) + shadcn-svelte + Tailwind CSS v4

## Commands

```bash
npm run dev              # Dev server (proxies /api, /ws to localhost:8080)
npm run build            # Production build (static adapter)
npm run check            # Svelte type checking
npm run check:watch      # Svelte type checking (watch mode)
```

## shadcn-svelte Component Usage Guide

Use the RIGHT component for the RIGHT job. Don't reinvent what shadcn provides.

| Use Case | Component | Import Pattern |
|---|---|---|
| Mutually exclusive selection (effects, modes) | `ToggleGroup` `type="single"` | `* as ToggleGroup from .../toggle-group/index.js` |
| Multiple selection (tags, filters) | `ToggleGroup` `type="multiple"` | same |
| Dropdown selection from list (presets, options) | `Select` | `* as Select from .../select/index.js` |
| Progress/phase visualization | `Progress` | `{ Progress } from .../progress/index.js` |
| Resizable split layouts | `Resizable` (PaneGroup + Pane + Handle) | `* as Resizable from .../resizable/index.js` |
| Tabbed content sections (config categories) | `Tabs` | `* as Tabs from .../tabs/index.js` |
| Toast notifications (save, errors) | `Sonner` — use `toast()` from `svelte-sonner` | `import { toast } from 'svelte-sonner'` |
| Hover context for compact data | `Tooltip` | `* as Tooltip from .../tooltip/index.js` |
| Expandable sections (table rows, details) | `Collapsible` | `* as Collapsible from .../collapsible/index.js` |
| Loading placeholders | `Skeleton` | `{ Skeleton } from .../skeleton/index.js` |
| Modal forms (save preset, create group) | `Dialog` | `* as Dialog from .../dialog/index.js` |
| Popup forms/controls | `Popover` | `* as Popover from .../popover/index.js` |
| Slide-out panel (device details) | `Sheet` | `* as Sheet from .../sheet/index.js` |
| Data tables | `Table` (Header/Body/Row/Cell) | `* as Table from .../table/index.js` |
| Buttons, inputs, labels, sliders, switches | Direct imports | `{ Button } from .../button/index.js` |

## Component Conventions

- All shadcn imports use `/index.js` suffix: `'$lib/components/ui/button/index.js'`
- Namespace imports (`* as Card`) for multi-part components (Card.Root, Card.Content)
- Named imports (`{ Button }`) for single-export components
- Svelte 5 runes: `$state()`, `$derived()`, `$props()`, `$effect()`
- `bind:this` variables require `$state` declaration in Svelte 5
- Slider `type="single"` uses plain `number` value (not array)
- Sonner: add `<Toaster />` in root layout, use `toast()` anywhere
- Dark-only app: `class="dark"` on `<html>`, no theme switching

## Architecture

```
src/
├── app.css              # Tailwind v4 + shadcn theme variables
├── app.html             # HTML shell (dark mode forced)
├── lib/
│   ├── utils.ts         # cn() helper + type re-exports for shadcn
│   ├── components/
│   │   ├── ui/          # shadcn-svelte generated (DO NOT EDIT)
│   │   ├── common/      # Shared: LedIndicator
│   │   ├── transport/   # Beat display: BpmDisplay, BeatGrid, PhaseMeter, PlayState
│   │   └── deck/        # Effect control: EffectDeckPanel, DeviceMonitor, ParamSlider, PaletteEditor
│   ├── stores/          # Svelte 5 rune stores (beat, effects, devices)
│   ├── ws/              # WebSocket client (multiplexed, auto-reconnect)
│   └── api/             # REST API client
└── routes/
    ├── +layout.svelte   # App shell: nav, WS init, store init, Toaster
    ├── +layout.ts       # SSR disabled
    ├── +page.svelte     # Live view (transport, effects, devices)
    ├── devices/         # Device management
    ├── config/          # Configuration
    └── scene/           # 3D scene (Phase 2 placeholder)
```

## Data Layer (DO NOT MODIFY without backend coordination)

- `stores/beat.svelte.ts` — Beat state from WS, client-side phase interpolation
- `stores/effects.svelte.ts` — Effect schemas, active params, presets (REST + WS)
- `stores/devices.svelte.ts` — Device list, frame data, groups (REST + WS)
- `ws/client.ts` — Multiplexed WS with reconnection, binary frame parsing
- `api/client.ts` — Typed REST client for all backend endpoints
