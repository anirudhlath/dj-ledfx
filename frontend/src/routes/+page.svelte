<script lang="ts">
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
  <!-- Transport bar -->
  <div class="flex items-center gap-6 px-4 py-3 bg-[--color-bg-surface] border-b border-[--color-border-subtle] shrink-0">
    <!-- Left: BPM -->
    <BpmDisplay />

    <!-- Center: Beat grid + phase meters -->
    <div class="flex-1 flex flex-col items-center gap-2">
      <BeatGrid />
      <div class="w-64 flex flex-col gap-1">
        <PhaseMeter value={beatStore.beatPhase} label="Beat" />
        <PhaseMeter value={beatStore.barPhase} label="Bar" />
      </div>
    </div>

    <!-- Right: Play state -->
    <PlayState />
  </div>

  <!-- Main area -->
  <div class="flex-1 flex min-h-0">
    <!-- Left: LED visualization placeholder -->
    <div class="flex-1 flex items-center justify-center bg-[--color-bg-base]">
      <div class="text-center">
        <div class="text-[--color-text-muted] text-sm font-[--font-mono]">LED Preview</div>
        <div class="text-[--color-text-muted] text-[10px] font-[--font-mono] mt-1">3D Scene — Phase 2</div>
      </div>
    </div>

    <!-- Right: Effect deck panel -->
    <div class="w-80 shrink-0 border-l border-[--color-border-subtle]">
      <EffectDeckPanel />
    </div>
  </div>

  <!-- Device monitors strip -->
  {#if devicesStore.devices.length > 0}
    <div class="flex gap-2 px-4 py-2 bg-[--color-bg-surface] border-t border-[--color-border-subtle] overflow-x-auto shrink-0">
      {#each devicesStore.devices as device}
        <DeviceMonitor {device} />
      {/each}
    </div>
  {/if}
</div>
