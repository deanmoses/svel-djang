<script lang="ts">
	import { replaceState } from '$app/navigation';
	import { resolve } from '$app/paths';
	import client from '$lib/api/client';
	import { createAsyncLoader } from '$lib/async-loader.svelte';
	import ManufacturerActiveFilterChips from '$lib/components/ManufacturerActiveFilterChips.svelte';
	import CardGrid from '$lib/components/grid/CardGrid.svelte';
	import FilterDrawer from '$lib/components/FilterDrawer.svelte';
	import ClientFilteredGrid from '$lib/components/grid/ClientFilteredGrid.svelte';
	import SearchBox from '$lib/components/SearchBox.svelte';
	import SkeletonCard from '$lib/components/cards/SkeletonCard.svelte';
	import ManufacturerCard from '$lib/components/cards/ManufacturerCard.svelte';
	import ManufacturerFilterSidebar from '$lib/components/ManufacturerFilterSidebar.svelte';
	import { pageTitle } from '$lib/constants';
	import {
		filterManufacturers,
		mfrFiltersFromParams,
		mfrFiltersToParams,
		type FacetedManufacturer
	} from '$lib/manufacturer-facet-engine';

	const SKELETON_INDICES = Array.from({ length: 12 }, (_, i) => i);

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------
	const manufacturers = createAsyncLoader(async () => {
		const { data } = await client.GET('/api/manufacturers/all/');
		return (data ?? []) as FacetedManufacturer[];
	}, [] as FacetedManufacturer[]);

	// -----------------------------------------------------------------------
	// Filter state — initialized from URL, synced back on change
	// -----------------------------------------------------------------------
	let filters = $state(mfrFiltersFromParams(new URLSearchParams(window.location.search)));

	let initialRun = true;
	$effect(() => {
		const sp = mfrFiltersToParams(filters, new URLSearchParams());
		const search = sp.toString();
		if (initialRun) {
			initialRun = false;
			return;
		}
		replaceState(`${resolve('/manufacturers')}${search ? `?${search}` : ''}`, {});
	});

	let filteredManufacturers = $derived(filterManufacturers(manufacturers.data, filters));
</script>

<svelte:head>
	<title>{pageTitle('Manufacturers')}</title>
	<link rel="preload" as="fetch" href="/api/manufacturers/all/" crossorigin="anonymous" />
</svelte:head>

<div class="manufacturers-page">
	<SearchBox bind:value={filters.query} placeholder="Search manufacturers..." />

	{#if manufacturers.loading}
		<CardGrid>
			{#each SKELETON_INDICES as i (i)}
				<SkeletonCard />
			{/each}
		</CardGrid>
	{:else if manufacturers.error}
		<p class="error">{manufacturers.error}</p>
	{:else}
		<div class="layout">
			<FilterDrawer label="Filter manufacturers">
				<ManufacturerFilterSidebar allManufacturers={manufacturers.data} bind:filters />
			</FilterDrawer>

			<main class="results">
				<ManufacturerActiveFilterChips bind:filters allManufacturers={manufacturers.data} />
				<ClientFilteredGrid items={filteredManufacturers} entityName="manufacturer">
					{#snippet children(mfr)}
						<ManufacturerCard
							slug={mfr.slug}
							name={mfr.name}
							thumbnailUrl={mfr.thumbnail_url}
							modelCount={mfr.model_count}
						/>
					{/snippet}
				</ClientFilteredGrid>
			</main>
		</div>
	{/if}
</div>

<style>
	.manufacturers-page {
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
