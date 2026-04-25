<!--
	Redirect fallback for manual URL trimming. Users who delete the section
	segment from /<entity>/<slug>/edit/<section> land at /<entity>/<slug>/edit,
	which otherwise has no UI of its own. This component forwards them to the
	platform-appropriate default section URL: `?edit=<default>` on desktop
	(modal editor over the detail page) or `/edit/<default>` on mobile
	(dedicated edit shell).

	Consumed by each entity's /edit/+page.svelte. The companion +page.ts sets
	`ssr = false` so `createIsMobileFlag` can return the browser's synchronous
	`matchMedia` value on first render — no loading state needed.
-->
<script lang="ts">
  import { page } from '$app/state';
  import { goto } from '$app/navigation';
  import { LAYOUT_BREAKPOINT } from '$lib/constants';
  import { createIsMobileFlag } from '$lib/use-is-mobile.svelte';
  import { resolveHref } from '$lib/utils';

  let {
    basePath,
    path,
    defaultSegment,
  }: {
    basePath: string;
    /** See TaxonomyDetailBaseLayout's `path` prop. */
    path?: string;
    defaultSegment: string;
  } = $props();

  let slug = $derived(path ?? page.params.slug);
  const isMobileFlag = createIsMobileFlag(LAYOUT_BREAKPOINT);
  let isMobile = $derived<boolean | null>(isMobileFlag.current);

  $effect(() => {
    if (isMobile === false) {
      goto(resolveHref(`${basePath}/${slug}?edit=${defaultSegment}`), { replaceState: true });
    }
    if (isMobile === true) {
      goto(resolveHref(`${basePath}/${slug}/edit/${defaultSegment}`), { replaceState: true });
    }
  });
</script>
