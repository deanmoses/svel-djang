<script lang="ts">
	import ChipGroup from './ChipGroup.svelte';
	import SearchableSelect from './SearchableSelect.svelte';
	import { buildFacetRefOptions } from '$lib/facet-engine';
	import {
		computeMfrFacetCounts,
		emptyMfrFilterState,
		type FacetedManufacturer,
		type MfrFilterState
	} from '$lib/manufacturer-facet-engine';

	let {
		allManufacturers,
		filters = $bindable()
	}: {
		allManufacturers: FacetedManufacturer[];
		filters: MfrFilterState;
	} = $props();

	// -----------------------------------------------------------------------
	// Facet counts (N-1 approach)
	// -----------------------------------------------------------------------
	let facetCounts = $derived(computeMfrFacetCounts(allManufacturers, filters));

	// -----------------------------------------------------------------------
	// Option lists (unique values enriched with live counts)
	// -----------------------------------------------------------------------
	let locationOptions = $derived(
		buildFacetRefOptions(allManufacturers, (m) => m.locations, facetCounts.location)
	);
	let personOptions = $derived(
		buildFacetRefOptions(allManufacturers, (m) => m.persons, facetCounts.person)
	);
	let techGenOptions = $derived(
		buildFacetRefOptions(allManufacturers, (m) => m.tech_generations, facetCounts.techGeneration)
	);

	// -----------------------------------------------------------------------
	// Active filter detection
	// -----------------------------------------------------------------------
	let hasActiveFilters = $derived(
		filters.location != null ||
			filters.yearMin != null ||
			filters.yearMax != null ||
			filters.person != null ||
			filters.techGeneration != null
	);

	function clearAll() {
		filters = emptyMfrFilterState();
	}
</script>

<aside class="sidebar">
	<div class="sidebar-header">
		<h2>Filters</h2>
		{#if hasActiveFilters}
			<button class="clear-all" onclick={clearAll}>Clear all</button>
		{/if}
	</div>

	<div class="filter-section">
		<SearchableSelect
			label="Location"
			options={locationOptions}
			bind:selected={filters.location}
			placeholder="Search locations..."
		/>
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
			label="Person"
			options={personOptions}
			bind:selected={filters.person}
			placeholder="Search people..."
		/>
	</div>

	<div class="filter-section">
		<ChipGroup
			label="Tech generation"
			options={techGenOptions}
			bind:selected={filters.techGeneration}
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
</style>
