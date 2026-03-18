<script lang="ts">
  import { effectsStore } from '$lib/stores/effects.svelte';
  import ParamSlider from './ParamSlider.svelte';
  import PaletteEditor from './PaletteEditor.svelte';
  import HwButton from '$lib/components/common/HwButton.svelte';

  let presetName = $state('');
</script>

<div class="flex flex-col gap-4 p-4 bg-[--color-bg-surface] rounded border border-[--color-border-subtle] h-full overflow-y-auto">
  <!-- Effect selector -->
  <div class="flex flex-col gap-2">
    <span class="text-[10px] uppercase tracking-wider text-[--color-text-secondary]">Effect</span>
    <div class="flex gap-1 flex-wrap">
      {#each Object.keys(effectsStore.effectSchemas) as name}
        <HwButton
          variant={effectsStore.activeEffect === name ? 'accent' : 'default'}
          active={effectsStore.activeEffect === name}
          onclick={() => effectsStore.switchEffect(name)}
        >
          {name.replace(/_/g, ' ')}
        </HwButton>
      {/each}
    </div>
  </div>

  <!-- Presets -->
  <div class="flex flex-col gap-2">
    <span class="text-[10px] uppercase tracking-wider text-[--color-text-secondary]">Presets</span>
    <div class="flex gap-1 flex-wrap">
      {#each effectsStore.presets as preset}
        <HwButton
          onclick={() => effectsStore.loadPreset(preset.name)}
        >
          {preset.name}
        </HwButton>
      {/each}
    </div>
    <div class="flex gap-1">
      <input
        type="text"
        bind:value={presetName}
        placeholder="Preset name"
        class="flex-1 px-2 py-1 text-xs bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded
          text-[--color-text-primary] font-[--font-mono] placeholder:text-[--color-text-muted]
          focus:outline-none focus:border-[--color-accent-cyan]"
      />
      <HwButton
        variant="accent"
        disabled={!presetName}
        onclick={() => { effectsStore.savePreset(presetName); presetName = ''; }}
      >
        Save
      </HwButton>
    </div>
  </div>

  <!-- Parameters -->
  {#if effectsStore.effectSchemas[effectsStore.activeEffect]}
    <div class="flex flex-col gap-3">
      <span class="text-[10px] uppercase tracking-wider text-[--color-text-secondary]">Parameters</span>
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
</div>
