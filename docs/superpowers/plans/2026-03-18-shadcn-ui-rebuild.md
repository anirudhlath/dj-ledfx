# shadcn-svelte UI Rebuild Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the dj-ledfx web UI frontend using shadcn-svelte's default dark theme with cyan primary, replacing all custom-styled components while keeping the working data layer (stores, WS client, API client) untouched.

**Architecture:** Delete all custom UI components and CSS theme. Initialize shadcn-svelte with Tailwind v4, install needed components (Button, Card, Input, Label, Slider, Switch, Table, Badge, Separator, Select), then rebuild each view using shadcn components. Domain-specific components (BpmDisplay, BeatGrid, PhaseMeter, PlayState, DeviceMonitor, LedIndicator, PaletteEditor) are rebuilt to match shadcn's visual conventions using its CSS variables.

**Tech Stack:** SvelteKit 2, Svelte 5 (runes), shadcn-svelte, bits-ui, Tailwind CSS v4, TypeScript

**Spec:** `docs/superpowers/specs/2026-03-13-web-ui-design.md`

---

## Chunk 1: shadcn-svelte Foundation

Set up the shadcn-svelte tooling and theme. After this chunk, the app will have a broken UI (old components deleted, new ones not yet written) but the foundation is in place.

### Task 1: Install shadcn-svelte dependencies and initialize

**Files:**
- Create: `frontend/components.json`
- Modify: `frontend/package.json`

- [ ] **Step 1: Install tw-animate-css**

```bash
cd frontend && npm install tw-animate-css
```

- [ ] **Step 2: Create components.json**

Create `frontend/components.json`:

```json
{
  "$schema": "https://shadcn-svelte.com/schema.json",
  "style": "default",
  "tailwind": {
    "css": "src/app.css"
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

- [ ] **Step 3: Install all needed shadcn-svelte components**

```bash
cd frontend && npx shadcn-svelte@latest add button card input label slider switch table badge separator select scroll-area
```

This generates files into `src/lib/components/ui/`. Accept all prompts.

- [ ] **Step 4: Verify components installed**

```bash
ls frontend/src/lib/components/ui/
```

Expected: directories for each component (button, card, input, label, slider, switch, table, badge, separator, select, scroll-area).

- [ ] **Step 5: Commit**

```bash
cd frontend && git add -A && git commit -m "build: initialize shadcn-svelte and install UI components"
```

### Task 2: Replace app.css with shadcn dark theme

**Files:**
- Rewrite: `frontend/src/app.css`
- Modify: `frontend/src/app.html`

- [ ] **Step 1: Replace app.css**

Replace the entire contents of `frontend/src/app.css` with the shadcn-svelte Tailwind v4 theme. The only customization is `--primary` set to cyan (`187 100% 50%`) in the `.dark` block, and the `beat-hit` keyframe animation retained for functional beat indication:

```css
@import "tailwindcss";
@import "tw-animate-css";

@custom-variant dark (&:is(.dark *));

:root {
  --background: 0 0% 100%;
  --foreground: 240 10% 3.9%;
  --muted: 240 4.8% 95.9%;
  --muted-foreground: 240 3.8% 46.1%;
  --popover: 0 0% 100%;
  --popover-foreground: 240 10% 3.9%;
  --card: 0 0% 100%;
  --card-foreground: 240 10% 3.9%;
  --border: 240 5.9% 90%;
  --input: 240 5.9% 90%;
  --primary: 240 5.9% 10%;
  --primary-foreground: 0 0% 98%;
  --secondary: 240 4.8% 95.9%;
  --secondary-foreground: 240 5.9% 10%;
  --accent: 240 4.8% 95.9%;
  --accent-foreground: 240 5.9% 10%;
  --destructive: 0 72.2% 50.6%;
  --destructive-foreground: 0 0% 98%;
  --ring: 240 10% 3.9%;
  --radius: 0.5rem;
}

