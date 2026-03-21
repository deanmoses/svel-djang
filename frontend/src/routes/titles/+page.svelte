<script lang="ts">
	import { replaceState } from '$app/navigation';
	import { resolve } from '$app/paths';
	import client from '$lib/api/client';
	import { createAsyncLoader } from '$lib/async-loader.svelte';
	import ActiveFilterChips from '$lib/components/ActiveFilterChips.svelte';
	import CardGrid from '$lib/components/grid/CardGrid.svelte';
	import FilterDrawer from '$lib/components/FilterDrawer.svelte';
	import ClientFilteredGrid from '$lib/components/grid/ClientFilteredGrid.svelte';
	import SearchBox from '$lib/components/SearchBox.svelte';
	import SkeletonCard from '$lib/components/cards/SkeletonCard.svelte';
	import TitleCard from '$lib/components/cards/TitleCard.svelte';
	import TitleFilterSidebar from '$lib/components/TitleFilterSidebar.svelte';
	import { pageTitle } from '$lib/constants';
	import {
		expandTitlesWithAncestorThemes,
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
		const [titlesRes, themesRes] = await Promise.all([
			client.GET('/api/titles/all/'),
			client.GET('/api/themes/')
		]);
		const raw = (titlesRes.data ?? []) as FacetedTitle[];
		const themeHierarchy = (themesRes.data ?? []) as {
			slug: string;
			name: string;
			parent_slugs: string[];
		}[];
		return expandTitlesWithAncestorThemes(raw, themeHierarchy);
	}, [] as FacetedTitle[]);

	// -----------------------------------------------------------------------
	// Filter state — initialized from URL, synced back on change
	// -----------------------------------------------------------------------
	let filters = $state(filtersFromParams(new URLSearchParams(window.location.search)));

	let initialRun = true;
	$effect(() => {
		const sp = filtersToParams(filters, new URLSearchParams());
		const search = sp.toString();
		if (initialRun) {
			initialRun = false;
			return;
		}
		replaceState(`${resolve('/titles')}${search ? `?${search}` : ''}`, {});
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
			<FilterDrawer label="Filter titles">
				<TitleFilterSidebar allTitles={titles.data} bind:filters />
			</FilterDrawer>

			<main class="results">
				<ActiveFilterChips bind:filters allTitles={titles.data} />
				<ClientFilteredGrid items={filteredTitles} entityName="title">
					{#snippet children(title)}
						<TitleCard
							slug={title.slug}
							name={title.name}
							thumbnailUrl={title.thumbnail_url}
							manufacturerName={title.manufacturer_name}
							year={title.year}
						/>
					{/snippet}
				</ClientFilteredGrid>
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

	.results {
		min-width: 0;
	}

	.error {
		text-align: center;
		color: var(--color-error);
		padding: var(--size-6) 0;
	}

	@media (max-width: 640px) {
		.layout {
			grid-template-columns: 1fr;
		}
	}
</style>
