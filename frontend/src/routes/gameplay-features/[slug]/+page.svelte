<script lang="ts">
	import client from '$lib/api/client';
	import { createPaginatedLoader } from '$lib/paginated-loader.svelte';
	import PaginatedSection from '$lib/components/grid/PaginatedSection.svelte';
	import MachineCard from '$lib/components/cards/MachineCard.svelte';

	let { data } = $props();
	let profile = $derived(data.profile);

	const machines = createPaginatedLoader(async (page) => {
		const { data: result } = await client.GET('/api/models/', {
			params: { query: { feature: profile.slug, page } }
		});
		return result ?? { items: [], count: 0 };
	});
</script>

<PaginatedSection
	loader={machines}
	heading="Machines"
	emptyMessage="No machines with this feature."
>
	{#snippet children(machine)}
		<MachineCard
			slug={machine.slug}
			name={machine.name}
			thumbnailUrl={machine.thumbnail_url}
			manufacturerName={machine.manufacturer?.name}
			year={machine.year}
		/>
	{/snippet}
</PaginatedSection>
