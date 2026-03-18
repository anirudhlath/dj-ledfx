# shadcn-svelte UI Rebuild Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the dj-ledfx web UI frontend from scratch using SvelteKit 2 + shadcn-svelte with completely vanilla/default theme (zinc dark). No custom colors, fonts, or theme overrides. The old frontend has been deleted. Data layer files (stores, WS client, API client) are preserved at `/tmp/dj-ledfx-data-layer/` and will be restored.

**Architecture:** Scaffold a fresh SvelteKit project, initialize shadcn-svelte with Tailwind v4, install UI components, restore the data layer, then create all views and domain-specific components from scratch. Domain-specific components (BpmDisplay, BeatGrid, PhaseMeter, PlayState, DeviceMonitor, LedIndicator, PaletteEditor) are styled using only default shadcn CSS variables — no custom theme.

**Tech Stack:** SvelteKit 2, Svelte 5 (runes), shadcn-svelte, bits-ui, Tailwind CSS v4, TypeScript

**Spec:** `docs/superpowers/specs/2026-03-13-web-ui-design.md`

**Learnings from first attempt:**
- shadcn-svelte v1.1.1 requires `baseColor` in `components.json` — use `"zinc"`
- Generated components import `WithElementRef`, `WithoutChild`, `WithoutChildrenOrChild` from `$lib/utils.ts` — must re-export from `bits-ui` and `svelte-toolbelt`
- `tailwind-variants` IS used by shadcn badge/button — do not remove
- shadcn-svelte Slider `type="single"` uses plain `number` value (not array)
- ParamSlider: no local state needed — pass `value` prop directly, use `onValueChange`/`onCheckedChange` callbacks
- Config page Import TOML: use programmatic `fileInput.click()`, not `<label>` wrapper (fragile with component libraries)
- Svelte 5 `bind:this` variables need `$state` declaration
- Use completely vanilla shadcn-svelte theme — no custom colors, no custom fonts, no overrides

---

## Chunk 1: Project Scaffold

Create a fresh SvelteKit project from scratch with all tooling.

### Task 1: Create SvelteKit project structure

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/.npmrc`
- Create: `frontend/.gitignore`
- Create: `frontend/svelte.config.js`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/src/app.d.ts`
- Create: `frontend/src/routes/+layout.ts`

- [ ] **Step 1: Create frontend directory**

```bash
mkdir -p frontend/src/routes frontend/src/lib frontend/static
```

- [ ] **Step 2: Create package.json**

Create `frontend/package.json`:

```json
{
  "name": "frontend",
  "private": true,
  "version": "0.0.1",
  "type": "module",
  "scripts": {
    "dev": "vite dev",
    "build": "vite build",
    "preview": "vite preview",
    "prepare": "svelte-kit sync || echo ''",
    "check": "svelte-kit sync && svelte-check --tsconfig ./tsconfig.json",
    "check:watch": "svelte-kit sync && svelte-check --tsconfig ./tsconfig.json --watch"
  },
  "devDependencies": {
    "@sveltejs/adapter-auto": "^7.0.0",
    "@sveltejs/adapter-static": "^3.0.10",
    "@sveltejs/kit": "^2.50.2",
    "@sveltejs/vite-plugin-svelte": "^6.2.4",
    "@tailwindcss/vite": "^4.2.1",
    "@types/three": "^0.183.1",
    "bits-ui": "^2.16.3",
    "clsx": "^2.1.1",
    "svelte": "^5.51.0",
    "svelte-check": "^4.4.2",
    "tailwind-merge": "^3.5.0",
    "tailwind-variants": "^3.2.2",
    "tailwindcss": "^4.2.1",
    "tw-animate-css": "^1.4.0",
    "typescript": "^5.9.3",
    "vite": "^7.3.1"
  },
  "dependencies": {
    "@threlte/core": "^8.5.0",
    "@threlte/extras": "^9.9.0",
    "three": "^0.183.2"
  }
}
```

- [ ] **Step 3: Create config files**

Create `frontend/.npmrc`:
```
engine-strict=true
```

Create `frontend/.gitignore`:
```
node_modules
.svelte-kit
build
.vite
```

Create `frontend/svelte.config.js`:
```javascript
import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

export default {
	preprocess: vitePreprocess(),
	kit: { adapter: adapter({ fallback: 'index.html' }) }
};
```

Create `frontend/vite.config.ts`:
```typescript
import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit()],
	server: {
		proxy: {
			'/api': 'http://localhost:8080',
			'/ws': { target: 'ws://localhost:8080', ws: true }
		}
	}
});
```

Create `frontend/tsconfig.json`:
```json
{
  "extends": "./.svelte-kit/tsconfig.json",
  "compilerOptions": {
    "rewriteRelativeImportExtensions": true,
    "allowJs": true,
    "checkJs": true,
    "esModuleInterop": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "skipLibCheck": true,
    "sourceMap": true,
    "strict": true,
    "moduleResolution": "bundler"
  }
}
```

Create `frontend/src/app.d.ts`:
```typescript
declare global {
	namespace App {}
}

export {};
```

Create `frontend/src/routes/+layout.ts`:
```typescript
export const ssr = false;
export const prerender = false;
```

