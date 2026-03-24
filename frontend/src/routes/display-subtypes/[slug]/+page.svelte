<script lang="ts">
	import client from '$lib/api/client';
	import { createPaginatedLoader } from '$lib/paginated-loader.svelte';
	import EntityDetailLayout from '$lib/components/EntityDetailLayout.svelte';
	import PaginatedSection from '$lib/components/grid/PaginatedSection.svelte';
	import MachineCard from '$lib/components/cards/MachineCard.svelte';

	let { data } = $props();
	let profile = $derived(data.profile);

	const machines = createPaginatedLoader(async (page) => {
		const { data: result } = await client.GET('/api/models/', {
			params: { query: { display_subtype: profile.slug, page } }
		});
		return result ?? { items: [], count: 0 };
	});
</script>

<EntityDetailLayout name={profile.name} description={profile.description}>
	<PaginatedSection
		loader={machines}
		heading="Machines"
		emptyMessage="No machines with this display subtype."
	>
		{#snippet children(machine)}
			<MachineCard
				slug={machine.slug}
				name={machine.name}
				thumbnailUrl={machine.thumbnail_url}
				manufacturerName={machine.manufacturer_name}
				year={machine.year}
			/>
		{/snippet}
	</PaginatedSection>
</EntityDetailLayout>
