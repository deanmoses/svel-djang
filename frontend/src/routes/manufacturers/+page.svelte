<script lang="ts">
	import client from '$lib/api/client';
	import { createAsyncLoader } from '$lib/async-loader.svelte';
	import SearchableGrid from '$lib/components/grid/SearchableGrid.svelte';
	import ManufacturerCard from '$lib/components/cards/ManufacturerCard.svelte';
	import { pageTitle } from '$lib/constants';

	const manufacturers = createAsyncLoader(async () => {
		const { data } = await client.GET('/api/manufacturers/all/');
		return data ?? [];
	}, []);
</script>

<svelte:head>
	<title>{pageTitle('Manufacturers')}</title>
	<link rel="preload" as="fetch" href="/api/manufacturers/all/" crossorigin="anonymous" />
</svelte:head>

<SearchableGrid
	items={manufacturers.data}
	loading={manufacturers.loading}
	error={manufacturers.error}
	filterFields={(item) => [item.name]}
	placeholder="Search manufacturers..."
	entityName="manufacturer"
>
	{#snippet children(mfr)}
		<ManufacturerCard
			slug={mfr.slug}
			name={mfr.name}
			thumbnailUrl={mfr.thumbnail_url}
			modelCount={mfr.model_count}
		/>
	{/snippet}
</SearchableGrid>
