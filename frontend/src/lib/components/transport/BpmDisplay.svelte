<script lang="ts">
  import { beatStore } from '$lib/stores/beat.svelte';
</script>

<div class="flex flex-col">
  <span class="text-[48px] font-[--font-mono] font-bold leading-none tabular-nums text-[--color-text-primary]">
    {beatStore.bpm > 0 ? beatStore.bpm.toFixed(1) : '---.-'}
  </span>
  <span class="text-[10px] font-[--font-mono] uppercase text-[--color-text-secondary] tracking-wider mt-1">BPM</span>
  {#if beatStore.pitchPercent !== null}
    <span class="text-[11px] font-[--font-mono] tabular-nums text-[--color-text-muted]">
      {beatStore.pitchPercent > 0 ? '+' : ''}{beatStore.pitchPercent.toFixed(1)}%
    </span>
  {/if}
  {#if beatStore.deckName}
    <span class="text-[10px] font-[--font-mono] text-[--color-text-muted]">{beatStore.deckName}</span>
  {/if}
</div>
