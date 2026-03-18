<script lang="ts">
  import { Progress } from '$lib/components/ui/progress/index.js';

  interface Props {
    value: number;
    label: string;
  }
  let { value, label }: Props = $props();
</script>

<div class="flex items-center gap-3">
  <span class="text-[10px] uppercase text-muted-foreground tracking-wider w-8 shrink-0 text-right">
    {label}
  </span>
  <Progress value={value * 100} class="h-1.5" />
</div>
