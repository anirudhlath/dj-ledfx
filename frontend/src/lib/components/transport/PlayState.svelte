<script lang="ts">
  import { beatStore } from '$lib/stores/beat.svelte';
</script>

<div class="flex items-center justify-center w-10 h-10 rounded-md {beatStore.isPlaying ? 'bg-primary/10' : 'bg-muted'}">
  {#if beatStore.isPlaying}
    <svg viewBox="0 0 24 24" class="w-5 h-5 fill-primary">
      <path d="M8 5v14l11-7z"/>
    </svg>
  {:else}
    <svg viewBox="0 0 24 24" class="w-4 h-4 fill-muted-foreground">
      <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
    </svg>
  {/if}
</div>
