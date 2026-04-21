<script lang="ts">
	import client from '$lib/api/client';
	import { createAsyncLoader } from '$lib/async-loader.svelte';
	import TaxonomyListPage from '$lib/components/TaxonomyListPage.svelte';

	const loader = createAsyncLoader(async () => {
		const { data } = await client.GET('/api/series/');
		return data ?? [];
	}, []);
</script>

{#snippet row(s: (typeof loader.data)[number])}
	<span class="series-name">{s.name}</span>
	<span class="series-count">{s.title_count} title{s.title_count === 1 ? '' : 's'}</span>
{/snippet}

<TaxonomyListPage
	catalogKey="series"
	subtitle="Curated groups of related pinball titles sharing a franchise lineage."
	items={loader.data}
	loading={loader.loading}
	error={loader.error}
	rowSnippet={row}
	rowStyle="justify-content: space-between; gap: var(--size-4)"
	canCreate
/>

<style>
	.series-name {
		font-size: var(--font-size-2);
		font-weight: 500;
		color: inherit;
	}

	.series-count {
		font-size: var(--font-size-1);
		color: var(--color-text-muted);
		flex-shrink: 0;
	}
</style>
