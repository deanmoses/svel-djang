<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { defaultManufacturerSectionSegment } from '$lib/components/editors/manufacturer-edit-sections';
	import { LAYOUT_BREAKPOINT } from '$lib/constants';
	import { createIsMobileFlag } from '$lib/use-is-mobile.svelte';

	let slug = $derived(page.params.slug);
	const isMobileFlag = createIsMobileFlag(LAYOUT_BREAKPOINT);
	let isMobile = $derived<boolean | null>(isMobileFlag.current);

	$effect(() => {
		if (isMobile === false) {
			goto(resolve(`/manufacturers/${slug}?edit=${defaultManufacturerSectionSegment()}`), {
				replaceState: true
			});
		}
		if (isMobile === true) {
			goto(resolve(`/manufacturers/${slug}/edit/${defaultManufacturerSectionSegment()}`), {
				replaceState: true
			});
		}
	});
</script>