- [ ] **Step 4: Install dependencies**

```bash
cd frontend && npm install
```

- [ ] **Step 5: Run svelte-kit sync**

```bash
cd frontend && npx svelte-kit sync
```

- [ ] **Step 6: Commit**

```bash
cd frontend && git add -A && git commit -m "build: scaffold fresh SvelteKit project"
```

### Task 2: Initialize shadcn-svelte and create theme

**Files:**
- Create: `frontend/components.json`
- Create: `frontend/src/app.css`
- Create: `frontend/src/app.html`
- Create: `frontend/src/lib/utils.ts`
- Create: `frontend/src/lib/components/ui/` (generated)

- [ ] **Step 1: Create utils.ts**

Create `frontend/src/lib/utils.ts`:

```typescript
import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
	return twMerge(clsx(inputs));
}

export type { WithElementRef } from 'bits-ui';
export type { WithoutChild, WithoutChildrenOrChild } from 'svelte-toolbelt';
```

Note: The type re-exports are required by shadcn-svelte generated components.

- [ ] **Step 2: Create components.json**

Create `frontend/components.json`:

```json
{
  "$schema": "https://shadcn-svelte.com/schema.json",
  "style": "default",
  "tailwind": {
    "css": "src/app.css",
    "baseColor": "zinc"
  },
  "typescript": true,
  "aliases": {
    "utils": "$lib/utils",
    "components": "$lib/components",
    "hooks": "$lib/hooks",
    "ui": "$lib/components/ui"
  },
  "registry": "https://shadcn-svelte.com/registry"
}
```

- [ ] **Step 3: Run shadcn-svelte init**

Run the shadcn-svelte CLI to generate `app.css`, `app.html`, and theme config. Use zinc base color, default style, dark mode via class. Accept all defaults — do NOT customize the generated theme in any way.

```bash
cd frontend && npx shadcn-svelte@latest init
```

After init completes, add `class="dark"` to the `<html>` tag in `src/app.html` to force dark mode (this is a dark-only app).

- [ ] **Step 4: Install shadcn-svelte components**

```bash
cd frontend && npx shadcn-svelte@latest add button card input label slider switch table badge separator select scroll-area
```

Accept all prompts. This generates files into `src/lib/components/ui/`.

- [ ] **Step 5: Verify components installed**

```bash
ls frontend/src/lib/components/ui/
```

Expected: directories for button, card, input, label, slider, switch, table, badge, separator, select, scroll-area.

- [ ] **Step 6: Verify dev server starts**

```bash
cd frontend && npm run dev -- --port 5173
```

Expected: Vite starts without CSS errors. The app will show a blank page (no routes yet).

- [ ] **Step 7: Commit**

```bash
cd frontend && git add -A && git commit -m "feat: initialize shadcn-svelte with default zinc dark theme"
```

### Task 3: Restore data layer files

**Files:**
- Create: `frontend/src/lib/stores/beat.svelte.ts` (from backup)
- Create: `frontend/src/lib/stores/effects.svelte.ts` (from backup)
- Create: `frontend/src/lib/stores/devices.svelte.ts` (from backup)
- Create: `frontend/src/lib/ws/client.ts` (from backup)
- Create: `frontend/src/lib/api/client.ts` (from backup)

- [ ] **Step 1: Copy data layer files from backup**

```bash
cd frontend
mkdir -p src/lib/stores src/lib/ws src/lib/api
cp /tmp/dj-ledfx-data-layer/stores/*.ts src/lib/stores/
cp /tmp/dj-ledfx-data-layer/ws/client.ts src/lib/ws/
cp /tmp/dj-ledfx-data-layer/api/client.ts src/lib/api/
```

- [ ] **Step 2: Verify files restored**

```bash
ls frontend/src/lib/stores/ frontend/src/lib/ws/ frontend/src/lib/api/
```

Expected: `beat.svelte.ts`, `effects.svelte.ts`, `devices.svelte.ts` in stores; `client.ts` in ws and api.

- [ ] **Step 3: Commit**

```bash
cd frontend && git add -A && git commit -m "feat: restore data layer (stores, WS client, API client)"
```

---

## Chunk 2: Create Custom Components

Domain-specific components that have no shadcn equivalent. Each uses shadcn CSS variables and matches shadcn's visual conventions.

### Task 4: Create LedIndicator

**Files:**
- Create: `frontend/src/lib/components/common/LedIndicator.svelte`

- [ ] **Step 1: Create LedIndicator**

```bash
mkdir -p frontend/src/lib/components/common
```

A small colored dot for device status. No glow/pulse effects:

```svelte
<script lang="ts">
  interface Props {
    color?: 'green' | 'red' | 'amber' | 'primary' | 'off';
    size?: 'sm' | 'md';
  }
  let { color = 'off', size = 'md' }: Props = $props();

  const colorMap: Record<string, string> = {
    green: 'bg-green-500',
    red: 'bg-red-500',
    amber: 'bg-amber-500',
    primary: 'bg-primary',
    off: 'bg-muted',
  };
</script>

<span
  class="inline-block rounded-full shrink-0
    {size === 'sm' ? 'h-2 w-2' : 'h-2.5 w-2.5'}
    {colorMap[color] ?? 'bg-muted'}"
></span>
```

