<script lang="ts">
  import { onMount } from 'svelte';
  import * as api from '$lib/api/client';
  import { toast } from 'svelte-sonner';
  import { Button } from '$lib/components/ui/button/index.js';
  import { Input } from '$lib/components/ui/input/index.js';
  import { Label } from '$lib/components/ui/label/index.js';
  import { Slider } from '$lib/components/ui/slider/index.js';
  import { Switch } from '$lib/components/ui/switch/index.js';
  import { Skeleton } from '$lib/components/ui/skeleton/index.js';
  import * as Card from '$lib/components/ui/card/index.js';
  import * as Tabs from '$lib/components/ui/tabs/index.js';

  let config = $state<api.AppConfig | null>(null);
  let saving = $state(false);
  let fileInput = $state<HTMLInputElement>(undefined!);

  onMount(async () => {
    config = await api.getConfig();
  });

  async function saveConfig() {
    if (!config) return;
    saving = true;
    try {
      config = await api.updateConfig(config);
      toast.success('Configuration saved');
    } catch (e) {
      toast.error(`Failed to save: ${e}`);
    } finally {
      saving = false;
    }
  }

  async function handleExport() {
    try {
      const toml = await api.exportConfig();
      const blob = new Blob([toml], { type: 'text/plain' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'dj-ledfx-config.toml';
      a.click();
      URL.revokeObjectURL(url);
      toast.success('Config exported');
    } catch (e) {
      toast.error(`Export failed: ${e}`);
    }
  }

  async function handleImport(e: Event) {
    const input = e.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    const text = await file.text();
    try {
      config = await api.importConfig(text);
      toast.success('Config imported');
    } catch (err) {
      toast.error(`Import failed: ${err}`);
    }
  }
</script>

<div class="h-full overflow-y-auto p-6 max-w-3xl mx-auto flex flex-col gap-6">
  <div class="flex items-center justify-between">
    <h2 class="text-lg font-semibold">Configuration</h2>
    <div class="flex gap-2">
      <Button variant="outline" size="sm" onclick={handleExport}>Export TOML</Button>
      <Button variant="outline" size="sm" onclick={() => fileInput.click()}>Import TOML</Button>
      <input bind:this={fileInput} type="file" accept=".toml" onchange={handleImport} class="hidden" />
    </div>
  </div>

  {#if config}
    <Tabs.Root value="engine">
      <Tabs.List>
        <Tabs.Trigger value="engine">Engine</Tabs.Trigger>
        <Tabs.Trigger value="network">Network</Tabs.Trigger>
        <Tabs.Trigger value="web">Web</Tabs.Trigger>
      </Tabs.List>

      <Tabs.Content value="engine">
        <Card.Root>
          <Card.Content class="grid grid-cols-2 gap-6 pt-6">
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
      </Tabs.Content>

      <Tabs.Content value="network">
        <Card.Root>
          <Card.Content class="grid grid-cols-2 gap-6 pt-6">
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
      </Tabs.Content>

      <Tabs.Content value="web">
        <Card.Root>
          <Card.Header>
            <Card.Title class="text-xs text-destructive font-normal">Changes require app restart</Card.Title>
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
      </Tabs.Content>
    </Tabs.Root>

    <!-- Apply button -->
    <Button onclick={saveConfig} disabled={saving}>
      {saving ? 'Saving...' : 'Apply Changes'}
    </Button>
  {:else}
    <!-- Loading skeleton -->
    <div class="flex flex-col gap-4">
      <Skeleton class="h-10 w-full" />
      <Skeleton class="h-48 w-full" />
      <Skeleton class="h-10 w-24" />
    </div>
  {/if}
</div>
