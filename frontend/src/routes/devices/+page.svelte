<script lang="ts">
  import { devicesStore } from '$lib/stores/devices.svelte';
  import { toast } from 'svelte-sonner';
  import { Button } from '$lib/components/ui/button/index.js';
  import { Input } from '$lib/components/ui/input/index.js';
  import { Badge } from '$lib/components/ui/badge/index.js';
  import { Label } from '$lib/components/ui/label/index.js';
  import * as Table from '$lib/components/ui/table/index.js';
  import * as Card from '$lib/components/ui/card/index.js';
  import * as Tooltip from '$lib/components/ui/tooltip/index.js';
  import * as Dialog from '$lib/components/ui/dialog/index.js';
  import LedIndicator from '$lib/components/common/LedIndicator.svelte';

  let expandedDevice = $state<string | null>(null);
  let newGroupName = $state('');
  let newGroupColor = $state('#00e5ff');
  let discovering = $state(false);
  let groupDialogOpen = $state(false);

  async function handleDiscover() {
    discovering = true;
    try {
      await devicesStore.discover();
      toast.success('Device scan complete');
    } catch {
      toast.error('Device scan failed');
    } finally {
      discovering = false;
    }
  }
</script>

<div class="h-full overflow-y-auto p-6 flex flex-col gap-6 max-w-5xl mx-auto">
  <!-- Header -->
  <div class="flex items-center justify-between">
    <h2 class="text-lg font-semibold">Devices</h2>
    <Button onclick={handleDiscover} disabled={discovering}>
      {#if discovering}
        <svg class="animate-spin -ml-1 mr-2 h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
        </svg>
        Scanning...
      {:else}
        Scan for Devices
      {/if}
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
            <Table.Cell class="text-right tabular-nums">
              <Tooltip.Provider>
                <Tooltip.Root>
                  <Tooltip.Trigger>
                    {device.send_fps.toFixed(0)}
                  </Tooltip.Trigger>
                  <Tooltip.Content>
                    <p>Send FPS (target: device cap)</p>
                  </Tooltip.Content>
                </Tooltip.Root>
              </Tooltip.Provider>
            </Table.Cell>
            <Table.Cell class="text-right tabular-nums">
              <Tooltip.Provider>
                <Tooltip.Root>
                  <Tooltip.Trigger>
                    {device.effective_latency_ms.toFixed(0)}ms
                  </Tooltip.Trigger>
                  <Tooltip.Content>
                    <p>Effective latency (heuristic + measured)</p>
                  </Tooltip.Content>
                </Tooltip.Root>
              </Tooltip.Provider>
            </Table.Cell>
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
    <Card.Header class="flex flex-row items-center justify-between">
      <Card.Title class="text-sm">Groups</Card.Title>
      <Dialog.Root bind:open={groupDialogOpen}>
        <Dialog.Trigger>
          {#snippet child({ props })}
            <Button {...props} size="sm" variant="outline">New Group</Button>
          {/snippet}
        </Dialog.Trigger>
        <Dialog.Content class="sm:max-w-sm">
          <Dialog.Header>
            <Dialog.Title>Create Group</Dialog.Title>
            <Dialog.Description>Create a new device group with a name and color.</Dialog.Description>
          </Dialog.Header>
          <div class="flex flex-col gap-4">
            <div class="flex flex-col gap-2">
              <Label class="text-xs">Name</Label>
              <Input
                bind:value={newGroupName}
                placeholder="Group name"
                class="text-sm"
              />
            </div>
            <div class="flex items-center gap-3">
              <Label class="text-xs">Color</Label>
              <input type="color" bind:value={newGroupColor}
                class="w-8 h-8 rounded-md border border-input bg-transparent cursor-pointer" />
            </div>
          </div>
          <Dialog.Footer>
            <Button
              disabled={!newGroupName}
              onclick={() => {
                devicesStore.createGroup(newGroupName, newGroupColor);
                toast.success(`Group "${newGroupName}" created`);
                newGroupName = '';
                groupDialogOpen = false;
              }}
            >
              Create
            </Button>
          </Dialog.Footer>
        </Dialog.Content>
      </Dialog.Root>
    </Card.Header>
    <Card.Content>
      {#if Object.keys(devicesStore.groups).length > 0}
        <div class="flex gap-2 flex-wrap">
          {#each Object.entries(devicesStore.groups) as [name, group]}
            <Badge variant="outline" class="gap-2">
              <span class="w-2 h-2 rounded-full inline-block" style="background: {group.color};"></span>
              {name}
              <button
                class="text-muted-foreground hover:text-destructive text-xs cursor-pointer"
                onclick={() => { devicesStore.deleteGroup(name); toast(`Group "${name}" deleted`); }}
              >✕</button>
            </Badge>
          {/each}
        </div>
      {:else}
        <p class="text-sm text-muted-foreground">No groups created yet.</p>
      {/if}
    </Card.Content>
  </Card.Root>
</div>
