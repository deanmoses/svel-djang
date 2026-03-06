<script lang="ts">
	import { replaceState } from '$app/navigation';
	import { page } from '$app/state';
	import SearchBox from '$lib/components/SearchBox.svelte';
	import SearchResults from '$lib/components/SearchResults.svelte';
	import { SITE_NAME } from '$lib/constants';
	import { resolveHref } from '$lib/utils';

	let searchQuery = $state(page.url.searchParams.get('q') ?? '');

	// Sync query to URL
	$effect(() => {
		const q = searchQuery.trim();
		const currentQ = page.url.searchParams.get('q') ?? '';
		if (q !== currentQ) {
			const url = new URL(page.url);
			if (q) {
				url.searchParams.set('q', q);
			} else {
				url.searchParams.delete('q');
			}
			replaceState(`${resolveHref('/search')}${url.search}`, {});
		}
	});
</script>

<svelte:head>
	<title>Search — {SITE_NAME}</title>
</svelte:head>

<div class="search-page">
	<h1 class="page-title">Search</h1>
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

	.page-title {
		font-size: var(--font-size-6);
		font-weight: 700;
		color: var(--color-text-primary);
		margin-bottom: var(--size-4);
	}
</style>
