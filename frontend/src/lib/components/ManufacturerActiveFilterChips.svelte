<script lang="ts">
	import {
		getMfrActiveFilterLabels,
		type FacetedManufacturer,
		type MfrActiveFilterLabel,
		type MfrFilterState
	} from '$lib/manufacturer-facet-engine';

	let {
		filters = $bindable(),
		allManufacturers
	}: {
		filters: MfrFilterState;
		allManufacturers: FacetedManufacturer[];
	} = $props();

	let activeLabels = $derived(getMfrActiveFilterLabels(filters, allManufacturers));

	function removeFilter(label: MfrActiveFilterLabel) {
		if (label.field === 'yearMin') {
			filters.yearMin = null;
			filters.yearMax = null;
		} else {
			(filters as unknown as Record<string, unknown>)[label.field] = null;
		}
	}
</script>

{#if activeLabels.length > 0}
	<div class="active-filters" role="list" aria-label="Active filters">
		{#each activeLabels as chip (chip.key)}
			<span class="filter-chip" role="listitem">
				{chip.label}
				<button
					class="chip-remove"
					aria-label="Remove filter: {chip.label}"
					onclick={() => removeFilter(chip)}
				>
					&times;
				</button>
			</span>
		{/each}
	</div>
{/if}

<style>
	.active-filters {
		display: flex;
		flex-wrap: wrap;
		gap: var(--size-1);
		margin-bottom: var(--size-3);
	}

	.filter-chip {
		display: inline-flex;
		align-items: center;
		gap: var(--size-1);
		padding: var(--size-1) var(--size-2);
		font-size: var(--font-size-0);
		background-color: var(--color-accent);
		color: white;
		border-radius: var(--radius-2);
	}

	.chip-remove {
		background: none;
		border: none;
		color: rgba(255, 255, 255, 0.8);
		cursor: pointer;
		padding: 0;
		font-size: var(--font-size-1);
		line-height: 1;
	}

	.chip-remove:hover {
		color: white;
	}
</style>