.dark {
  --background: 240 10% 3.9%;
  --foreground: 0 0% 98%;
  --muted: 240 3.7% 15.9%;
  --muted-foreground: 240 5% 64.9%;
  --popover: 240 10% 3.9%;
  --popover-foreground: 0 0% 98%;
  --card: 240 10% 3.9%;
  --card-foreground: 0 0% 98%;
  --border: 240 3.7% 15.9%;
  --input: 240 3.7% 15.9%;
  --primary: 187 100% 50%;
  --primary-foreground: 240 10% 3.9%;
  --secondary: 240 3.7% 15.9%;
  --secondary-foreground: 0 0% 98%;
  --accent: 240 3.7% 15.9%;
  --accent-foreground: 0 0% 98%;
  --destructive: 0 62.8% 30.6%;
  --destructive-foreground: 0 0% 98%;
  --ring: 187 100% 50%;
}

@theme inline {
  --radius-sm: calc(var(--radius) - 4px);
  --radius-md: calc(var(--radius) - 2px);
  --radius-lg: var(--radius);
  --radius-xl: calc(var(--radius) + 4px);

  --color-background: hsl(var(--background));
  --color-foreground: hsl(var(--foreground));
  --color-muted: hsl(var(--muted));
  --color-muted-foreground: hsl(var(--muted-foreground));
  --color-popover: hsl(var(--popover));
  --color-popover-foreground: hsl(var(--popover-foreground));
  --color-card: hsl(var(--card));
  --color-card-foreground: hsl(var(--card-foreground));
  --color-border: hsl(var(--border));
  --color-input: hsl(var(--input));
  --color-primary: hsl(var(--primary));
  --color-primary-foreground: hsl(var(--primary-foreground));
  --color-secondary: hsl(var(--secondary));
  --color-secondary-foreground: hsl(var(--secondary-foreground));
  --color-accent: hsl(var(--accent));
  --color-accent-foreground: hsl(var(--accent-foreground));
  --color-destructive: hsl(var(--destructive));
  --color-destructive-foreground: hsl(var(--destructive-foreground));
  --color-ring: hsl(var(--ring));

  --font-display: 'Orbitron', monospace;
}

@layer base {
  * {
    @apply border-border;
  }
  body {
    @apply bg-background text-foreground;
  }
}

/* Functional animation: mirrors LED beat timing */
@keyframes beat-hit {
  0% {
    transform: scale(1.08);
  }
  100% {
    transform: scale(1);
  }
}
```

- [ ] **Step 2: Update app.html fonts**

In `frontend/src/app.html`, remove the Google Fonts `<link>` tags for Exo 2 and JetBrains Mono. Keep only Orbitron. The shadcn-svelte components use the system font stack by default. Update to:

```html
<!doctype html>
<html lang="en" class="dark">
  <head>
    <meta charset="utf-8" />
    <link rel="icon" href="%sveltekit.assets%/favicon.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&display=swap" rel="stylesheet" />
    %sveltekit.head%
  </head>
  <body>
    <div style="display: contents">%sveltekit.body%</div>
  </body>
</html>
```

Note: `class="dark"` on `<html>` forces dark mode since this is a dark-only app.

- [ ] **Step 3: Verify the dev server starts**

```bash
cd frontend && npm run dev
```

Expected: Vite starts without CSS errors. The app will look broken (old components reference deleted CSS variables) — that's expected at this stage.

- [ ] **Step 4: Commit**

```bash
cd frontend && git add -A && git commit -m "feat: replace custom theme with shadcn-svelte dark theme (cyan primary)"
```

### Task 3: Delete old custom components and theme tokens

**Files:**
- Delete: `frontend/src/lib/components/common/HwButton.svelte`
- Delete: `frontend/src/lib/components/common/Fader.svelte`
- Delete: `frontend/src/lib/components/common/Field.svelte`
- Delete: `frontend/src/lib/components/deck/LedPreview.svelte`
- Delete: `frontend/src/lib/theme/tokens.ts`

- [ ] **Step 1: Delete files**

```bash
cd frontend
rm src/lib/components/common/HwButton.svelte
rm src/lib/components/common/Fader.svelte
rm src/lib/components/common/Field.svelte
rm src/lib/components/deck/LedPreview.svelte
rm -rf src/lib/theme/
```

Files kept (will be rebuilt in-place):
- `src/lib/components/common/LedIndicator.svelte`
- All transport components (`BpmDisplay`, `BeatGrid`, `PhaseMeter`, `PlayState`)
- All deck components (`EffectDeckPanel`, `ParamSlider`, `PaletteEditor`, `DeviceMonitor`)
- All route files

- [ ] **Step 2: Commit**

```bash
cd frontend && git add -A && git commit -m "chore: delete custom components replaced by shadcn-svelte"
```

---

## Chunk 2: Rebuild Custom Components

Rebuild the domain-specific components that have no shadcn equivalent. Each uses shadcn CSS variables and matches shadcn's visual conventions (no glow, no custom shadows, clean minimal styling).

### Task 4: Rebuild LedIndicator

**Files:**
- Rewrite: `frontend/src/lib/components/common/LedIndicator.svelte`

- [ ] **Step 1: Rewrite LedIndicator**

A small colored dot for device status. Uses standard CSS colors, no glow/pulse effects:

```svelte
<script lang="ts">
  interface Props {
    color: 'green' | 'red' | 'amber' | 'cyan' | 'off';
    size?: 'sm' | 'md';
  }
  let { color, size = 'md' }: Props = $props();

  const colorMap: Record<string, string> = {
    green: 'bg-green-500',
    red: 'bg-red-500',
    amber: 'bg-amber-500',
    cyan: 'bg-primary',
    off: 'bg-muted',
  };