- [ ] **Step 2: Commit**

```bash
cd frontend && git add src/lib/components/common/ && git commit -m "feat: create LedIndicator component"
```

### Task 5: Create transport components (BpmDisplay, BeatGrid, PhaseMeter, PlayState)

**Files:**
- Create: `frontend/src/lib/components/transport/BpmDisplay.svelte`
- Create: `frontend/src/lib/components/transport/BeatGrid.svelte`
- Create: `frontend/src/lib/components/transport/PhaseMeter.svelte`
- Create: `frontend/src/lib/components/transport/PlayState.svelte`

- [ ] **Step 1: Create directory**

```bash
mkdir -p frontend/src/lib/components/transport
```

- [ ] **Step 2: Create BpmDisplay**

Large BPM number with muted metadata:

```svelte
<script lang="ts">
  import { beatStore } from '$lib/stores/beat.svelte';
</script>

<div class="flex flex-col">
  <span class="text-5xl font-bold tabular-nums tracking-tight text-foreground">
    {beatStore.bpm > 0 ? beatStore.bpm.toFixed(1) : '---.-'}
  </span>
  <span class="text-xs text-muted-foreground mt-1">
    BPM{#if beatStore.pitchPercent}&ensp;·&ensp;{beatStore.pitchPercent > 0 ? '+' : ''}{beatStore.pitchPercent.toFixed(1)}%{/if}{#if beatStore.deckName}&ensp;·&ensp;{beatStore.deckName}{/if}
  </span>
</div>
```

- [ ] **Step 3: Create BeatGrid**

Four beat position boxes highlighting the active beat:

```svelte
<script lang="ts">
  import { beatStore } from '$lib/stores/beat.svelte';
</script>

<div class="flex gap-1.5 items-center">
  {#each [1, 2, 3, 4] as beat}
    {@const active = beatStore.beatPos === beat && beatStore.isPlaying}
    <div
      class="w-9 h-9 rounded-md flex items-center justify-center text-sm font-medium transition-colors
        {active ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'}"
    >
      {beat}
    </div>
  {/each}
</div>
```

- [ ] **Step 4: Create PhaseMeter**

Thin progress bar:

```svelte
<script lang="ts">
  interface Props {
    value: number;
    label: string;
  }
  let { value, label }: Props = $props();
</script>

<div class="flex items-center gap-3">
  <span class="text-[10px] uppercase text-muted-foreground tracking-wider w-8 shrink-0 text-right">
    {label}
  </span>
  <div class="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
    <div
      class="h-full rounded-full bg-primary transition-[width] duration-75"
      style="width: {value * 100}%;"
    ></div>
  </div>
</div>
```

- [ ] **Step 5: Create PlayState**

Play/pause icon:

```svelte
<script lang="ts">
  import { beatStore } from '$lib/stores/beat.svelte';
</script>

<div class="flex items-center justify-center w-10 h-10 rounded-md {beatStore.isPlaying ? 'bg-accent' : 'bg-muted'}">
  {#if beatStore.isPlaying}
    <svg viewBox="0 0 24 24" class="w-5 h-5 fill-foreground">
      <path d="M8 5v14l11-7z"/>
    </svg>
  {:else}
    <svg viewBox="0 0 24 24" class="w-4 h-4 fill-muted-foreground">
      <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
    </svg>
  {/if}
</div>
```

- [ ] **Step 6: Commit**

```bash
cd frontend && git add src/lib/components/transport/ && git commit -m "feat: create transport components (BpmDisplay, BeatGrid, PhaseMeter, PlayState)"
```

### Task 6: Create deck helpers (PaletteEditor, ParamSlider)

**Files:**
- Create: `frontend/src/lib/components/deck/PaletteEditor.svelte`
- Create: `frontend/src/lib/components/deck/ParamSlider.svelte`

- [ ] **Step 1: Create directory**

```bash
mkdir -p frontend/src/lib/components/deck
```

- [ ] **Step 2: Create PaletteEditor**

Row of color inputs:

```svelte
<script lang="ts">
  import { Label } from '$lib/components/ui/label/index.js';

  interface Props {
    colors: string[];
    onchange: (colors: string[]) => void;
  }
  let { colors, onchange }: Props = $props();

  function updateColor(index: number, value: string) {
    const newColors = [...colors];
    newColors[index] = value;
    onchange(newColors);
  }
</script>

<div class="flex flex-col gap-2">
  <Label class="text-xs">Palette</Label>
  <div class="flex gap-1.5 flex-wrap">
    {#each colors as color, i}
      <input
        type="color"
        value={color}
        onchange={(e) => updateColor(i, (e.target as HTMLInputElement).value)}
        class="w-8 h-8 rounded-md border border-input bg-transparent cursor-pointer"
      />
    {/each}
  </div>
</div>
```

- [ ] **Step 3: Create ParamSlider**

Dispatches to shadcn Slider (float/int) or Switch (bool). Uses callback pattern — no local state needed:

