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
