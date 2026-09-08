<!--
  Invisible kiosk-mode shell. Mounted by the root +layout.svelte whenever
  the `mode=kiosk` cookie is set. Watches for visitor inactivity and
  navigates back to /kiosk after the idle timeout. Renders no visible UI.

  `idle_seconds` is read from the `kioskIdleSeconds` cookie (denormalized
  from the DB-backed config when an operator picks one) so this component
  doesn't need a server load on every navigation.
-->
<script lang="ts">
  import { on } from 'svelte/events';
  import { goto } from '$app/navigation';
  import { page } from '$app/state';
  import { DEFAULT_IDLE_SECONDS, getKioskIdleSecondsFromCookie } from './config';

  $effect(() => {
    // The whole point of kiosk mode: a device that's wandered off (to
    // /titles/foo, etc.) auto-returns to /kiosk on idle. The only route
    // we exclude is the staff editor — bouncing operators mid-edit would
    // be hostile.
    if (page.url.pathname.startsWith('/kiosk/edit')) return;

    const idleSeconds = getKioskIdleSecondsFromCookie() ?? DEFAULT_IDLE_SECONDS;
    const idleMs = idleSeconds * 1000;

    let timer: ReturnType<typeof setTimeout> | undefined;

    function reset() {
      if (timer !== undefined) clearTimeout(timer);
      timer = setTimeout(() => {
        void goto('/kiosk', { invalidateAll: true, replaceState: true });
      }, idleMs);
    }

    const events = ['pointerdown', 'keydown', 'touchstart'] as const;
    const offs = events.map((ev) => on(window, ev, reset, { passive: true }));
    reset();

    return () => {
      if (timer !== undefined) clearTimeout(timer);
      for (const off of offs) off();
    };
  });
</script>
