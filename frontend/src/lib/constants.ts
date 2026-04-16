export const SITE_NAME = 'The Flip Pinball DB';

/**
 * Breakpoint (in rem) where the layout switches from single-column (mobile)
 * to two-column (desktop). CSS media queries can't use JS constants, so
 * TwoColumnLayout.svelte and layout files duplicate this as `52rem` —
 * search for "LAYOUT_BREAKPOINT" to find all copies.
 */
export const LAYOUT_BREAKPOINT = 52;

/** Build a browser tab title like "Manufacturers — The Flip Pinball DB". */
export const pageTitle = (name: string) => `${name} — ${SITE_NAME}`;
