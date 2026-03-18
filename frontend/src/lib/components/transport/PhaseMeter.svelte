<script lang="ts">
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
  <div class="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
    <div
      class="h-full rounded-full bg-primary transition-[width] duration-75"
      style="width: {value * 100}%;"
    ></div>
  </div>
</div>
