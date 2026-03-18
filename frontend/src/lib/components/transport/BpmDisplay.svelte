<script lang="ts">
  import { beatStore } from '$lib/stores/beat.svelte';
</script>

<div class="flex flex-col">
  <span class="text-5xl font-bold font-display tabular-nums tracking-tight text-foreground">
    {beatStore.bpm > 0 ? beatStore.bpm.toFixed(1) : '---.-'}
  </span>
  <span class="text-xs text-muted-foreground mt-1">
    BPM{#if beatStore.pitchPercent}&ensp;·&ensp;{beatStore.pitchPercent > 0 ? '+' : ''}{beatStore.pitchPercent.toFixed(1)}%{/if}{#if beatStore.deckName}&ensp;·&ensp;{beatStore.deckName}{/if}
  </span>
</div>