</script>

<span
  class="inline-block rounded-full shrink-0
    {size === 'sm' ? 'h-2 w-2' : 'h-2.5 w-2.5'}
    {colorMap[color] ?? 'bg-muted'}"
></span>
```

- [ ] **Step 2: Verify no type errors**

```bash
cd frontend && npx svelte-check --tsconfig ./tsconfig.json 2>&1 | head -30
```

Look for errors in LedIndicator.svelte specifically. Other files will have errors (expected — they reference deleted components).

- [ ] **Step 3: Commit**

```bash
cd frontend && git add src/lib/components/common/LedIndicator.svelte && git commit -m "feat: rebuild LedIndicator with shadcn styling"
```

### Task 5: Rebuild transport components (BpmDisplay, BeatGrid, PhaseMeter, PlayState)

**Files:**
- Rewrite: `frontend/src/lib/components/transport/BpmDisplay.svelte`
- Rewrite: `frontend/src/lib/components/transport/BeatGrid.svelte`
- Rewrite: `frontend/src/lib/components/transport/PhaseMeter.svelte`
- Rewrite: `frontend/src/lib/components/transport/PlayState.svelte`

- [ ] **Step 1: Rewrite BpmDisplay**

Large Orbitron BPM number with muted metadata. No glow, no ghost segments:

```svelte
<script lang="ts">
  import { beatStore } from '$lib/stores/beat.svelte';
</script>

