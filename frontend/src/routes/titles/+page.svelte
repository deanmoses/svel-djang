<script lang="ts">
	import { replaceState } from '$app/navigation';
	import { resolve } from '$app/paths';
	import client from '$lib/api/client';
	import { createAsyncLoader } from '$lib/async-loader.svelte';
	import { auth } from '$lib/auth.svelte';
	import ActiveFilterChips from '$lib/components/ActiveFilterChips.svelte';
	import CardGrid from '$lib/components/grid/CardGrid.svelte';
	import FilterDrawer from '$lib/components/FilterDrawer.svelte';
	import ClientFilteredGrid from '$lib/components/grid/ClientFilteredGrid.svelte';
	import NoResultsCreatePrompt from '$lib/components/NoResultsCreatePrompt.svelte';
	import SearchBox from '$lib/components/SearchBox.svelte';
	import SkeletonCard from '$lib/components/cards/SkeletonCard.svelte';
	import TitleCard from '$lib/components/cards/TitleCard.svelte';
	import TitleFilterSidebar from '$lib/components/TitleFilterSidebar.svelte';
	import { pageTitle } from '$lib/constants';
	import {
		expandTitlesWithAncestorFeatures,
		expandTitlesWithAncestorThemes,
		filterTitles,
		filtersFromParams,
		filtersToParams,
		type FacetedTitle,
		type GameplayFeatureHierarchyEntry
	} from '$lib/facet-engine';
	import { decideCreatePrompt } from './titles-create-prompt';

	const SKELETON_INDICES = Array.from({ length: 12 }, (_, i) => i);

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------
	const titles = createAsyncLoader(async () => {
		const [titlesRes, themesRes, featuresRes] = await Promise.all([
			client.GET('/api/titles/all/'),
			client.GET('/api/themes/'),
			client.GET('/api/gameplay-features/')
		]);
		let data = (titlesRes.data ?? []) as FacetedTitle[];
		const themeHierarchy = (themesRes.data ?? []) as {
			slug: string;
			name: string;
			parent_slugs: string[];
		}[];
		const featureHierarchy = (featuresRes.data ?? []) as GameplayFeatureHierarchyEntry[];
		data = expandTitlesWithAncestorThemes(data, themeHierarchy);
		data = expandTitlesWithAncestorFeatures(data, featureHierarchy);
		return data;
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

	let createPrompt = $derived(
		decideCreatePrompt({
			titles: titles.data,
			query: filters.query,
			isAuthenticated: auth.isAuthenticated
		})
	);

	let createHref = $derived(
		`${resolve('/titles/new')}?name=${encodeURIComponent(createPrompt.query)}`
	);

	$effect(() => {
		void auth.load();
	});
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
							manufacturerName={title.manufacturer?.name}
							year={title.year}
						/>
					{/snippet}
				</ClientFilteredGrid>
				{#if createPrompt.show}
					<NoResultsCreatePrompt entityLabel="title" query={createPrompt.query} {createHref} />
				{/if}
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
