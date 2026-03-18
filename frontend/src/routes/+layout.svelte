<script lang="ts">
  import '../app.css';
  import type { Snippet } from 'svelte';
  import { wsClient } from '$lib/ws/client';
  import { beatStore } from '$lib/stores/beat.svelte';
  import { effectsStore } from '$lib/stores/effects.svelte';
  import { devicesStore } from '$lib/stores/devices.svelte';
  import { onMount } from 'svelte';
  import { page } from '$app/state';
  import LedIndicator from '$lib/components/common/LedIndicator.svelte';

  interface Props {
    children: Snippet;
  }
  let { children }: Props = $props();

  const tabs = [
    { label: 'LIVE', href: '/' },
    { label: 'SCENE', href: '/scene' },
    { label: 'DEVICES', href: '/devices' },
    { label: 'CONFIG', href: '/config' },
  ];

  onMount(() => {
    wsClient.connect();
    wsClient.subscribeBeat(30);
    wsClient.subscribeFrames(30);
    effectsStore.init();
    devicesStore.init();
    beatStore.startInterpolation();

    return () => {
      wsClient.disconnect();
      beatStore.stopInterpolation();
    };
  });
</script>

<div class="h-screen flex flex-col bg-background overflow-hidden">
  <nav class="h-11 flex items-center px-4 bg-card border-b border-border shrink-0">
    <span class="font-display text-primary text-sm font-bold mr-6 tracking-widest select-none">
      dj-ledfx
    </span>

    <div class="flex gap-1">
      {#each tabs as tab}
        {@const active = page.url.pathname === tab.href}
        <a
          href={tab.href}
          class="px-3 py-1.5 text-xs font-medium rounded-md transition-colors
            {active
              ? 'bg-accent text-accent-foreground'
              : 'text-muted-foreground hover:text-foreground hover:bg-accent/50'}"
        >
          {tab.label}
        </a>
      {/each}
    </div>

    <div class="ml-auto flex items-center gap-4 text-xs text-muted-foreground">
      <span class="flex items-center gap-1.5">
        <LedIndicator color={beatStore.wsConnected ? 'green' : 'red'} size="sm" />
        WS
      </span>
      <span class="flex items-center gap-1.5">
        <LedIndicator color={beatStore.isPlaying ? 'cyan' : 'off'} size="sm" />
        {beatStore.isPlaying ? 'PLAYING' : 'STOPPED'}
      </span>
    </div>
  </nav>

  <main class="flex-1 overflow-hidden">
    {@render children()}
  </main>
</div>