<div class="flex flex-col">
  <span class="text-5xl font-bold font-display tabular-nums tracking-tight text-foreground">
    {beatStore.bpm > 0 ? beatStore.bpm.toFixed(1) : '---.-'}
  </span>
  <span class="text-xs text-muted-foreground mt-1">
    BPM{#if beatStore.pitchPercent}&ensp;·&ensp;{beatStore.pitchPercent > 0 ? '+' : ''}{beatStore.pitchPercent.toFixed(1)}%{/if}{#if beatStore.deckName}&ensp;·&ensp;{beatStore.deckName}{/if}
  </span>
</div>
```

- [ ] **Step 2: Rewrite BeatGrid**

Four beat position boxes. Inactive: `bg-muted`. Active: `bg-primary text-primary-foreground` with `beat-hit` animation:

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
      style={active ? 'animation: beat-hit 150ms ease-out;' : ''}
    >
      {beat}
    </div>
  {/each}
</div>
```

- [ ] **Step 3: Rewrite PhaseMeter**

Thin progress bar using shadcn colors:

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

- [ ] **Step 4: Rewrite PlayState**

Simple play/pause icon:

```svelte
<script lang="ts">
  import { beatStore } from '$lib/stores/beat.svelte';
</script>

<div class="flex items-center justify-center w-10 h-10 rounded-md {beatStore.isPlaying ? 'bg-primary/10' : 'bg-muted'}">
  {#if beatStore.isPlaying}
    <svg viewBox="0 0 24 24" class="w-5 h-5 fill-primary">
      <path d="M8 5v14l11-7z"/>
    </svg>
  {:else}
    <svg viewBox="0 0 24 24" class="w-4 h-4 fill-muted-foreground">
      <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
    </svg>
  {/if}
</div>
```

- [ ] **Step 5: Commit**

```bash
cd frontend && git add src/lib/components/transport/ && git commit -m "feat: rebuild transport components with shadcn styling"
```

### Task 6: Rebuild deck helper components (PaletteEditor, ParamSlider)

**Files:**
- Rewrite: `frontend/src/lib/components/deck/PaletteEditor.svelte`
- Rewrite: `frontend/src/lib/components/deck/ParamSlider.svelte`

- [ ] **Step 1: Rewrite PaletteEditor**

Row of color inputs with shadcn-consistent borders:

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

- [ ] **Step 2: Rewrite ParamSlider**

Dispatches to shadcn Slider (float/int) or Switch (bool):

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

  // Local state for two-way binding with shadcn components
  let sliderValue = $state(value as number);
  let switchValue = $state(value as boolean);

  // Sync prop -> local when parent changes
  $effect(() => { sliderValue = value as number; });
  $effect(() => { switchValue = value as boolean; });

  function onSliderChange(v: number) {
    sliderValue = v;
    onchange(v);
  }

  function onSwitchChange(v: boolean) {
    switchValue = v;
    onchange(v);
  }
</script>

{#if schema.type === 'float' || schema.type === 'int'}
  <div class="flex flex-col gap-2">
    <div class="flex items-baseline justify-between">
      <Label class="text-xs">{schema.label || name}</Label>
      <span class="text-xs text-primary tabular-nums font-mono">
        {sliderValue.toFixed(schema.step && schema.step < 1 ? 1 : 0)}
      </span>
    </div>
    <Slider
      type="single"
      value={sliderValue}
      min={schema.min ?? 0}
      max={schema.max ?? 100}
      step={schema.step ?? (schema.type === 'int' ? 1 : 0.1)}
      onValueChange={onSliderChange}
    />
  </div>
{:else if schema.type === 'bool'}
  <div class="flex items-center gap-3">
    <Switch
      checked={switchValue}
      onCheckedChange={onSwitchChange}
    />
    <Label class="text-xs">{schema.label || name}</Label>
  </div>
{/if}
```

Note: shadcn-svelte wraps bits-ui which supports both `bind:value` and callback props (`onValueChange`, `onCheckedChange`). The callback pattern is used here because ParamSlider dispatches changes to the effects store API.

- [ ] **Step 3: Commit**

```bash
cd frontend && git add src/lib/components/deck/PaletteEditor.svelte src/lib/components/deck/ParamSlider.svelte && git commit -m "feat: rebuild ParamSlider and PaletteEditor with shadcn components"
```

### Task 7: Rebuild EffectDeckPanel and DeviceMonitor

**Files:**
- Rewrite: `frontend/src/lib/components/deck/EffectDeckPanel.svelte`
- Rewrite: `frontend/src/lib/components/deck/DeviceMonitor.svelte`

- [ ] **Step 1: Rewrite EffectDeckPanel**

Right sidebar using shadcn Card, Button, Separator, Input:

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

- [ ] **Step 2: Rewrite DeviceMonitor**

Compact device tile showing status, name, stats, and LED color data:

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
cd frontend && git add src/lib/components/deck/ && git commit -m "feat: rebuild EffectDeckPanel and DeviceMonitor with shadcn components"
```

---

## Chunk 3: Rebuild Route Views

Rebuild each page view using the new shadcn components and rebuilt custom components.

### Task 8: Rebuild layout (navigation)

**Files:**
- Rewrite: `frontend/src/routes/+layout.svelte`

- [ ] **Step 1: Rewrite +layout.svelte**

Navigation bar using shadcn conventions. No custom classes:

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
    <span class="font-display text-primary text-sm font-bold mr-6 tracking-widest select-none">
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
        <LedIndicator color={beatStore.isPlaying ? 'cyan' : 'off'} size="sm" />
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
cd frontend && git add src/routes/+layout.svelte && git commit -m "feat: rebuild layout with shadcn navigation"
```

### Task 9: Rebuild Live view (+page.svelte)

**Files:**
- Rewrite: `frontend/src/routes/+page.svelte`

- [ ] **Step 1: Rewrite +page.svelte**

Live performance view with transport Card, scene placeholder Card, effect deck sidebar, device monitor strip:

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
cd frontend && git add src/routes/+page.svelte && git commit -m "feat: rebuild Live view with shadcn Card layout"
```

### Task 10: Rebuild Devices view

**Files:**
- Rewrite: `frontend/src/routes/devices/+page.svelte`

- [ ] **Step 1: Rewrite devices/+page.svelte**

Device table using shadcn Table, Badge, Button, Input:

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
  let newGroupColor = $state('#00e5ff');
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
cd frontend && git add src/routes/devices/+page.svelte && git commit -m "feat: rebuild Devices view with shadcn Table and Card"
```

### Task 11: Rebuild Config view

**Files:**
- Rewrite: `frontend/src/routes/config/+page.svelte`

- [ ] **Step 1: Rewrite config/+page.svelte**

Config page using shadcn Card, Input, Label, Slider, Switch, Button:

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
            <span class="text-xs text-primary tabular-nums font-mono">{config.engine.fps}</span>
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
            <span class="text-xs text-primary tabular-nums font-mono">{config.engine.max_lookahead_ms}ms</span>
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
      <label class="cursor-pointer">
        <Button variant="outline" onclick={() => {}}>Import TOML</Button>
        <input type="file" accept=".toml" onchange={handleImport} class="hidden" />
      </label>
      {#if message}
        <span class="text-xs text-primary">{message}</span>
      {/if}
    </div>
  {:else}
    <p class="text-muted-foreground text-sm">Loading configuration...</p>
  {/if}
</div>
```

- [ ] **Step 2: Commit**

```bash
cd frontend && git add src/routes/config/+page.svelte && git commit -m "feat: rebuild Config view with shadcn Card, Input, Slider, Switch"
```

### Task 12: Rebuild Scene placeholder page

**Files:**
- Rewrite: `frontend/src/routes/scene/+page.svelte`

- [ ] **Step 1: Rewrite scene/+page.svelte**

Simple placeholder using shadcn CSS variables:

```svelte
<div class="h-full flex items-center justify-center">
  <p class="text-muted-foreground text-sm">3D Scene Editor — Coming in Phase 2</p>
</div>
```

- [ ] **Step 2: Commit**

```bash
cd frontend && git add src/routes/scene/+page.svelte && git commit -m "feat: rebuild Scene placeholder with shadcn styling"
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
- shadcn-svelte Slider with `type="single"` uses `value: number` (plain number), with `type="multiple"` uses `value: number[]`
- shadcn-svelte Switch supports both `bind:checked` and `checked` + `onCheckedChange` callback pattern
- Import paths for shadcn components use `/index.js` suffix (e.g., `$lib/components/ui/button/index.js`)
- Card.Content may need explicit padding class since shadcn Card.Content has default padding

- [ ] **Step 2: Run dev server and verify pages load**

```bash
cd frontend && npm run dev
```

Navigate to each page (/, /devices, /config, /scene) and verify they render without console errors.

- [ ] **Step 3: Fix any issues found**

Address type errors, missing imports, or layout issues discovered in steps 1-2.

- [ ] **Step 4: Final commit**

```bash
cd frontend && git add -A && git commit -m "fix: resolve type errors and verify all views render correctly"
```

### Task 14: Clean up unused dependencies

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Check for unused packages**

The following may no longer be needed now that shadcn-svelte is fully set up:
- `tailwind-variants` — check if any shadcn-svelte generated components use it; if not, remove
- `@types/three`, `@threlte/core`, `@threlte/extras`, `three` — these are for phase 2 scene editor; keep them

```bash
cd frontend && grep -r "tailwind-variants" src/lib/components/ui/ || echo "NOT USED"
```

- [ ] **Step 2: Remove unused deps if confirmed**

```bash
cd frontend && npm uninstall tailwind-variants  # only if confirmed unused
```

- [ ] **Step 3: Commit**

```bash
cd frontend && git add package.json package-lock.json && git commit -m "chore: remove unused dependencies"
```
