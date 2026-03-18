<script lang="ts">
  interface Props {
    value: number;
    min?: number;
    max?: number;
    step?: number;
    label?: string;
    unit?: string;
    onchange?: (value: number) => void;
  }
  let { value = $bindable(), min = 0, max = 1, step = 0.01, label, unit, onchange }: Props = $props();

  function handleInput(e: Event) {
    const target = e.target as HTMLInputElement;
    value = parseFloat(target.value);
    onchange?.(value);
  }
</script>

<div class="flex flex-col gap-1">
  {#if label}
    <label class="text-[10px] uppercase tracking-wider text-[--color-text-secondary] font-[--font-sans]">
      {label}
    </label>
  {/if}
  <input
    type="range"
    {min}
    {max}
    {step}
    {value}
    oninput={handleInput}
    class="w-full h-1 bg-[--color-bg-overlay] rounded appearance-none cursor-pointer
      [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3
      [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-[--color-accent-cyan]
      [&::-webkit-slider-thumb]:shadow-[0_0_6px_rgba(0,229,255,0.4)]"
  />
  <span class="text-[11px] font-[--font-mono] text-[--color-text-accent] tabular-nums">
    {value.toFixed(step < 1 ? 1 : 0)}{unit || ''}
  </span>
</div>
