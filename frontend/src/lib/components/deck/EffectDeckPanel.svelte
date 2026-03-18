<script lang="ts">
  import { effectsStore } from '$lib/stores/effects.svelte';
  import { toast } from 'svelte-sonner';
  import { Button } from '$lib/components/ui/button/index.js';
  import { Input } from '$lib/components/ui/input/index.js';
  import { Label } from '$lib/components/ui/label/index.js';
  import { Separator } from '$lib/components/ui/separator/index.js';
  import * as ToggleGroup from '$lib/components/ui/toggle-group/index.js';
  import * as Select from '$lib/components/ui/select/index.js';
  import * as Dialog from '$lib/components/ui/dialog/index.js';
  import * as ScrollArea from '$lib/components/ui/scroll-area/index.js';
  import ParamSlider from './ParamSlider.svelte';
  import PaletteEditor from './PaletteEditor.svelte';

  let presetName = $state('');
  let saveDialogOpen = $state(false);
</script>

<div class="flex flex-col h-full bg-card border-l border-border">
  <!-- Effect selector -->
  <div class="p-4">
    <Label class="text-xs text-muted-foreground mb-2 block">Effect</Label>
    <ToggleGroup.Root
      type="single"
      value={effectsStore.activeEffect}
      onValueChange={(v) => { if (v) effectsStore.switchEffect(v); }}
      class="flex-wrap justify-start"
    >
      {#each Object.keys(effectsStore.effectSchemas) as name}
        <ToggleGroup.Item value={name} size="sm">
          {name.replace(/_/g, ' ')}
        </ToggleGroup.Item>
      {/each}
    </ToggleGroup.Root>
  </div>

  <Separator />

  <!-- Parameters -->
  {#if effectsStore.effectSchemas[effectsStore.activeEffect]}
    <ScrollArea.Root class="flex-1">
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
    </ScrollArea.Root>
  {/if}

  <Separator />

  <!-- Presets -->
  <div class="p-4">
    <Label class="text-xs text-muted-foreground mb-2 block">Presets</Label>
    <div class="flex gap-1.5 items-center">
      {#if effectsStore.presets.length > 0}
        <Select.Root
          type="single"
          onValueChange={(v) => { if (v) effectsStore.loadPreset(v); }}
        >
          <Select.Trigger class="flex-1 text-xs">
            Load preset...
          </Select.Trigger>
          <Select.Content>
            {#each effectsStore.presets as preset}
              <Select.Item value={preset.name}>{preset.name}</Select.Item>
            {/each}
          </Select.Content>
        </Select.Root>
      {/if}

      <Dialog.Root bind:open={saveDialogOpen}>
        <Dialog.Trigger>
          {#snippet child({ props })}
            <Button {...props} size="sm" variant="outline">Save</Button>
          {/snippet}
        </Dialog.Trigger>
        <Dialog.Content class="sm:max-w-sm">
          <Dialog.Header>
            <Dialog.Title>Save Preset</Dialog.Title>
            <Dialog.Description>Save current effect parameters as a preset.</Dialog.Description>
          </Dialog.Header>
          <div class="flex gap-2">
            <Input
              bind:value={presetName}
              placeholder="Preset name"
              class="text-sm"
            />
            <Button
              disabled={!presetName}
              onclick={() => {
                effectsStore.savePreset(presetName);
                toast.success(`Preset "${presetName}" saved`);
                presetName = '';
                saveDialogOpen = false;
              }}
            >
              Save
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Root>
    </div>
  </div>
</div>
