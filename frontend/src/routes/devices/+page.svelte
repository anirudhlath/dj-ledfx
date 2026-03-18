<script lang="ts">
  import { devicesStore } from '$lib/stores/devices.svelte';
  import LedIndicator from '$lib/components/common/LedIndicator.svelte';
  import HwButton from '$lib/components/common/HwButton.svelte';

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

<div class="h-full overflow-y-auto p-4 flex flex-col gap-4">
  <!-- Header -->
  <div class="flex items-center justify-between">
    <h2 class="text-base font-[--font-mono] text-[--color-text-primary] uppercase tracking-wider">Devices</h2>
    <HwButton variant="accent" onclick={handleDiscover} disabled={discovering}>
      {discovering ? 'Scanning...' : 'Scan for Devices'}
    </HwButton>
  </div>

  <!-- Device table -->
  <div class="bg-[--color-bg-surface] rounded border border-[--color-border-subtle] overflow-hidden">
    <table class="w-full text-[12px] font-[--font-mono]">
      <thead>
        <tr class="bg-[--color-bg-elevated] text-[--color-text-secondary] uppercase text-[10px] tracking-wider">
          <th class="px-3 py-2 text-left w-6"></th>
          <th class="px-3 py-2 text-left">Name</th>
          <th class="px-3 py-2 text-left">Type</th>
          <th class="px-3 py-2 text-right">LEDs</th>
          <th class="px-3 py-2 text-left">Address</th>
          <th class="px-3 py-2 text-left">Group</th>
          <th class="px-3 py-2 text-right">FPS</th>
          <th class="px-3 py-2 text-right">Latency</th>
        </tr>
      </thead>
      <tbody>
        {#each devicesStore.devices as device}
          <tr
            class="border-t border-[--color-border-subtle] hover:bg-[--color-bg-elevated] cursor-pointer transition-colors"
            onclick={() => expandedDevice = expandedDevice === device.name ? null : device.name}
          >
            <td class="px-3 py-2"><LedIndicator color={device.connected ? 'green' : 'red'} /></td>
            <td class="px-3 py-2 text-[--color-text-primary]">{device.name}</td>
            <td class="px-3 py-2 text-[--color-text-secondary]">{device.device_type}</td>
            <td class="px-3 py-2 text-right text-[--color-text-secondary] tabular-nums">{device.led_count}</td>
            <td class="px-3 py-2 text-[--color-text-muted]">{device.address}</td>
            <td class="px-3 py-2">
              {#if device.group}
                <span class="px-1.5 py-0.5 rounded bg-[--color-bg-overlay] text-[--color-text-accent] text-[10px]">
                  {device.group}
                </span>
              {:else}
                <span class="text-[--color-text-muted]">—</span>
              {/if}
            </td>
            <td class="px-3 py-2 text-right tabular-nums text-[--color-text-secondary]">{device.send_fps.toFixed(0)}</td>
            <td class="px-3 py-2 text-right tabular-nums text-[--color-text-secondary]">{device.effective_latency_ms.toFixed(0)}ms</td>
          </tr>
          {#if expandedDevice === device.name}
            <tr class="bg-[--color-bg-elevated]">
              <td colspan="8" class="px-6 py-3">
                <div class="flex gap-4 items-center">
                  <HwButton onclick={() => devicesStore.identify(device.name)}>
                    Identify
                  </HwButton>
                  <span class="text-[10px] text-[--color-text-muted]">
                    Frames dropped: {device.frames_dropped}
                  </span>
                </div>
              </td>
            </tr>
          {/if}
        {/each}
        {#if devicesStore.devices.length === 0}
          <tr>
            <td colspan="8" class="px-3 py-8 text-center text-[--color-text-muted] text-sm">
              No devices found. Click "Scan for Devices" to discover.
            </td>
          </tr>
        {/if}
      </tbody>
    </table>
  </div>

  <!-- Groups -->
  <div class="bg-[--color-bg-surface] rounded border border-[--color-border-subtle] p-4">
    <h3 class="text-[11px] font-[--font-mono] uppercase tracking-wider text-[--color-text-secondary] mb-3">Groups</h3>
    <div class="flex gap-2 flex-wrap mb-3">
      {#each Object.entries(devicesStore.groups) as [name, group]}
        <div class="flex items-center gap-2 px-2 py-1 bg-[--color-bg-elevated] rounded border border-[--color-border-subtle]">
          <div class="w-3 h-3 rounded-full" style="background: {group.color};"></div>
          <span class="text-[11px] font-[--font-mono] text-[--color-text-primary]">{name}</span>
          <button
            class="text-[--color-text-muted] hover:text-[--color-status-error] text-[10px]"
            onclick={() => devicesStore.deleteGroup(name)}
          >✕</button>
        </div>
      {/each}
    </div>
    <div class="flex gap-2 items-center">
      <input
        type="text"
        bind:value={newGroupName}
        placeholder="Group name"
        class="px-2 py-1 text-xs bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded
          text-[--color-text-primary] font-[--font-mono] placeholder:text-[--color-text-muted]
          focus:outline-none focus:border-[--color-accent-cyan]"
      />
      <input type="color" bind:value={newGroupColor} class="w-7 h-7 rounded border border-[--color-border-subtle] bg-transparent cursor-pointer" />
      <HwButton
        variant="accent"
        disabled={!newGroupName}
        onclick={() => { devicesStore.createGroup(newGroupName, newGroupColor); newGroupName = ''; }}
      >
        Create
      </HwButton>
    </div>
  </div>
</div>
