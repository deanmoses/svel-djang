<script lang="ts">
	import { afterNavigate, replaceState } from '$app/navigation';
	import { onMount } from 'svelte';
	import SearchBox from '$lib/components/SearchBox.svelte';
	import SearchResults from '$lib/components/SearchResults.svelte';
	import { SITE_NAME } from '$lib/constants';
	import { resolveHref } from '$lib/utils';

	let searchQuery = $state('');
	let lastSyncedQ = '';

	// Sync URL → state. Uses window.location directly because page.url
	// may still reflect the prerendered URL (no query params) during hydration.
	function syncFromUrl() {
		const urlQ = new URLSearchParams(window.location.search).get('q') ?? '';
		searchQuery = urlQ;
		lastSyncedQ = urlQ.trim();
	}

	// onMount guarantees we read the real browser URL after hydration.
	onMount(syncFromUrl);

	// afterNavigate handles back/forward navigation (does NOT fire on replaceState).
	afterNavigate(syncFromUrl);

	// State → URL: update query string as user types.
	$effect(() => {
		const q = searchQuery.trim();
		if (q !== lastSyncedQ) {
			lastSyncedQ = q;
			const search = q ? `?q=${encodeURIComponent(q)}` : '';
			replaceState(`${resolveHref('/search')}${search}`, {});
		}
	});
</script>

<svelte:head>
	<title>Search — {SITE_NAME}</title>
	<link rel="preload" as="fetch" href="/api/titles/all/" crossorigin="anonymous" />
	<link rel="preload" as="fetch" href="/api/manufacturers/all/" crossorigin="anonymous" />
	<link rel="preload" as="fetch" href="/api/models/all/" crossorigin="anonymous" />
	<link rel="preload" as="fetch" href="/api/people/all/" crossorigin="anonymous" />
</svelte:head>

<div class="search-page">
	<SearchBox
		bind:value={searchQuery}
		placeholder="Search titles, manufacturers, people..."
		autofocus
	/>
	<SearchResults query={searchQuery} />
</div>

<style>
	.search-page {
		padding: var(--size-5) 0;
	}
</style>