```svelte
<script lang="ts">
  import type { EffectParamSchema } from '$lib/api/client';
  import { Slider } from '$lib/components/ui/slider/index.js';
  import { Switch } from '$lib/components/ui/switch/index.js';
  import { Label } from '$lib/components/ui/label/index.js';

  interface Props {
    name: string;
    schema: EffectParamSchema;
    value: unknown;
    onchange: (value: unknown) => void;
  }
  let { name, schema, value, onchange }: Props = $props();
</script>

{#if schema.type === 'float' || schema.type === 'int'}
  <div class="flex flex-col gap-2">
    <div class="flex items-baseline justify-between">
      <Label class="text-xs">{schema.label || name}</Label>
      <span class="text-xs text-muted-foreground tabular-nums font-mono">
        {(value as number).toFixed(schema.step && schema.step < 1 ? 1 : 0)}
      </span>
    </div>
    <Slider
      type="single"
      value={value as number}
      min={schema.min ?? 0}
      max={schema.max ?? 100}
      step={schema.step ?? (schema.type === 'int' ? 1 : 0.1)}
      onValueChange={(v) => onchange(v)}
    />
  </div>
{:else if schema.type === 'bool'}
  <div class="flex items-center gap-3">
    <Switch
      checked={value as boolean}
      onCheckedChange={(v) => onchange(v)}
    />
    <Label class="text-xs">{schema.label || name}</Label>
  </div>
{/if}
```

Note: shadcn-svelte Slider with `type="single"` accepts a plain `number` (not array). The `value` prop is reactive — no local state + $effect sync needed.

- [ ] **Step 4: Commit**

```bash
cd frontend && git add src/lib/components/deck/PaletteEditor.svelte src/lib/components/deck/ParamSlider.svelte && git commit -m "feat: create ParamSlider and PaletteEditor"
```

### Task 7: Create EffectDeckPanel and DeviceMonitor

**Files:**
- Create: `frontend/src/lib/components/deck/EffectDeckPanel.svelte`
- Create: `frontend/src/lib/components/deck/DeviceMonitor.svelte`

- [ ] **Step 1: Create EffectDeckPanel**

Right sidebar — effect selector, parameters, presets:

```svelte
<script lang="ts">
  import { effectsStore } from '$lib/stores/effects.svelte';
  import { Button } from '$lib/components/ui/button/index.js';
  import { Input } from '$lib/components/ui/input/index.js';
  import { Label } from '$lib/components/ui/label/index.js';
  import { Separator } from '$lib/components/ui/separator/index.js';
  import ParamSlider from './ParamSlider.svelte';
  import PaletteEditor from './PaletteEditor.svelte';

  let presetName = $state('');
</script>

<div class="flex flex-col h-full bg-card border-l border-border overflow-y-auto">
  <!-- Effect selector -->
  <div class="p-4">
    <Label class="text-xs text-muted-foreground mb-2 block">Effect</Label>
    <div class="flex gap-1.5 flex-wrap">
      {#each Object.keys(effectsStore.effectSchemas) as name}
        <Button
          variant={effectsStore.activeEffect === name ? 'default' : 'outline'}
          size="sm"
          onclick={() => effectsStore.switchEffect(name)}
        >
          {name.replace(/_/g, ' ')}
        </Button>
      {/each}
    </div>
  </div>

  <Separator />

  <!-- Parameters -->
  {#if effectsStore.effectSchemas[effectsStore.activeEffect]}
    <div class="p-4 flex flex-col gap-4">
      <Label class="text-xs text-muted-foreground">Parameters</Label>
      {#each Object.entries(effectsStore.effectSchemas[effectsStore.activeEffect]) as [key, schema]}
        {#if schema.type === 'color_list'}
          <PaletteEditor
            colors={(effectsStore.activeParams[key] as string[]) || schema.default as string[]}
            onchange={(colors) => effectsStore.updateParam(key, colors)}
          />
        {:else}
          <ParamSlider
            name={key}
            {schema}
            value={effectsStore.activeParams[key] ?? schema.default}
            onchange={(v) => effectsStore.updateParam(key, v)}
          />
        {/if}
      {/each}
    </div>
  {/if}

  <Separator />

  <!-- Presets -->
  <div class="p-4 mt-auto">
    <Label class="text-xs text-muted-foreground mb-2 block">Presets</Label>
    {#if effectsStore.presets.length > 0}
      <div class="flex gap-1.5 flex-wrap mb-3">
        {#each effectsStore.presets as preset}
          <Button variant="outline" size="sm" onclick={() => effectsStore.loadPreset(preset.name)}>
            {preset.name}
          </Button>
        {/each}
      </div>
    {/if}
    <div class="flex gap-1.5">
      <Input
        bind:value={presetName}
        placeholder="Save as..."
        class="text-xs"
      />
      <Button
        size="sm"
        disabled={!presetName}
        onclick={() => { effectsStore.savePreset(presetName); presetName = ''; }}
      >
        Save
      </Button>
    </div>
  </div>
</div>
```

- [ ] **Step 2: Create DeviceMonitor**

Compact device tile with LED color visualization:

