<script lang="ts">
	import TitleCard from '$lib/components/cards/TitleCard.svelte';
	import CardGrid from '$lib/components/grid/CardGrid.svelte';

	type Title = {
		slug: string;
		name: string;
		thumbnail_url?: string | null;
		manufacturer_name?: string | null;
		year?: number | null;
	};

	let {
		titles,
		emptyMessage
	}: {
		titles: Title[];
		emptyMessage: string;
	} = $props();
</script>

<section class="titles">
	<h2>Titles ({titles.length})</h2>
	{#if titles.length === 0}
		<p class="empty">{emptyMessage}</p>
	{:else}
		<CardGrid>
			{#each titles as title (title.slug)}
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
