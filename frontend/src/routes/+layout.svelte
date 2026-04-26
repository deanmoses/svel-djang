<script lang="ts">
  import '../app.css';
  import { page } from '$app/state';
  import SiteShell from '$lib/components/SiteShell.svelte';
  import FocusSiteShell from '$lib/components/FocusSiteShell.svelte';
  import ToastHost from '$lib/toast/ToastHost.svelte';
  import { isFocusModePath } from '$lib/focus-mode';

  let { children } = $props();

  let isFocusMode = $derived(isFocusModePath(page.url.pathname));
</script>

<div class="app-root">
  {#if isFocusMode}
    <FocusSiteShell>
      {@render children()}
    </FocusSiteShell>
  {:else}
    <SiteShell>
      {@render children()}
    </SiteShell>
  {/if}

  <ToastHost />
</div>

<style>
  .app-root {
    display: flex;
    flex-direction: column;
    min-height: 100dvh;
  }
</style>