```svelte
<script lang="ts">
  import type { Device } from '$lib/api/client';
  import LedIndicator from '$lib/components/common/LedIndicator.svelte';
  import { devicesStore } from '$lib/stores/devices.svelte';

  interface Props {
    device: Device;
  }
  let { device }: Props = $props();

  type DeviceVisual = 'point' | 'segment' | 'matrix';

  let visual = $derived.by((): DeviceVisual => {
    if (device.led_count <= 1) return 'point';
    if (device.device_type.includes('matrix')) return 'matrix';
    return 'segment';
  });

  let frameColors = $derived.by(() => {
    const frame = devicesStore.frameData.get(device.name);
    if (!frame || frame.rgb.length < 3) return [];
    const count = Math.min(device.led_count, Math.floor(frame.rgb.length / 3));
    const colors: string[] = [];
    for (let i = 0; i < count; i++) {
      colors.push(`rgb(${frame.rgb[i * 3]}, ${frame.rgb[i * 3 + 1]}, ${frame.rgb[i * 3 + 2]})`);
    }
    return colors;
  });

  let avgColor = $derived.by(() => {
    if (frameColors.length === 0) return null;
    return frameColors[0];
  });
</script>

<div class="flex items-center gap-2.5 px-3 py-2 rounded-md border border-border bg-card min-w-[160px]">
  <LedIndicator color={device.connected ? 'green' : 'red'} size="sm" />
  <div class="flex flex-col min-w-0 shrink-0">
    <span class="text-xs text-foreground truncate max-w-[120px]">
      {device.name}
    </span>
    <div class="flex items-center gap-2 text-[10px] text-muted-foreground tabular-nums">
      <span>{device.send_fps.toFixed(0)}fps</span>
      <span>{device.effective_latency_ms.toFixed(0)}ms</span>
    </div>
  </div>

  <!-- LED visualization -->
  <div class="ml-auto shrink-0">
    {#if visual === 'point'}
      <div
        class="w-4 h-4 rounded-full border border-border"
        style="background: {avgColor ?? 'hsl(var(--muted))'};"
      ></div>
    {:else if visual === 'matrix'}
      {@const size = Math.ceil(Math.sqrt(frameColors.length))}
      <div class="grid gap-px" style="grid-template-columns: repeat({size}, 1fr);">
        {#each frameColors as color}
          <div class="w-1 h-1 rounded-[1px]" style="background: {color};"></div>
        {/each}
      </div>
    {:else}
      <div class="flex gap-px">
        {#each frameColors as color}
          <div class="w-1 h-4 rounded-[1px]" style="background: {color};"></div>
        {/each}
      </div>
    {/if}
  </div>
</div>
```

- [ ] **Step 3: Commit**

```bash
cd frontend && git add src/lib/components/deck/ && git commit -m "feat: create EffectDeckPanel and DeviceMonitor"
```

---

## Chunk 3: Create Route Views

### Task 8: Create layout (navigation)

**Files:**
- Create: `frontend/src/routes/+layout.svelte`

- [ ] **Step 1: Create +layout.svelte**

```svelte
<script lang="ts">
  import '../app.css';
  import type { Snippet } from 'svelte';
  import { wsClient } from '$lib/ws/client';
  import { beatStore } from '$lib/stores/beat.svelte';
  import { effectsStore } from '$lib/stores/effects.svelte';
  import { devicesStore } from '$lib/stores/devices.svelte';
  import { onMount } from 'svelte';
  import { page } from '$app/state';
  import LedIndicator from '$lib/components/common/LedIndicator.svelte';

  interface Props {
    children: Snippet;
  }
  let { children }: Props = $props();

  const tabs = [
    { label: 'LIVE', href: '/' },
    { label: 'SCENE', href: '/scene' },
    { label: 'DEVICES', href: '/devices' },
    { label: 'CONFIG', href: '/config' },
  ];

  onMount(() => {
    wsClient.connect();
    wsClient.subscribeBeat(30);
    wsClient.subscribeFrames(30);
    effectsStore.init();
    devicesStore.init();
    beatStore.startInterpolation();

    return () => {
      wsClient.disconnect();
      beatStore.stopInterpolation();
    };
  });
</script>

<div class="h-screen flex flex-col bg-background overflow-hidden">
  <nav class="h-11 flex items-center px-4 bg-card border-b border-border shrink-0">
    <span class="text-sm font-bold mr-6 tracking-widest select-none">
      dj-ledfx
    </span>

    <div class="flex gap-1">
      {#each tabs as tab}
        {@const active = page.url.pathname === tab.href}
        <a
          href={tab.href}
          class="px-3 py-1.5 text-xs font-medium rounded-md transition-colors
            {active
              ? 'bg-accent text-accent-foreground'
              : 'text-muted-foreground hover:text-foreground hover:bg-accent/50'}"
        >
          {tab.label}
        </a>
      {/each}
    </div>

    <div class="ml-auto flex items-center gap-4 text-xs text-muted-foreground">
      <span class="flex items-center gap-1.5">
        <LedIndicator color={beatStore.wsConnected ? 'green' : 'red'} size="sm" />
        WS
      </span>
      <span class="flex items-center gap-1.5">
        <LedIndicator color={beatStore.isPlaying ? 'primary' : 'off'} size="sm" />
        {beatStore.isPlaying ? 'PLAYING' : 'STOPPED'}
      </span>
    </div>
  </nav>

  <main class="flex-1 overflow-hidden">
    {@render children()}
  </main>
</div>
```

