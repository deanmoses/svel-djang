<script lang="ts">
	import { replaceState } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import { SvelteSet } from 'svelte/reactivity';
	import client from '$lib/api/client';
	import { createAsyncLoader } from '$lib/async-loader.svelte';
	import CardGrid from '$lib/components/grid/CardGrid.svelte';
	import MachineCard from '$lib/components/cards/MachineCard.svelte';
	import ManufacturerCard from '$lib/components/cards/ManufacturerCard.svelte';
	import PersonCard from '$lib/components/cards/PersonCard.svelte';
	import SearchBox from '$lib/components/SearchBox.svelte';
	import TitleCard from '$lib/components/cards/TitleCard.svelte';
	import { SITE_NAME } from '$lib/constants';
	import { normalizeText } from '$lib/util';

	const MIN_QUERY_LENGTH = 2;
	const PREVIEW_SIZE = 5;

	// Reactive search query synced to URL ?q= param
	let searchQuery = $state(page.url.searchParams.get('q') ?? '');

	// Track which groups are expanded
	let expanded: Record<string, boolean> = $state({});

	// Prefetch all datasets on mount
	const titles = createAsyncLoader(async () => {
		const { data } = await client.GET('/api/titles/all/');
		return data ?? [];
	}, []);

	const models = createAsyncLoader(async () => {
		const { data } = await client.GET('/api/models/all/');
		return data ?? [];
	}, []);

	const manufacturers = createAsyncLoader(async () => {
		const { data } = await client.GET('/api/manufacturers/all/');
		return data ?? [];
	}, []);

	const people = createAsyncLoader(async () => {
		const { data } = await client.GET('/api/people/all/');
		return data ?? [];
	}, []);

	const systems = createAsyncLoader(async () => {
		const { data } = await client.GET('/api/systems/all/');
		return data ?? [];
	}, []);

	const series = createAsyncLoader(async () => {
		const { data } = await client.GET('/api/series/');
		return data ?? [];
	}, []);

	const franchises = createAsyncLoader(async () => {
		const { data } = await client.GET('/api/franchises/all/');
		return data ?? [];
	}, []);

	// Sync query to URL via SvelteKit's shallow routing.
	// replaceState keeps the router aware of the URL so back/forward just works —
	// navigating back re-creates this component, which initializes searchQuery from page.url.
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
			// eslint-disable-next-line svelte/no-navigation-without-resolve -- resolve() is used in the template literal
			replaceState(`${resolve('/')}${url.search}`, {});
		}
	});

	// Reset expanded when query changes
	$effect(() => {
		void searchQuery;
		expanded = {};
	});

	let normalizedQuery = $derived(normalizeText(searchQuery.trim()));
	let isSearching = $derived(normalizedQuery.length >= MIN_QUERY_LENGTH);

	function textMatches(q: string, ...fields: (string | number | null | undefined)[]): boolean {
		return fields.some((f) => f != null && normalizeText(String(f)).includes(q));
	}

	// --- Filtered results ---

	let matchedModels = $derived.by(() => {
		if (!isSearching) return [];
		return models.data.filter(
			(m) =>
				textMatches(normalizedQuery, m.name, m.shortname) ||
				(m.search_text && normalizeText(m.search_text).includes(normalizedQuery))
		);
	});

	// Title slugs from matched models for roll-up
	let rollupTitleSlugs = $derived.by(() => {
		const slugs = new SvelteSet<string>();
		for (const m of matchedModels) {
			if (m.title_slug) slugs.add(m.title_slug);
		}
		return slugs;
	});

	let matchedTitles = $derived.by(() => {
		if (!isSearching) return [];
		return titles.data.filter(
			(t) => textMatches(normalizedQuery, t.name, t.short_name) || rollupTitleSlugs.has(t.slug)
		);
	});

	let matchedManufacturers = $derived.by(() => {
		if (!isSearching) return [];
		return manufacturers.data.filter(
			(m) =>
				textMatches(normalizedQuery, m.name, m.trade_name) ||
				(m.search_text && normalizeText(m.search_text).includes(normalizedQuery))
		);
	});

	let matchedPeople = $derived.by(() => {
		if (!isSearching) return [];
		return people.data.filter((p) => textMatches(normalizedQuery, p.name));
	});

	let matchedSystems = $derived.by(() => {
		if (!isSearching) return [];
		return systems.data.filter((s) => textMatches(normalizedQuery, s.name, s.manufacturer_name));
	});

	let matchedSeries = $derived.by(() => {
		if (!isSearching) return [];
		return series.data.filter((s) => textMatches(normalizedQuery, s.name));
	});

	let matchedFranchises = $derived.by(() => {
		if (!isSearching) return [];
		return franchises.data.filter((f) => textMatches(normalizedQuery, f.name));
	});

	let totalResults = $derived(
		matchedTitles.length +
			matchedModels.length +
			matchedManufacturers.length +
			matchedPeople.length +
			matchedSystems.length +
			matchedSeries.length +
			matchedFranchises.length
	);

	let anyLoading = $derived(
		titles.loading ||
			models.loading ||
			manufacturers.loading ||
			people.loading ||
			systems.loading ||
			series.loading ||
			franchises.loading
	);

	function toggleGroup(group: string) {
		expanded[group] = !expanded[group];
	}
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
		<SearchBox bind:value={searchQuery} placeholder="Search titles, models, people..." />
	</div>

	{#if searchQuery.trim().length > 0 && searchQuery.trim().length < MIN_QUERY_LENGTH}
		<p class="hint">Type at least {MIN_QUERY_LENGTH} characters to search</p>
	{/if}

	{#if isSearching}
		<div class="results-summary">
			{#if anyLoading}
				<p class="count">Searching...</p>
			{:else}
				<p class="count">
					{totalResults.toLocaleString()} result{totalResults === 1 ? '' : 's'}
				</p>
			{/if}
		</div>

		<!-- Titles -->
		{#if matchedTitles.length > 0}
			{@const showAll = expanded['titles']}
			{@const items = showAll ? matchedTitles : matchedTitles.slice(0, PREVIEW_SIZE)}
			<section class="result-group">
				<h2>Titles <span class="group-count">{matchedTitles.length}</span></h2>
				<CardGrid>
					{#each items as title (title.slug)}
						<TitleCard
							slug={title.slug}
							name={title.name}
							thumbnailUrl={title.thumbnail_url}
							short_name={title.short_name}
						/>
					{/each}
				</CardGrid>
				{#if matchedTitles.length > PREVIEW_SIZE}
					<button class="see-all" onclick={() => toggleGroup('titles')}>
						{showAll ? 'Show less' : `See all ${matchedTitles.length.toLocaleString()} titles`}
					</button>
				{/if}
			</section>
		{/if}

		<!-- Models -->
		{#if matchedModels.length > 0}
			{@const showAll = expanded['models']}
			{@const items = showAll ? matchedModels : matchedModels.slice(0, PREVIEW_SIZE)}
			<section class="result-group">
				<h2>Models <span class="group-count">{matchedModels.length}</span></h2>
				<CardGrid>
					{#each items as model (model.slug)}
						<MachineCard
							slug={model.slug}
							name={model.name}
							thumbnailUrl={model.thumbnail_url}
							manufacturerName={model.manufacturer_name}
							year={model.year}
						/>
					{/each}
				</CardGrid>
				{#if matchedModels.length > PREVIEW_SIZE}
					<button class="see-all" onclick={() => toggleGroup('models')}>
						{showAll ? 'Show less' : `See all ${matchedModels.length.toLocaleString()} models`}
					</button>
				{/if}
			</section>
		{/if}

		<!-- Manufacturers -->
		{#if matchedManufacturers.length > 0}
			{@const showAll = expanded['manufacturers']}
			{@const items = showAll ? matchedManufacturers : matchedManufacturers.slice(0, PREVIEW_SIZE)}
			<section class="result-group">
				<h2>
					Manufacturers <span class="group-count">{matchedManufacturers.length}</span>
				</h2>
				<CardGrid>
					{#each items as mfr (mfr.slug)}
						<ManufacturerCard
							slug={mfr.slug}
							name={mfr.name}
							thumbnailUrl={mfr.thumbnail_url}
							tradeName={mfr.trade_name}
							modelCount={mfr.model_count}
						/>
					{/each}
				</CardGrid>
				{#if matchedManufacturers.length > PREVIEW_SIZE}
					<button class="see-all" onclick={() => toggleGroup('manufacturers')}>
						{showAll
							? 'Show less'
							: `See all ${matchedManufacturers.length.toLocaleString()} manufacturers`}
					</button>
				{/if}
			</section>
		{/if}

		<!-- People -->
		{#if matchedPeople.length > 0}
			{@const showAll = expanded['people']}
			{@const items = showAll ? matchedPeople : matchedPeople.slice(0, PREVIEW_SIZE)}
			<section class="result-group">
				<h2>People <span class="group-count">{matchedPeople.length}</span></h2>
				<CardGrid>
					{#each items as person (person.slug)}
						<PersonCard
							slug={person.slug}
							name={person.name}
							thumbnailUrl={person.thumbnail_url}
							creditCount={person.credit_count}
						/>
					{/each}
				</CardGrid>
				{#if matchedPeople.length > PREVIEW_SIZE}
					<button class="see-all" onclick={() => toggleGroup('people')}>
						{showAll ? 'Show less' : `See all ${matchedPeople.length.toLocaleString()} people`}
					</button>
				{/if}
			</section>
		{/if}

		<!-- Systems -->
		{#if matchedSystems.length > 0}
			<section class="result-group">
				<h2>Systems <span class="group-count">{matchedSystems.length}</span></h2>
				<ul class="list-rows">
					{#each matchedSystems as system (system.slug)}
						<li>
							<a href={resolve(`/systems/${system.slug}`)} class="list-row">
								<span class="list-name">{system.name}</span>
								<span class="list-meta">
									{#if system.manufacturer_name}
										<span>{system.manufacturer_name}</span>
									{/if}
									<span>{system.machine_count} machine{system.machine_count === 1 ? '' : 's'}</span>
								</span>
							</a>
						</li>
					{/each}
				</ul>
			</section>
		{/if}

		<!-- Series -->
		{#if matchedSeries.length > 0}
			<section class="result-group">
				<h2>Series <span class="group-count">{matchedSeries.length}</span></h2>
				<ul class="list-rows">
					{#each matchedSeries as s (s.slug)}
						<li>
							<a href={resolve(`/series/${s.slug}`)} class="list-row">
								<span class="list-name">{s.name}</span>
								<span class="list-meta">
									<span>{s.title_count} title{s.title_count === 1 ? '' : 's'}</span>
								</span>
							</a>
						</li>
					{/each}
				</ul>
			</section>
		{/if}

		<!-- Franchises -->
		{#if matchedFranchises.length > 0}
			<section class="result-group">
				<h2>Franchises <span class="group-count">{matchedFranchises.length}</span></h2>
				<ul class="list-rows">
					{#each matchedFranchises as f (f.slug)}
						<li>
							<a href={resolve(`/franchises/${f.slug}`)} class="list-row">
								<span class="list-name">{f.name}</span>
								<span class="list-meta">
									<span>{f.title_count} title{f.title_count === 1 ? '' : 's'}</span>
								</span>
							</a>
						</li>
					{/each}
				</ul>
			</section>
		{/if}

		{#if !anyLoading && totalResults === 0}
			<p class="no-results">No results found for "{searchQuery.trim()}"</p>
		{/if}
	{/if}
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

	.hint {
		text-align: center;
		color: var(--color-text-muted);
		font-size: var(--font-size-1);
		margin-top: var(--size-2);
	}

	.results-summary {
		text-align: center;
		margin-bottom: var(--size-4);
	}

	.count {
		color: var(--color-text-muted);
		font-size: var(--font-size-1);
	}

	.result-group {
		margin-bottom: var(--size-6);
	}

	.result-group h2 {
		font-size: var(--font-size-4);
		font-weight: 600;
		color: var(--color-text-primary);
		margin-bottom: var(--size-3);
		display: flex;
		align-items: baseline;
		gap: var(--size-2);
	}

	.group-count {
		font-size: var(--font-size-1);
		font-weight: 400;
		color: var(--color-text-muted);
	}

	.see-all {
		display: block;
		margin: var(--size-3) auto 0;
		padding: var(--size-2) var(--size-4);
		background: none;
		border: 1px solid var(--color-border-soft);
		border-radius: var(--radius-2);
		color: var(--color-accent);
		font-size: var(--font-size-1);
		cursor: pointer;
		transition:
			background-color 0.15s ease,
			border-color 0.15s ease;
	}

	.see-all:hover {
		background-color: var(--color-surface);
		border-color: var(--color-accent);
	}

	.list-rows {
		list-style: none;
		padding: 0;
		max-width: 48rem;
	}

	.list-row {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		padding: var(--size-3) 0;
		border-bottom: 1px solid var(--color-border-soft);
		text-decoration: none;
		color: inherit;
		gap: var(--size-4);
	}

	.list-row:hover .list-name {
		color: var(--color-accent);
	}

	.list-name {
		font-size: var(--font-size-2);
		color: var(--color-text-primary);
		font-weight: 500;
	}

	.list-meta {
		display: flex;
		gap: var(--size-4);
		flex-shrink: 0;
		font-size: var(--font-size-1);
		color: var(--color-text-muted);
	}

	.no-results {
		text-align: center;
		color: var(--color-text-muted);
		font-size: var(--font-size-2);
		padding: var(--size-8) 0;
	}
</style>
