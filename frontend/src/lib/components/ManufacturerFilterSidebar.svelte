<script lang="ts">
	import ChipGroup from './ChipGroup.svelte';
	import SearchableSelect from './SearchableSelect.svelte';
	import YearRangeInput from './YearRangeInput.svelte';
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

	<div class="filter-section">
		<span class="filter-label">Year</span>
		<YearRangeInput bind:min={filters.yearMin} bind:max={filters.yearMax} />
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
</style>
