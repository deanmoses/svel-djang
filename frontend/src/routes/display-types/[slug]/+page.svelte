<script lang="ts">
	import client from '$lib/api/client';
	import { createPaginatedLoader } from '$lib/paginated-loader.svelte';
	import EntityDetailLayout from '$lib/components/EntityDetailLayout.svelte';
	import PaginatedSection from '$lib/components/grid/PaginatedSection.svelte';
	import TitleCard from '$lib/components/cards/TitleCard.svelte';

	let { data } = $props();
	let profile = $derived(data.profile);

	const titles = createPaginatedLoader(async (page) => {
		const { data: result } = await client.GET('/api/titles/', {
			params: { query: { display: profile.slug, page } }
		});
		return result ?? { items: [], count: 0 };
	});
</script>

<EntityDetailLayout
	name={profile.name}
	description={profile.description}
	breadcrumbs={[{ label: 'Display Types', href: '/display-types' }]}
>
	<PaginatedSection
		loader={titles}
		heading="Titles"
		emptyMessage="No titles with this display type."
	>
		{#snippet children(title)}
			<TitleCard
				slug={title.slug}
				name={title.name}
				thumbnailUrl={title.thumbnail_url}
				manufacturerName={title.manufacturer_name}
				year={title.year}
			/>
		{/snippet}
	</PaginatedSection>
</EntityDetailLayout>
