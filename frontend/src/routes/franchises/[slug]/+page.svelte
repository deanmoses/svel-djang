<script lang="ts">
	import AttributionLine from '$lib/components/AttributionLine.svelte';
	import Markdown from '$lib/components/Markdown.svelte';
	import TitleCard from '$lib/components/cards/TitleCard.svelte';
	import CardGrid from '$lib/components/grid/CardGrid.svelte';

	let { data } = $props();
	let franchise = $derived(data.franchise);
</script>

{#if franchise.description?.html}
	<section class="description">
		<Markdown html={franchise.description.html} citations={franchise.description.citations ?? []} />
		<AttributionLine attribution={franchise.description.attribution} />
	</section>
{/if}

<section>
	<h2>Titles ({franchise.titles.length})</h2>
	{#if franchise.titles.length === 0}
		<p class="empty">No titles in this franchise.</p>
	{:else}
		<CardGrid>
			{#each franchise.titles as title (title.slug)}
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

<style>
	.description {
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
