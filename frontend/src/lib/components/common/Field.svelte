<script lang="ts">
  import type { Snippet } from 'svelte';
  interface Props {
    label: string;
    unit?: string;
    children: Snippet;
  }
  let { label, unit, children }: Props = $props();
</script>

<div class="flex flex-col gap-1">
  <label class="text-[10px] uppercase tracking-wider text-[--color-text-secondary] font-[--font-sans]">
    {label}
    {#if unit}<span class="text-[--color-text-muted]">({unit})</span>{/if}
  </label>
  {@render children()}
</div>
