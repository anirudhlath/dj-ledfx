<script lang="ts">
  import { Label } from '$lib/components/ui/label/index.js';

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

<div class="flex flex-col gap-2">
  <Label class="text-xs">Palette</Label>
  <div class="flex gap-1.5 flex-wrap">
    {#each colors as color, i}
      <input
        type="color"
        value={color}
        onchange={(e) => updateColor(i, (e.target as HTMLInputElement).value)}
        class="w-8 h-8 rounded-md border border-input bg-transparent cursor-pointer"
      />
    {/each}
  </div>
</div>
