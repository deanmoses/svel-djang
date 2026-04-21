<script lang="ts">
	import TaxonomyListPage from './TaxonomyListPage.svelte';

	const items = [
		{ slug: 'alpha', name: 'Alpha', count: 42 },
		{ slug: 'beta', name: 'Beta', count: 0 }
	];
</script>

{#snippet row(item: (typeof items)[number])}
	<span class="custom-name">{item.name}</span>
	{#if item.count > 0}
		<span class="custom-count">{item.count}</span>
	{/if}
{/snippet}

<TaxonomyListPage
	catalogKey="tag"
	subtitle="All the tags."
	{items}
	loading={false}
	error={null}
	rowSnippet={row}
/>
