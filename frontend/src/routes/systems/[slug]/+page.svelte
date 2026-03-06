<script lang="ts">
	import { resolve } from '$app/paths';
	import CardGrid from '$lib/components/grid/CardGrid.svelte';
	import TitleCard from '$lib/components/cards/TitleCard.svelte';
	import { pageTitle } from '$lib/constants';

	let { data } = $props();
	let system = $derived(data.system);
</script>

<svelte:head>
	<title>{pageTitle(system.name)}</title>
</svelte:head>

<article>
	<header>
		<h1>{system.name}</h1>
		{#if system.manufacturer_name}
			<p class="manufacturer">
				By <a href={resolve(`/manufacturers/${system.manufacturer_slug}`)}
					>{system.manufacturer_name}</a
				>
			</p>
		{/if}
		{#if system.description}
			<p class="description">{system.description}</p>
		{/if}
	</header>

	{#if system.titles.length === 0}
		<p class="empty">No titles on this system.</p>
	{:else}
		<section>
			<h2>Titles ({system.titles.length})</h2>
			<CardGrid>
				{#each system.titles as title (title.slug)}
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

	.manufacturer {
		font-size: var(--font-size-2);
		color: var(--color-text-muted);
		margin-bottom: var(--size-2);
	}

	.description {
		font-size: var(--font-size-2);
		color: var(--color-text-muted);
		line-height: var(--font-lineheight-3);
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
