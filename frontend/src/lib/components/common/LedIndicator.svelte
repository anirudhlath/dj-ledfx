<script lang="ts">
  interface Props {
    color?: 'green' | 'red' | 'amber' | 'cyan' | 'off';
    size?: 'sm' | 'md';
    pulse?: boolean;
  }
  let { color = 'off', size = 'sm', pulse = false }: Props = $props();

  const colorMap = {
    green: { bg: '#00e676', glow: 'rgba(0, 230, 118, 0.4)' },
    red: { bg: '#ff1744', glow: 'rgba(255, 23, 68, 0.4)' },
    amber: { bg: '#ffab00', glow: 'rgba(255, 171, 0, 0.4)' },
    cyan: { bg: '#00e5ff', glow: 'rgba(0, 229, 255, 0.4)' },
    off: { bg: '#505050', glow: 'none' },
  };

  const sizeMap = { sm: '8px', md: '12px' };
</script>

<span
  class="inline-block rounded-full"
  class:animate-pulse={pulse}
  style="width: {sizeMap[size]}; height: {sizeMap[size]}; background: {colorMap[color].bg}; box-shadow: 0 0 6px {colorMap[color].glow};"
></span>
