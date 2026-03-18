<script lang="ts">
  import type { EffectParamSchema } from '$lib/api/client';
  import { Slider } from '$lib/components/ui/slider/index.js';
  import { Switch } from '$lib/components/ui/switch/index.js';
  import { Label } from '$lib/components/ui/label/index.js';

  interface Props {
    name: string;
    schema: EffectParamSchema;
    value: unknown;
    onchange: (value: unknown) => void;
  }
  let { name, schema, value, onchange }: Props = $props();
</script>

{#if schema.type === 'float' || schema.type === 'int'}
  <div class="flex flex-col gap-2">
    <div class="flex items-baseline justify-between">
      <Label class="text-xs">{schema.label || name}</Label>
      <span class="text-xs text-primary tabular-nums font-mono">
        {(value as number).toFixed(schema.step && schema.step < 1 ? 1 : 0)}
      </span>
    </div>
    <Slider
      type="single"
      value={value as number}
      min={schema.min ?? 0}
      max={schema.max ?? 100}
      step={schema.step ?? (schema.type === 'int' ? 1 : 0.1)}
      onValueChange={(v) => onchange(v)}
    />
  </div>
{:else if schema.type === 'bool'}
  <div class="flex items-center gap-3">
    <Switch
      checked={value as boolean}
      onCheckedChange={(v) => onchange(v)}
    />
    <Label class="text-xs">{schema.label || name}</Label>
  </div>
{/if}
