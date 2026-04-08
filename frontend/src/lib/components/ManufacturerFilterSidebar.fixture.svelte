<script lang="ts">
	import ManufacturerFilterSidebar from './ManufacturerFilterSidebar.svelte';
	import { emptyMfrFilterState, type FacetedManufacturer } from '$lib/manufacturer-facet-engine';

	const MANUFACTURERS: FacetedManufacturer[] = [
		{
			name: 'Stern Pinball',
			slug: 'stern-pinball',
			model_count: 30,
			locations: [{ slug: 'usa', name: 'USA' }],
			year_min: 1977,
			year_max: 2024,
			persons: [{ slug: 'steve-ritchie', name: 'Steve Ritchie' }],
			tech_generations: [{ slug: 'solid-state', name: 'Solid State' }]
		},
		{
			name: 'Williams Electronics',
			slug: 'williams-electronics',
			model_count: 40,
			locations: [{ slug: 'usa', name: 'USA' }],
			year_min: 1967,
			year_max: 2000,
			persons: [{ slug: 'pat-lawlor', name: 'Pat Lawlor' }],
			tech_generations: [{ slug: 'solid-state', name: 'Solid State' }]
		},
		{
			name: 'Zaccaria',
			slug: 'zaccaria',
			model_count: 18,
			locations: [{ slug: 'italy', name: 'Italy' }],
			year_min: 1974,
			year_max: 1987,
			persons: [{ slug: 'renato-digioia', name: 'Renato Di Gioia' }],
			tech_generations: [{ slug: 'electromechanical', name: 'Electromechanical' }]
		}
	];

	let filters = $state(emptyMfrFilterState());
</script>

<ManufacturerFilterSidebar allManufacturers={MANUFACTURERS} bind:filters />
