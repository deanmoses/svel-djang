<script lang="ts">
	import ChipGroup from './ChipGroup.svelte';
	import SearchableSelect from './SearchableSelect.svelte';
	import {
		buildFacetRefOptions,
		buildPlayerCountOptions,
		buildSingleRefOptions,
		computeFacetCounts,
		emptyFilterState,
		type FacetedTitle,
		type FilterState
	} from '$lib/facet-engine';

	let {
		allTitles,
		filters = $bindable()
	}: {
		allTitles: FacetedTitle[];
		filters: FilterState;
	} = $props();

	// -----------------------------------------------------------------------
	// Facet counts (N-1 approach)
	// -----------------------------------------------------------------------
	let facetCounts = $derived(computeFacetCounts(allTitles, filters));

	// -----------------------------------------------------------------------
	// Option lists (unique values enriched with live counts)
	// -----------------------------------------------------------------------
	let techGenOptions = $derived(
		buildFacetRefOptions(allTitles, (t) => t.tech_generations, facetCounts.techGeneration)
	);
	let displayTypeOptions = $derived(
		buildFacetRefOptions(allTitles, (t) => t.display_types, facetCounts.displayType)
	);
	let manufacturerOptions = $derived(
		buildSingleRefOptions(
			allTitles,
			(t) =>
				t.manufacturer_slug && t.manufacturer_name
					? { slug: t.manufacturer_slug, name: t.manufacturer_name }
					: null,
			facetCounts.manufacturer
		)
	);
	let personOptions = $derived(
		buildFacetRefOptions(allTitles, (t) => t.persons, facetCounts.person)
	);
	let themeOptions = $derived(buildFacetRefOptions(allTitles, (t) => t.themes, facetCounts.theme));
	let systemOptions = $derived(
		buildFacetRefOptions(allTitles, (t) => t.systems, facetCounts.system)
	);
	let franchiseOptions = $derived(
		buildSingleRefOptions(allTitles, (t) => t.franchise, facetCounts.franchise)
	);
	let seriesOptions = $derived(
		buildFacetRefOptions(allTitles, (t) => t.series, facetCounts.series)
	);
	let playerCountOptions = $derived(buildPlayerCountOptions(facetCounts.playerCount));

	// Player count adaptor: ChipGroup works with string slugs, filters.playerCount is number|null
	let playerCountChipOptions = $derived(
		playerCountOptions.map((o) => ({ slug: String(o.value), label: o.label, count: o.count }))
	);
	let playerCountSlug = $derived(filters.playerCount != null ? String(filters.playerCount) : null);

	function setPlayerCount(slug: string | null) {
		filters.playerCount = slug ? Number(slug) : null;
	}

	// -----------------------------------------------------------------------
	// Active filter detection
	// -----------------------------------------------------------------------
	let hasActiveFilters = $derived(
		filters.techGeneration != null ||
			filters.yearMin != null ||
			filters.yearMax != null ||
			filters.manufacturer != null ||
			filters.person != null ||
			filters.themes.length > 0 ||
			filters.displayType != null ||
			filters.playerCount != null ||
			filters.system != null ||
			filters.franchise != null ||
			filters.series != null ||
			filters.ratingMin != null
	);

	function clearAll() {
		filters = emptyFilterState();
	}
</script>

