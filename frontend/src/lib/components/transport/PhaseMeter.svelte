<script lang="ts">
  interface Props {
    value: number;
    label: string;
  }
  let { value, label }: Props = $props();
</script>

<div class="flex flex-col gap-1">
  <span class="text-[10px] font-[--font-mono] uppercase text-[--color-text-secondary] tracking-wider">{label}</span>
  <div class="h-2 bg-[--color-bg-overlay] rounded-full overflow-hidden">
    <div
      class="h-full bg-[--color-accent-cyan] rounded-full transition-[width] duration-75"
      style="width: {value * 100}%; box-shadow: 0 0 8px rgba(0, 229, 255, 0.4);"
    ></div>
  </div>
</div>
