<script lang="ts">
  import { beatStore } from '$lib/stores/beat.svelte';
</script>

<div class="flex gap-2 items-center">
  {#each [1, 2, 3, 4] as beat}
    <div
      class="w-8 h-8 rounded flex items-center justify-center font-[--font-mono] text-sm font-bold transition-all duration-100
        {beatStore.beatPos === beat && beatStore.isPlaying
          ? 'bg-[--color-accent-cyan]/20 text-[--color-accent-cyan] shadow-[0_0_12px_rgba(0,229,255,0.3)] border border-[--color-accent-cyan]/50'
          : 'bg-[--color-bg-elevated] text-[--color-text-muted] border border-[--color-border-subtle]'}"
    >
      {beat}
    </div>
  {/each}
</div>
