<script lang="ts">
	import { replaceState } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import client from '$lib/api/client';
	import { createAsyncLoader } from '$lib/async-loader.svelte';
	import CardGrid from '$lib/components/grid/CardGrid.svelte';
	import InfiniteGrid from '$lib/components/grid/InfiniteGrid.svelte';
	import SearchBox from '$lib/components/SearchBox.svelte';
	import SkeletonCard from '$lib/components/cards/SkeletonCard.svelte';
	import TitleCard from '$lib/components/cards/TitleCard.svelte';
	import TitleFilterSidebar from '$lib/components/TitleFilterSidebar.svelte';
	import { pageTitle } from '$lib/constants';
	import {
		filterTitles,
		filtersFromParams,
		filtersToParams,
		type FacetedTitle
	} from '$lib/facet-engine';

	const SKELETON_INDICES = Array.from({ length: 12 }, (_, i) => i);

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------
	const titles = createAsyncLoader(async () => {
		const { data } = await client.GET('/api/titles/all/');
		return (data ?? []) as FacetedTitle[];
	}, [] as FacetedTitle[]);

	// -----------------------------------------------------------------------
	// Filter state — initialized from URL, synced back on change
	// -----------------------------------------------------------------------
	let filters = $state(filtersFromParams(page.url.searchParams));

	$effect(() => {
		const url = new URL(page.url);
		filtersToParams(filters, url.searchParams);
		// eslint-disable-next-line svelte/no-navigation-without-resolve -- resolve() is used in the template literal
		replaceState(`${resolve('/titles')}${url.search}`, {});
	});

	let filteredTitles = $derived(filterTitles(titles.data, filters));
</script>

<svelte:head>
	<title>{pageTitle('Titles')}</title>
	<link rel="preload" as="fetch" href="/api/titles/all/" crossorigin="anonymous" />
</svelte:head>

<div class="titles-page">
	<SearchBox bind:value={filters.query} placeholder="Search titles..." />

	{#if titles.loading}
		<CardGrid>
			{#each SKELETON_INDICES as i (i)}
				<SkeletonCard />
			{/each}
		</CardGrid>
	{:else if titles.error}
		<p class="error">{titles.error}</p>
	{:else}
		<div class="layout">
			<TitleFilterSidebar allTitles={titles.data} bind:filters />

			<main class="results">
				<InfiniteGrid items={filteredTitles} entityName="title">
					{#snippet children(title)}
						<TitleCard
							slug={title.slug}
							name={title.name}
							thumbnailUrl={title.thumbnail_url}
							short_name={title.short_name}
						/>
					{/snippet}
				</InfiniteGrid>
			</main>
		</div>
	{/if}
</div>

<style>
	.titles-page {
		padding: var(--size-5) 0;
	}

	.layout {
		display: grid;
		grid-template-columns: 16rem 1fr;
		gap: var(--size-5);
		align-items: start;
	}

	@media (max-width: 640px) {
		.layout {
			grid-template-columns: 1fr;
		}
	}

	.results {
		min-width: 0;
	}

	.error {
		text-align: center;
		color: var(--color-error);
		padding: var(--size-6) 0;
	}
</style>
