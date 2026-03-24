<script lang="ts">
	import EntityDetailLayout from '$lib/components/EntityDetailLayout.svelte';
	import ClientFilteredGrid from '$lib/components/grid/ClientFilteredGrid.svelte';
	import TitleCard from '$lib/components/cards/TitleCard.svelte';

	let { data } = $props();
	let franchise = $derived(data.franchise);
</script>

<EntityDetailLayout
	name={franchise.name}
	description={franchise.description}
	breadcrumbs={[{ label: 'Franchises', href: '/franchises' }]}
>
	{#if franchise.titles.length === 0}
		<p class="empty">No titles in this franchise.</p>
	{:else}
		<section>
			<h2>Titles ({franchise.titles.length})</h2>
			<ClientFilteredGrid items={franchise.titles} showCount={false}>
				{#snippet children(title)}
					<TitleCard
						slug={title.slug}
						name={title.name}
						thumbnailUrl={title.thumbnail_url}
						manufacturerName={title.manufacturer_name}
						year={title.year}
					/>
				{/snippet}
			</ClientFilteredGrid>
		</section>
	{/if}
</EntityDetailLayout>

<style>
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
