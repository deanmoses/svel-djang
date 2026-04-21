import { browser } from '$app/environment';
import { onMount } from 'svelte';

export function createIsMobileFlag(maxWidthRem: number, initialValue: boolean | null = false) {
	const query = `(max-width: ${maxWidthRem}rem)`;
	// Read matchMedia synchronously on the first browser tick so deep-links
	// that gate on `isMobile` (e.g. mobile edit shells) render the correct
	// UI on first paint. Without this, desktop users briefly see the mobile
	// shell before onMount() settles the value.
	let isMobile = $state<boolean | null>(browser ? matchMedia(query).matches : initialValue);

	onMount(() => {
		const mql = matchMedia(query);
		isMobile = mql.matches;

		function onChange(event: MediaQueryListEvent) {
			isMobile = event.matches;
		}

		mql.addEventListener('change', onChange);
		return () => mql.removeEventListener('change', onChange);
	});

	return {
		get current() {
			return isMobile;
		}
	};
}