- [ ] **Step 2: Commit**

```bash
cd frontend && git add src/routes/+layout.svelte && git commit -m "feat: create layout with shadcn navigation"
```

### Task 9: Create Live view (+page.svelte)

**Files:**
- Create: `frontend/src/routes/+page.svelte`

- [ ] **Step 1: Create +page.svelte**

```svelte
<script lang="ts">
  import * as Card from '$lib/components/ui/card/index.js';
  import BpmDisplay from '$lib/components/transport/BpmDisplay.svelte';
  import BeatGrid from '$lib/components/transport/BeatGrid.svelte';
  import PhaseMeter from '$lib/components/transport/PhaseMeter.svelte';
  import PlayState from '$lib/components/transport/PlayState.svelte';
  import EffectDeckPanel from '$lib/components/deck/EffectDeckPanel.svelte';
  import DeviceMonitor from '$lib/components/deck/DeviceMonitor.svelte';
  import { beatStore } from '$lib/stores/beat.svelte';
  import { devicesStore } from '$lib/stores/devices.svelte';
</script>

<div class="h-full flex flex-col">
  <div class="flex-1 flex min-h-0">
    <!-- Left: Transport + Scene preview -->
    <div class="flex-1 flex flex-col min-h-0 p-4 gap-4">
      <!-- Transport -->
      <Card.Root>
        <Card.Content class="flex items-center gap-6 py-4">
          <BpmDisplay />
          <div class="flex flex-col gap-2 flex-1 max-w-sm">
            <BeatGrid />
            <PhaseMeter value={beatStore.beatPhase} label="BEAT" />
            <PhaseMeter value={beatStore.barPhase} label="BAR" />
          </div>
          <PlayState />
        </Card.Content>
      </Card.Root>

      <!-- Scene preview placeholder -->
      <Card.Root class="flex-1">
        <Card.Content class="flex items-center justify-center h-full">
          <p class="text-sm text-muted-foreground">Scene Preview — Phase 2</p>
        </Card.Content>
      </Card.Root>
    </div>

    <!-- Right: Effect deck sidebar -->
    <div class="w-80 shrink-0">
      <EffectDeckPanel />
    </div>
  </div>

  <!-- Device monitor strip -->
  {#if devicesStore.devices.length > 0}
    <div class="flex gap-2 px-4 py-2 border-t border-border overflow-x-auto shrink-0">
      {#each devicesStore.devices as device}
        <DeviceMonitor {device} />
      {/each}
    </div>
  {/if}
</div>
```

- [ ] **Step 2: Commit**

```bash
cd frontend && git add src/routes/+page.svelte && git commit -m "feat: create Live view with shadcn Card layout"
```

### Task 10: Create Devices view

**Files:**
- Create: `frontend/src/routes/devices/+page.svelte`

- [ ] **Step 1: Create devices directory and page**

```bash
mkdir -p frontend/src/routes/devices
```

