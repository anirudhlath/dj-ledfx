<script lang="ts">
  interface Props {
    color?: 'green' | 'red' | 'amber' | 'cyan' | 'off';
    size?: 'sm' | 'md';
  }
  let { color = 'off', size = 'md' }: Props = $props();

  const colorMap: Record<string, string> = {
    green: 'bg-green-500',
    red: 'bg-red-500',
    amber: 'bg-amber-500',
    cyan: 'bg-primary',
    off: 'bg-muted',
  };
</script>

<span
  class="inline-block rounded-full shrink-0
    {size === 'sm' ? 'h-2 w-2' : 'h-2.5 w-2.5'}
    {colorMap[color] ?? 'bg-muted'}"
></span>
