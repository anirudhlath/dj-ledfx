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