```svelte
<script lang="ts">
  import { devicesStore } from '$lib/stores/devices.svelte';
  import { Button } from '$lib/components/ui/button/index.js';
  import { Input } from '$lib/components/ui/input/index.js';
  import { Badge } from '$lib/components/ui/badge/index.js';
  import * as Table from '$lib/components/ui/table/index.js';
  import * as Card from '$lib/components/ui/card/index.js';
  import LedIndicator from '$lib/components/common/LedIndicator.svelte';

  let expandedDevice = $state<string | null>(null);
  let newGroupName = $state('');
  let newGroupColor = $state('#ffffff');
  let discovering = $state(false);

  async function handleDiscover() {
    discovering = true;
    await devicesStore.discover();
    discovering = false;
  }
</script>

<div class="h-full overflow-y-auto p-6 flex flex-col gap-6 max-w-5xl mx-auto">
  <!-- Header -->
  <div class="flex items-center justify-between">
    <h2 class="text-lg font-semibold">Devices</h2>
    <Button onclick={handleDiscover} disabled={discovering}>
      {discovering ? 'Scanning...' : 'Scan for Devices'}
    </Button>
  </div>

  <!-- Device table -->
  <Card.Root>
    <Table.Root>
      <Table.Header>
        <Table.Row>
          <Table.Head class="w-10"></Table.Head>
          <Table.Head>Name</Table.Head>
          <Table.Head>Type</Table.Head>
          <Table.Head class="text-right">LEDs</Table.Head>
          <Table.Head>Address</Table.Head>
          <Table.Head>Group</Table.Head>
          <Table.Head class="text-right">FPS</Table.Head>
          <Table.Head class="text-right">Latency</Table.Head>
        </Table.Row>
      </Table.Header>
      <Table.Body>
        {#each devicesStore.devices as device}
          <Table.Row
            class="cursor-pointer"
            onclick={() => expandedDevice = expandedDevice === device.name ? null : device.name}
          >
            <Table.Cell><LedIndicator color={device.connected ? 'green' : 'red'} /></Table.Cell>
            <Table.Cell class="font-medium">{device.name}</Table.Cell>
            <Table.Cell class="text-muted-foreground">{device.device_type}</Table.Cell>
            <Table.Cell class="text-right tabular-nums">{device.led_count}</Table.Cell>
            <Table.Cell class="text-muted-foreground text-xs">{device.address}</Table.Cell>
            <Table.Cell>
              {#if device.group}
                <Badge variant="secondary">{device.group}</Badge>
              {:else}
                <span class="text-muted-foreground">—</span>
              {/if}
            </Table.Cell>
            <Table.Cell class="text-right tabular-nums">{device.send_fps.toFixed(0)}</Table.Cell>
            <Table.Cell class="text-right tabular-nums">{device.effective_latency_ms.toFixed(0)}ms</Table.Cell>
          </Table.Row>
          {#if expandedDevice === device.name}
            <Table.Row>
              <Table.Cell colspan={8} class="bg-muted/50">
                <div class="flex gap-3 items-center py-1">
                  <Button variant="outline" size="sm" onclick={() => devicesStore.identify(device.name)}>
                    Identify
                  </Button>
                  <span class="text-xs text-muted-foreground">
                    Frames dropped: {device.frames_dropped}
                  </span>
                </div>
              </Table.Cell>
            </Table.Row>
          {/if}
        {/each}
        {#if devicesStore.devices.length === 0}
          <Table.Row>
            <Table.Cell colspan={8} class="text-center text-muted-foreground py-10">
              No devices found. Click "Scan for Devices" to discover.
            </Table.Cell>
          </Table.Row>
        {/if}
      </Table.Body>
    </Table.Root>
  </Card.Root>

  <!-- Groups -->
  <Card.Root>
    <Card.Header>
      <Card.Title class="text-sm">Groups</Card.Title>
    </Card.Header>
    <Card.Content>
      <div class="flex gap-2 flex-wrap mb-4">
        {#each Object.entries(devicesStore.groups) as [name, group]}
          <Badge variant="outline" class="gap-2">
            <span class="w-2 h-2 rounded-full inline-block" style="background: {group.color};"></span>
            {name}
            <button
              class="text-muted-foreground hover:text-destructive text-xs cursor-pointer"
              onclick={() => devicesStore.deleteGroup(name)}
            >✕</button>
          </Badge>
        {/each}
      </div>
      <div class="flex gap-2 items-center">
        <Input
          bind:value={newGroupName}
          placeholder="Group name"
          class="max-w-[200px] text-sm"
        />
        <input type="color" bind:value={newGroupColor}
          class="w-8 h-8 rounded-md border border-input bg-transparent cursor-pointer" />
        <Button
          size="sm"
          disabled={!newGroupName}
          onclick={() => { devicesStore.createGroup(newGroupName, newGroupColor); newGroupName = ''; }}
        >
          Create
        </Button>
      </div>
    </Card.Content>
  </Card.Root>
</div>
```

- [ ] **Step 2: Commit**

```bash
cd frontend && git add src/routes/devices/ && git commit -m "feat: create Devices view with shadcn Table and Card"
```

### Task 11: Create Config view

**Files:**
- Create: `frontend/src/routes/config/+page.svelte`

- [ ] **Step 1: Create config directory and page**

```bash
mkdir -p frontend/src/routes/config
```

