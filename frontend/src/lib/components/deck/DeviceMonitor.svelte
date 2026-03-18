<script lang="ts">
  import type { Device } from '$lib/api/client';
  import LedIndicator from '$lib/components/common/LedIndicator.svelte';
  import { devicesStore } from '$lib/stores/devices.svelte';

  interface Props {
    device: Device;
  }
  let { device }: Props = $props();

  type DeviceVisual = 'point' | 'segment' | 'matrix';

  let visual = $derived.by((): DeviceVisual => {
    if (device.led_count <= 1) return 'point';
    if (device.device_type.includes('matrix')) return 'matrix';
    return 'segment';
  });

  let frameColors = $derived.by(() => {
    const frame = devicesStore.frameData.get(device.name);
    if (!frame || frame.rgb.length < 3) return [];
    const count = Math.min(device.led_count, Math.floor(frame.rgb.length / 3));
    const colors: string[] = [];
    for (let i = 0; i < count; i++) {
      colors.push(`rgb(${frame.rgb[i * 3]}, ${frame.rgb[i * 3 + 1]}, ${frame.rgb[i * 3 + 2]})`);
    }
    return colors;
  });

  let avgColor = $derived.by(() => {
    if (frameColors.length === 0) return null;
    return frameColors[0];
  });
</script>

<div class="flex items-center gap-2.5 px-3 py-2 rounded-md border border-border bg-card min-w-[160px]">
  <LedIndicator color={device.connected ? 'green' : 'red'} size="sm" />
  <div class="flex flex-col min-w-0 shrink-0">
    <span class="text-xs text-foreground truncate max-w-[120px]">
      {device.name}
    </span>
    <div class="flex items-center gap-2 text-[10px] text-muted-foreground tabular-nums">
      <span>{device.send_fps.toFixed(0)}fps</span>
      <span>{device.effective_latency_ms.toFixed(0)}ms</span>
    </div>
  </div>

  <!-- LED visualization -->
  <div class="ml-auto shrink-0">
    {#if visual === 'point'}
      <div
        class="w-4 h-4 rounded-full border border-border"
        style="background: {avgColor ?? 'hsl(var(--muted))'};"
      ></div>
    {:else if visual === 'matrix'}
      {@const size = Math.ceil(Math.sqrt(frameColors.length))}
      <div class="grid gap-px" style="grid-template-columns: repeat({size}, 1fr);">
        {#each frameColors as color}
          <div class="w-1 h-1 rounded-[1px]" style="background: {color};"></div>
        {/each}
      </div>
    {:else}
      <div class="flex gap-px">
        {#each frameColors as color}
          <div class="w-1 h-4 rounded-[1px]" style="background: {color};"></div>
        {/each}
      </div>
    {/if}
  </div>
</div>
