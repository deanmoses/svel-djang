<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { defaultManufacturerSectionSegment } from '$lib/components/editors/manufacturer-edit-sections';
	import { LAYOUT_BREAKPOINT } from '$lib/constants';

	let slug = $derived(page.params.slug);
	let isMobile = $state<boolean | null>(null);

	$effect(() => {
		const mql = matchMedia(`(max-width: ${LAYOUT_BREAKPOINT}rem)`);
		isMobile = mql.matches;
		function onChange(e: MediaQueryListEvent) {
			isMobile = e.matches;
		}
		mql.addEventListener('change', onChange);
		return () => mql.removeEventListener('change', onChange);
	});

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