<aside class="sidebar">
	<div class="sidebar-header">
		<h2>Filters</h2>
		{#if hasActiveFilters}
			<button class="clear-all" onclick={clearAll}>Clear all</button>
		{/if}
	</div>

	<div class="filter-section year-range">
		<span class="filter-label">Year</span>
		<div class="year-inputs">
			<input
				type="number"
				placeholder="From"
				aria-label="Year from"
				value={filters.yearMin ?? ''}
				onchange={(e) => {
					const v = e.currentTarget.value;
					filters.yearMin = v ? Number(v) : null;
				}}
			/>
			<span class="year-sep">&ndash;</span>
			<input
				type="number"
				placeholder="To"
				aria-label="Year to"
				value={filters.yearMax ?? ''}
				onchange={(e) => {
					const v = e.currentTarget.value;
					filters.yearMax = v ? Number(v) : null;
				}}
			/>
		</div>
	</div>

	<div class="filter-section">
		<SearchableSelect
			label="Manufacturer"
			options={manufacturerOptions}
			bind:selected={filters.manufacturer}
			placeholder="Search manufacturers..."
		/>
	</div>

	<div class="filter-section">
		<SearchableSelect
			label="Person"
			options={personOptions}
			bind:selected={filters.person}
			placeholder="Search people..."
		/>
	</div>

	<div class="filter-section">
		<SearchableSelect
			label="Theme"
			options={themeOptions}
			bind:selected={filters.themes}
			multi
			placeholder="Search themes..."
		/>
	</div>

	<div class="filter-section">
		<ChipGroup
			label="Tech generation"
			options={techGenOptions}
			bind:selected={filters.techGeneration}
		/>
	</div>

	<div class="filter-section">
		<ChipGroup
			label="Display type"
			options={displayTypeOptions}
			bind:selected={filters.displayType}
		/>
	</div>

	<div class="filter-section">
		<ChipGroup
			label="Player count"
			options={playerCountChipOptions}
			selected={playerCountSlug}
			onchange={setPlayerCount}
		/>
	</div>

	<div class="filter-section">
		<SearchableSelect
			label="System"
			options={systemOptions}
			bind:selected={filters.system}
			placeholder="Search systems..."
		/>
	</div>

	<div class="filter-section">
		<SearchableSelect
			label="Franchise"
			options={franchiseOptions}
			bind:selected={filters.franchise}
			placeholder="Search franchises..."
		/>
	</div>

	<div class="filter-section">
		<SearchableSelect
			label="Series"
			options={seriesOptions}
			bind:selected={filters.series}
			placeholder="Search series..."
		/>
	</div>

	<div class="filter-section">
		<span class="filter-label">Min IPDB rating</span>
		<input
			type="number"
			step="0.1"
			min="0"
			max="10"
			placeholder="e.g. 7.0"
			aria-label="Minimum IPDB rating"
			class="rating-input"
			value={filters.ratingMin ?? ''}
			onchange={(e) => {
				const v = e.currentTarget.value;
				filters.ratingMin = v ? Number(v) : null;
			}}
		/>
	</div>
</aside>

<style>
	.sidebar {
		display: flex;
		flex-direction: column;
		gap: var(--size-3);
	}

	.sidebar-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
	}

	.sidebar-header h2 {
		font-size: var(--font-size-2);
		margin: 0;
	}

	.clear-all {
		background: none;
		border: none;
		color: var(--color-accent);
		cursor: pointer;
		font-size: var(--font-size-0);
		font-family: var(--font-body);
		padding: 0;
	}

	.clear-all:hover {
		text-decoration: underline;
	}

	.filter-section {
		display: flex;
		flex-direction: column;
		gap: var(--size-1);
	}

	.filter-label {
		font-size: var(--font-size-0);
		color: var(--color-text-muted);
	}

	.year-inputs {
		display: flex;
		align-items: center;
		gap: var(--size-2);
	}

	.year-inputs input {
		width: 5.5rem;
		padding: var(--size-2) var(--size-2);
		font-size: var(--font-size-1);
		font-family: var(--font-body);
		background-color: var(--color-input-bg);
		color: var(--color-text-primary);
		border: 1px solid var(--color-input-border);
		border-radius: var(--radius-2);
	}

	.year-inputs input:focus {
		outline: none;
		border-color: var(--color-input-focus);
		box-shadow: 0 0 0 3px var(--color-input-focus-ring);
	}

	.year-sep {
		color: var(--color-text-muted);
	}

	.rating-input {
		width: 6rem;
		padding: var(--size-2);
		font-size: var(--font-size-1);
		font-family: var(--font-body);
		background-color: var(--color-input-bg);
		color: var(--color-text-primary);
		border: 1px solid var(--color-input-border);
		border-radius: var(--radius-2);
	}

	.rating-input:focus {
		outline: none;
		border-color: var(--color-input-focus);
		box-shadow: 0 0 0 3px var(--color-input-focus-ring);
	}
</style>
