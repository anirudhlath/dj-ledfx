<script lang="ts">
  import type { Snippet } from 'svelte';
  interface Props {
    variant?: 'default' | 'accent' | 'danger';
    active?: boolean;
    disabled?: boolean;
    onclick?: () => void;
    children: Snippet;
  }
  let { variant = 'default', active = false, disabled = false, onclick, children }: Props = $props();
</script>

<button
  class="px-3 py-1.5 rounded text-xs font-medium font-[--font-mono] uppercase tracking-wider
    transition-all duration-150 border
    {variant === 'accent' ? 'border-[--color-accent-cyan] text-[--color-accent-cyan]' :
     variant === 'danger' ? 'border-[--color-status-error] text-[--color-status-error]' :
     'border-[--color-border-medium] text-[--color-text-primary]'}
    {active ? 'bg-[--color-accent-cyan]/20 shadow-[0_0_8px_rgba(0,229,255,0.3)]' : 'bg-[--color-bg-elevated]'}
    hover:bg-[--color-bg-overlay] active:scale-95
    disabled:opacity-40 disabled:cursor-not-allowed"
  {disabled}
  {onclick}
>
  {@render children()}
</button>
