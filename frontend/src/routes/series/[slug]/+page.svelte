<script lang="ts">
	import AttributionLine from '$lib/components/AttributionLine.svelte';
	import CreditsList from '$lib/components/CreditsList.svelte';
	import Markdown from '$lib/components/Markdown.svelte';
	import TitleCard from '$lib/components/cards/TitleCard.svelte';
	import CardGrid from '$lib/components/grid/CardGrid.svelte';

	let { data } = $props();
	let series = $derived(data.series);
</script>

{#if series.description?.html}
	<section class="description">
		<Markdown html={series.description.html} citations={series.description.citations ?? []} />
		<AttributionLine attribution={series.description.attribution} />
	</section>
{/if}

<section class="titles">
	<h2>Titles ({series.titles.length})</h2>
	{#if series.titles.length === 0}
		<p class="empty">No titles in this series.</p>
	{:else}
		<CardGrid>
			{#each series.titles as title (title.slug)}
				<TitleCard
					slug={title.slug}
					name={title.name}
					thumbnailUrl={title.thumbnail_url}
					manufacturerName={title.manufacturer_name}
					year={title.year}
				/>
			{/each}
		</CardGrid>
	{/if}
</section>

<CreditsList credits={series.credits} />

<style>
	.description {
		margin-bottom: var(--size-6);
	}

	.titles {
		margin-bottom: var(--size-6);
	}

	h2 {
		font-size: var(--font-size-3);
		font-weight: 600;
		color: var(--color-text-primary);
		margin-bottom: var(--size-3);
	}

	.empty {
		color: var(--color-text-muted);
		font-size: var(--font-size-1);
		margin: 0;
	}
</style>
