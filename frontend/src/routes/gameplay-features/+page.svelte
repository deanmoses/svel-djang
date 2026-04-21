<script lang="ts">
	import client from '$lib/api/client';
	import { createAsyncLoader } from '$lib/async-loader.svelte';
	import TaxonomyListPage from '$lib/components/TaxonomyListPage.svelte';

	const loader = createAsyncLoader(async () => {
		const { data } = await client.GET('/api/gameplay-features/');
		return data ?? [];
	}, []);
</script>

{#snippet row(feature: (typeof loader.data)[number])}
	<span class="feature-name">{feature.name}</span>
	{#if feature.model_count > 0}
		<span class="model-count">{feature.model_count}</span>
	{/if}
{/snippet}

<TaxonomyListPage
	catalogKey="gameplay-feature"
	subtitle="Mechanical and digital features that define how a pinball machine plays."
	items={loader.data}
	loading={loader.loading}
	error={loader.error}
	rowSnippet={row}
	canCreate
/>

<style>
	.feature-name {
		font-size: var(--font-size-2);
		font-weight: 500;
		color: inherit;
		flex: 1;
	}

	.model-count {
		font-size: var(--font-size-0);
		color: var(--color-text-muted);
	}
</style>
