<script lang="ts">
  import '../app.css';
  import type { Snippet } from 'svelte';
  import { wsClient } from '$lib/ws/client';
  import { beatStore } from '$lib/stores/beat.svelte';
  import { effectsStore } from '$lib/stores/effects.svelte';
  import { devicesStore } from '$lib/stores/devices.svelte';
  import { onMount } from 'svelte';
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

  let currentPath = $state('/');

  onMount(() => {
    // Initialize WebSocket
    wsClient.connect();
    wsClient.subscribeBeat(10);

    // Initialize stores
    effectsStore.init();
    devicesStore.init();
    beatStore.startInterpolation();

    // Track current path
    currentPath = window.location.pathname;

    return () => {
      wsClient.disconnect();
      beatStore.stopInterpolation();
    };
  });

  function navigate(href: string) {
    currentPath = href;
  }
</script>

<div class="min-h-screen flex flex-col bg-[--color-bg-base]">
  <!-- Navigation -->
  <nav class="h-10 flex items-center px-4 bg-[--color-bg-surface] border-b border-[--color-border-subtle] shrink-0">
    <span class="font-[--font-mono] text-[--color-accent-cyan] text-sm font-bold mr-6 tracking-wider">
      dj-ledfx
    </span>
    <div class="flex gap-1">
      {#each tabs as tab}
        <a
          href={tab.href}
          class="px-3 py-1 text-[11px] font-[--font-mono] uppercase tracking-wider rounded transition-colors
            {currentPath === tab.href
              ? 'text-[--color-accent-cyan] bg-[--color-accent-cyan]/10'
              : 'text-[--color-text-secondary] hover:text-[--color-text-primary] hover:bg-[--color-bg-elevated]'}"
          onclick={() => { navigate(tab.href); }}
        >
          {tab.label}
        </a>
      {/each}
    </div>
    <div class="ml-auto flex items-center gap-3 text-[10px] font-[--font-mono] text-[--color-text-secondary]">
      <span class="flex items-center gap-1.5">
        <LedIndicator color={beatStore.wsConnected ? 'green' : 'red'} />
        WS
      </span>
      <span class="flex items-center gap-1.5">
        <LedIndicator color={beatStore.isPlaying ? 'cyan' : 'off'} />
        {beatStore.isPlaying ? 'PLAYING' : 'STOPPED'}
      </span>
    </div>
  </nav>

  <!-- Main content -->
  <main class="flex-1 overflow-hidden">
    {@render children()}
  </main>
</div>
