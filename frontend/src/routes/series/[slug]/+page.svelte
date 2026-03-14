<script lang="ts">
	import CardGrid from '$lib/components/grid/CardGrid.svelte';
	import Markdown from '$lib/components/Markdown.svelte';
	import TitleCard from '$lib/components/cards/TitleCard.svelte';
	import CreditsList from '$lib/components/CreditsList.svelte';
	import { pageTitle } from '$lib/constants';

	let { data } = $props();
	let series = $derived(data.series);
</script>

<svelte:head>
	<title>{pageTitle(series.name)}</title>
</svelte:head>

<article>
	<header>
		<h1>{series.name}</h1>
		{#if series.description_html}
			<Markdown html={series.description_html} />
		{/if}
	</header>

	{#if series.titles.length === 0}
		<p class="empty">No titles in this series.</p>
	{:else}
		<section>
			<h2>Titles ({series.titles.length})</h2>
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
		</section>
	{/if}

	<CreditsList credits={series.credits} />
</article>

<style>
	article {
		max-width: 64rem;
	}

	header {
		margin-bottom: var(--size-6);
	}

	h1 {
		font-size: var(--font-size-7);
		font-weight: 700;
		color: var(--color-text-primary);
		margin-bottom: var(--size-2);
	}

	h2 {
		font-size: var(--font-size-3);
		font-weight: 600;
		color: var(--color-text-primary);
		margin-bottom: var(--size-3);
	}

	.empty {
		color: var(--color-text-muted);
		font-size: var(--font-size-2);
		padding: var(--size-8) 0;
		text-align: center;
	}
</style>
