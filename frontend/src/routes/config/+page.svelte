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
      <Button variant="outline" onclick={() => fileInput.click()}>Import TOML</Button>
      <input bind:this={fileInput} type="file" accept=".toml" onchange={handleImport} class="hidden" />
      {#if message}
        <span class="text-xs text-primary">{message}</span>
      {/if}
    </div>
  {:else}
    <p class="text-muted-foreground text-sm">Loading configuration...</p>
  {/if}
</div>
