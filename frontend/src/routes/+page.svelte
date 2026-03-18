<script lang="ts">
  import * as Card from '$lib/components/ui/card/index.js';
  import * as Resizable from '$lib/components/ui/resizable/index.js';
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
  <Resizable.PaneGroup direction="horizontal" class="flex-1 min-h-0">
    <Resizable.Pane defaultSize={70} minSize={40}>
      <!-- Left: Transport + Scene preview -->
      <div class="flex flex-col h-full p-4 gap-4">
        <!-- Transport -->
        <Card.Root>
          <Card.Content class="flex items-center gap-6 py-4">
            <BpmDisplay />
            <div class="flex flex-col gap-2 flex-1 max-w-sm">
              <BeatGrid />
              <PhaseMeter value={beatStore.beatPhase} label="BEAT" />
              <PhaseMeter value={beatStore.barPhase} label="BAR" />
            </div>
            <PlayState />
          </Card.Content>
        </Card.Root>

        <!-- Scene preview placeholder -->
        <Card.Root class="flex-1">
          <Card.Content class="flex items-center justify-center h-full">
            <p class="text-sm text-muted-foreground">Scene Preview — Phase 2</p>
          </Card.Content>
        </Card.Root>
      </div>
    </Resizable.Pane>

    <Resizable.Handle />

    <Resizable.Pane defaultSize={30} minSize={20} maxSize={45}>
      <!-- Right: Effect deck sidebar -->
      <EffectDeckPanel />
    </Resizable.Pane>
  </Resizable.PaneGroup>

  <!-- Device monitor strip -->
  {#if devicesStore.devices.length > 0}
    <div class="flex gap-2 px-4 py-2 border-t border-border overflow-x-auto shrink-0">
      {#each devicesStore.devices as device}
        <DeviceMonitor {device} />
      {/each}
    </div>
  {/if}
</div>
