import { browser } from '$app/environment';
import { on } from 'svelte/events';
import { onMount } from 'svelte';

/**
 * Reactive flag for "is the viewport below this rem threshold?"
 *
 * Pair with the shared CSS `@custom-media` names in `app.css` —
 * `createBelowBreakpointFlag(NARROW_BREAKPOINT)` mirrors `(--breakpoint-narrow)`,
 * `createBelowBreakpointFlag(WIDE_BREAKPOINT)` mirrors `not (--breakpoint-wide)`.
 */
export function createBelowBreakpointFlag(
  maxWidthRem: number,
  initialValue: boolean | null = false,
) {
  const query = `(max-width: ${maxWidthRem}rem)`;
  // Read matchMedia synchronously on the first browser tick so deep-links
  // that gate on the flag (e.g. mobile edit shells) render the correct
  // UI on first paint. Without this, desktop users briefly see the mobile
  // shell before onMount() settles the value.
  let isBelow = $state<boolean | null>(browser ? matchMedia(query).matches : initialValue);

  onMount(() => {
    const mql = matchMedia(query);
    isBelow = mql.matches;

    function onChange(event: MediaQueryListEvent) {
      isBelow = event.matches;
    }

    return on(mql, 'change', onChange);
  });

  return {
    get current() {
      return isBelow;
    },
  };
}