```svelte
<script lang="ts">
  import { onMount } from 'svelte';
  import * as api from '$lib/api/client';
  import { Button } from '$lib/components/ui/button/index.js';
  import { Input } from '$lib/components/ui/input/index.js';
  import { Label } from '$lib/components/ui/label/index.js';
  import { Slider } from '$lib/components/ui/slider/index.js';
  import { Switch } from '$lib/components/ui/switch/index.js';
  import * as Card from '$lib/components/ui/card/index.js';

  let config = $state<api.AppConfig | null>(null);
  let saving = $state(false);
  let message = $state('');
  let fileInput = $state<HTMLInputElement>(undefined!);

  onMount(async () => {
    config = await api.getConfig();
  });

  async function saveConfig() {
    if (!config) return;
    saving = true;
    try {
      config = await api.updateConfig(config);
      message = 'Config saved';
      setTimeout(() => message = '', 3000);
    } catch (e) {
      message = `Error: ${e}`;
    } finally {
      saving = false;
    }
  }

  async function handleExport() {
    const toml = await api.exportConfig();
    const blob = new Blob([toml], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'dj-ledfx-config.toml';
    a.click();
    URL.revokeObjectURL(url);
  }

  async function handleImport(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    const text = await file.text();
    try {
      config = await api.importConfig(text);
      message = 'Config imported';
      setTimeout(() => message = '', 3000);
    } catch (err) {
      message = `Import error: ${err}`;
    }
  }
</script>

<div class="h-full overflow-y-auto p-6 max-w-3xl mx-auto flex flex-col gap-6">
  <h2 class="text-lg font-semibold">Configuration</h2>

  {#if config}
    <!-- Engine -->
    <Card.Root>
      <Card.Header>
        <Card.Title class="text-sm">Engine</Card.Title>
      </Card.Header>
      <Card.Content class="grid grid-cols-2 gap-6">
        <div class="flex flex-col gap-2">
          <div class="flex items-baseline justify-between">
            <Label class="text-xs">FPS</Label>
            <span class="text-xs text-muted-foreground tabular-nums font-mono">{config.engine.fps}</span>
          </div>
          <Slider
            type="single"
            bind:value={config.engine.fps}
            min={30}
            max={120}
            step={1}
          />
        </div>
        <div class="flex flex-col gap-2">
          <div class="flex items-baseline justify-between">
            <Label class="text-xs">Max Lookahead</Label>
            <span class="text-xs text-muted-foreground tabular-nums font-mono">{config.engine.max_lookahead_ms}ms</span>
          </div>
          <Slider
            type="single"
            bind:value={config.engine.max_lookahead_ms}
            min={500}
            max={2000}
            step={50}
          />
        </div>
      </Card.Content>
    </Card.Root>

    <!-- Network -->
    <Card.Root>
      <Card.Header>
        <Card.Title class="text-sm">Network</Card.Title>
      </Card.Header>
      <Card.Content class="grid grid-cols-2 gap-6">
        <div class="flex flex-col gap-2">
          <Label for="net-interface" class="text-xs">Interface</Label>
          <Input id="net-interface" bind:value={config.network.interface} class="text-sm" />
        </div>
        <div class="flex items-center gap-3 self-end">
          <Switch bind:checked={config.network.passive_mode} />
          <Label class="text-xs">Passive Mode</Label>
        </div>
      </Card.Content>
    </Card.Root>

    <!-- Web -->
    <Card.Root>
      <Card.Header>
        <Card.Title class="text-sm">
          Web
          <span class="text-xs text-destructive ml-2 font-normal">Requires restart</span>
        </Card.Title>
      </Card.Header>
      <Card.Content class="grid grid-cols-2 gap-6">
        <div class="flex flex-col gap-2">
          <Label for="web-host" class="text-xs">Host</Label>
          <Input id="web-host" bind:value={config.web.host} class="text-sm font-mono" />
        </div>
        <div class="flex flex-col gap-2">
          <Label for="web-port" class="text-xs">Port</Label>
          <Input id="web-port" type="number" bind:value={config.web.port} class="text-sm font-mono" />
        </div>
      </Card.Content>
    </Card.Root>

    <!-- Actions -->
    <div class="flex gap-3 items-center">
      <Button onclick={saveConfig} disabled={saving}>
        {saving ? 'Saving...' : 'Apply'}
      </Button>
      <Button variant="outline" onclick={handleExport}>Export TOML</Button>
      <Button variant="outline" onclick={() => fileInput.click()}>Import TOML</Button>
      <input bind:this={fileInput} type="file" accept=".toml" onchange={handleImport} class="hidden" />
      {#if message}
        <span class="text-xs text-muted-foreground">{message}</span>
      {/if}
    </div>
  {:else}
    <p class="text-muted-foreground text-sm">Loading configuration...</p>
  {/if}
</div>
```

Note: `fileInput` uses `$state` + `bind:this` for programmatic file picker trigger (Svelte 5 requires `$state` for `bind:this` variables). The `<label>` wrapper pattern is fragile with component libraries.

- [ ] **Step 2: Commit**

```bash
cd frontend && git add src/routes/config/ && git commit -m "feat: create Config view with shadcn Card, Input, Slider, Switch"
```

### Task 12: Create Scene placeholder page

**Files:**
- Create: `frontend/src/routes/scene/+page.svelte`

- [ ] **Step 1: Create scene directory and page**

```bash
mkdir -p frontend/src/routes/scene
```

```svelte
<div class="h-full flex items-center justify-center">
  <p class="text-muted-foreground text-sm">3D Scene Editor — Coming in Phase 2</p>
</div>
```

- [ ] **Step 2: Commit**

```bash
cd frontend && git add src/routes/scene/ && git commit -m "feat: create Scene placeholder"
```

---

## Chunk 4: Verify and Fix

### Task 13: Run type checking and fix errors

**Files:**
- Possibly modify any files with type errors

- [ ] **Step 1: Run svelte-check**

```bash
cd frontend && npx svelte-check --tsconfig ./tsconfig.json 2>&1
```

Fix any type errors. Common issues:
- shadcn-svelte Slider with `type="single"` uses `value: number` (plain number)
- Import paths for shadcn components use `/index.js` suffix
- Card.Content may need explicit padding class

- [ ] **Step 2: Verify pages load via dev server**

The backend should be running at localhost:8080. Start the frontend:

```bash
cd frontend && npm run dev -- --port 5173
```

Verify each page loads:
```bash
curl -s http://localhost:5173/ | head -5
curl -s http://localhost:5173/devices | head -5
curl -s http://localhost:5173/config | head -5
curl -s http://localhost:5173/scene | head -5
```

- [ ] **Step 3: Fix any issues found**

Address type errors, missing imports, or runtime errors.

- [ ] **Step 4: Commit**

```bash
cd frontend && git add -A && git commit -m "fix: resolve type errors and verify all views render"
```

### Task 14: Verify build and clean up

**Files:**
- Possibly modify: `frontend/package.json`

- [ ] **Step 1: Run production build**

```bash
cd frontend && npm run build
```

Fix any build errors.

- [ ] **Step 2: Commit if changes needed**

```bash
cd frontend && git add -A && git commit -m "fix: resolve build issues"
```
