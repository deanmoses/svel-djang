import { browser } from '$app/environment';
import { onMount } from 'svelte';

export function createIsMobileFlag(maxWidthRem: number, initialValue: boolean | null = false) {
	const query = `(max-width: ${maxWidthRem}rem)`;
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
