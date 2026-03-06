<script lang="ts">
	import { replaceState } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import SearchBox from '$lib/components/SearchBox.svelte';
	import SearchResults from '$lib/components/SearchResults.svelte';
	import { SITE_NAME } from '$lib/constants';
	import { normalizeText } from '$lib/util';

	const MIN_QUERY_LENGTH = 2;

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
			replaceState(`${resolve('/')}${url.search}`, {});
		}
	});

	let isSearching = $derived(normalizeText(searchQuery.trim()).length >= MIN_QUERY_LENGTH);
</script>

<svelte:head>
	<title>{SITE_NAME}</title>
</svelte:head>

<div class="search-page">
	<div class="search-hero" class:compact={isSearching}>
		<h1 class="site-title">{SITE_NAME}</h1>
		{#if !isSearching}
			<p class="tagline">The open encyclopedia of pinball machines</p>
		{/if}
		<SearchBox bind:value={searchQuery} placeholder="Search titles, manufacturers, people..." />
	</div>

	<SearchResults query={searchQuery} />
</div>

<style>
	.search-page {
		padding: var(--size-5) 0;
	}

	.search-hero {
		text-align: center;
		padding: var(--size-10) 0 var(--size-6);
		transition: padding 0.2s ease;
	}

	.search-hero.compact {
		padding: var(--size-4) 0 var(--size-4);
	}

	.site-title {
		font-size: var(--font-size-8);
		font-weight: 700;
		color: var(--color-text-primary);
		margin-bottom: var(--size-2);
	}

	.compact .site-title {
		font-size: var(--font-size-5);
	}

	.tagline {
		font-size: var(--font-size-3);
		color: var(--color-text-muted);
		margin-bottom: var(--size-6);
	}
</style>
