<script lang="ts">
  import type { EffectParamSchema } from '$lib/api/client';
  import Fader from '$lib/components/common/Fader.svelte';

  interface Props {
    name: string;
    schema: EffectParamSchema;
    value: unknown;
    onchange: (value: unknown) => void;
  }
  let { name, schema, value, onchange }: Props = $props();
</script>

{#if schema.type === 'float' || schema.type === 'int'}
  <Fader
    value={value as number}
    min={schema.min ?? 0}
    max={schema.max ?? 100}
    step={schema.step ?? (schema.type === 'int' ? 1 : 0.1)}
    label={schema.label || name}
    onchange={(v) => onchange(v)}
  />
{:else if schema.type === 'bool'}
  <label class="flex items-center gap-2 cursor-pointer">
    <input
      type="checkbox"
      checked={value as boolean}
      onchange={(e) => onchange((e.target as HTMLInputElement).checked)}
      class="accent-[--color-accent-cyan]"
    />
    <span class="text-[10px] uppercase tracking-wider text-[--color-text-secondary] font-[--font-sans]">
      {schema.label || name}
    </span>
  </label>
{/if}
