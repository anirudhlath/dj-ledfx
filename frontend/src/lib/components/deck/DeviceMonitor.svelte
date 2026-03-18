<script lang="ts">
  import type { Device } from '$lib/api/client';
  import LedIndicator from '$lib/components/common/LedIndicator.svelte';
  import { devicesStore } from '$lib/stores/devices.svelte';

  interface Props {
    device: Device;
  }
  let { device }: Props = $props();

  let frameColors = $derived(() => {
    const frame = devicesStore.frameData.get(device.name);
    if (!frame) return [];
    const colors: string[] = [];
    for (let i = 0; i < frame.rgb.length; i += 3) {
      colors.push(`rgb(${frame.rgb[i]}, ${frame.rgb[i + 1]}, ${frame.rgb[i + 2]})`);
    }
    return colors.slice(0, 20); // Show first 20 LEDs
  });
</script>

<div class="flex items-center gap-2 px-3 py-1.5 bg-[--color-bg-elevated] rounded border border-[--color-border-subtle]">
  <LedIndicator color={device.connected ? 'green' : 'red'} />
  <span class="text-[11px] font-[--font-mono] text-[--color-text-primary] min-w-[80px]">{device.name}</span>
  <span class="text-[10px] font-[--font-mono] text-[--color-text-muted] tabular-nums">{device.send_fps.toFixed(0)}fps</span>
  <span class="text-[10px] font-[--font-mono] text-[--color-text-muted] tabular-nums">{device.effective_latency_ms.toFixed(0)}ms</span>
  <div class="flex gap-px ml-2">
    {#each frameColors() as color}
      <div class="w-1.5 h-4 rounded-sm" style="background: {color};"></div>
    {/each}
  </div>
</div>
