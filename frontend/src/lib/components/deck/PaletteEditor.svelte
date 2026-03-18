<script lang="ts">
  interface Props {
    colors: string[];
    onchange: (colors: string[]) => void;
  }
  let { colors, onchange }: Props = $props();

  function updateColor(index: number, value: string) {
    const newColors = [...colors];
    newColors[index] = value;
    onchange(newColors);
  }
</script>

<div class="flex flex-col gap-1">
  <span class="text-[10px] uppercase tracking-wider text-[--color-text-secondary] font-[--font-sans]">Palette</span>
  <div class="flex gap-1 flex-wrap">
    {#each colors as color, i}
      <input
        type="color"
        value={color}
        onchange={(e) => updateColor(i, (e.target as HTMLInputElement).value)}
        class="w-7 h-7 rounded border border-[--color-border-subtle] bg-transparent cursor-pointer"
      />
    {/each}
  </div>
</div>
