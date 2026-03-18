<script lang="ts">
  import { beatStore } from '$lib/stores/beat.svelte';
</script>

<div class="flex items-center gap-2">
  <div class="w-6 h-6 flex items-center justify-center">
    {#if beatStore.isPlaying}
      <svg viewBox="0 0 24 24" class="w-5 h-5 fill-[--color-status-ok]">
        <path d="M8 5v14l11-7z"/>
      </svg>
    {:else}
      <svg viewBox="0 0 24 24" class="w-5 h-5 fill-[--color-text-muted]">
        <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
      </svg>
    {/if}
  </div>
</div>
