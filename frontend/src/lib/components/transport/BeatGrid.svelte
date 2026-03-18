<script lang="ts">
  import { beatStore } from '$lib/stores/beat.svelte';
</script>

<div class="flex gap-1.5 items-center">
  {#each [1, 2, 3, 4] as beat}
    {@const active = beatStore.beatPos === beat && beatStore.isPlaying}
    <div
      class="w-9 h-9 rounded-md flex items-center justify-center text-sm font-medium transition-colors
        {active ? 'bg-primary text-primary-foreground' : 'bg-muted text-muted-foreground'}"
      style={active ? 'animation: beat-hit 150ms ease-out;' : ''}
    >
      {beat}
    </div>
  {/each}
</div>
