<script lang="ts">
  import { onMount } from 'svelte';
  import * as api from '$lib/api/client';
  import HwButton from '$lib/components/common/HwButton.svelte';
  import Fader from '$lib/components/common/Fader.svelte';
  import Field from '$lib/components/common/Field.svelte';

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

<div class="h-full overflow-y-auto p-4 max-w-3xl mx-auto flex flex-col gap-6">
  <h2 class="text-base font-[--font-mono] text-[--color-text-primary] uppercase tracking-wider">Configuration</h2>

  {#if config}
    <!-- Engine -->
    <section class="bg-[--color-bg-surface] rounded border border-[--color-border-subtle] p-4">
      <h3 class="text-[11px] font-[--font-mono] uppercase tracking-wider text-[--color-text-secondary] mb-3">Engine</h3>
      <div class="grid grid-cols-2 gap-4">
        <Fader bind:value={config.engine.fps} min={30} max={120} step={1} label="FPS" />
        <Fader bind:value={config.engine.max_lookahead_ms} min={500} max={2000} step={50} label="Max Lookahead" unit="ms" />
      </div>
    </section>

    <!-- Network -->
    <section class="bg-[--color-bg-surface] rounded border border-[--color-border-subtle] p-4">
      <h3 class="text-[11px] font-[--font-mono] uppercase tracking-wider text-[--color-text-secondary] mb-3">Network</h3>
      <div class="grid grid-cols-2 gap-4">
        <Field label="Interface">
          <input
            type="text"
            bind:value={config.network.interface}
            class="w-full px-2 py-1 text-xs bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded
              text-[--color-text-primary] font-[--font-mono] focus:outline-none focus:border-[--color-accent-cyan]"
          />
        </Field>
        <label class="flex items-center gap-2 cursor-pointer self-end">
          <input type="checkbox" bind:checked={config.network.passive_mode} class="accent-[--color-accent-cyan]" />
          <span class="text-[10px] uppercase tracking-wider text-[--color-text-secondary] font-[--font-sans]">Passive Mode</span>
        </label>
      </div>
    </section>

    <!-- Web -->
    <section class="bg-[--color-bg-surface] rounded border border-[--color-border-subtle] p-4">
      <h3 class="text-[11px] font-[--font-mono] uppercase tracking-wider text-[--color-text-secondary] mb-3">
        Web
        <span class="text-[9px] text-[--color-status-warning] ml-2 normal-case">Requires restart</span>
      </h3>
      <div class="grid grid-cols-2 gap-4">
        <Field label="Host">
          <input
            type="text"
            bind:value={config.web.host}
            class="w-full px-2 py-1 text-xs bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded
              text-[--color-text-primary] font-[--font-mono] focus:outline-none focus:border-[--color-accent-cyan]"
          />
        </Field>
        <Field label="Port">
          <input
            type="number"
            bind:value={config.web.port}
            class="w-full px-2 py-1 text-xs bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded
              text-[--color-text-primary] font-[--font-mono] focus:outline-none focus:border-[--color-accent-cyan]"
          />
        </Field>
      </div>
    </section>

    <!-- Actions -->
    <div class="flex gap-3 items-center">
      <HwButton variant="accent" onclick={saveConfig} disabled={saving}>
        {saving ? 'Saving...' : 'Apply'}
      </HwButton>
      <HwButton onclick={handleExport}>Export TOML</HwButton>
      <label class="cursor-pointer">
        <HwButton onclick={() => {}}>Import TOML</HwButton>
        <input type="file" accept=".toml" onchange={handleImport} class="hidden" />
      </label>
      {#if message}
        <span class="text-[11px] font-[--font-mono] text-[--color-accent-cyan]">{message}</span>
      {/if}
    </div>
  {:else}
    <div class="text-[--color-text-muted] text-sm font-[--font-mono]">Loading configuration...</div>
  {/if}
</div>
