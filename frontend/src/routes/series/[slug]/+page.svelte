<script lang="ts">
	import EntityDetailLayout from '$lib/components/EntityDetailLayout.svelte';
	import ClientFilteredGrid from '$lib/components/grid/ClientFilteredGrid.svelte';
	import TitleCard from '$lib/components/cards/TitleCard.svelte';
	import CreditsList from '$lib/components/CreditsList.svelte';

	let { data } = $props();
	let series = $derived(data.series);
</script>

<EntityDetailLayout
	name={series.name}
	descriptionHtml={series.description_html}
	breadcrumbs={[{ label: 'Series', href: '/series' }]}
>
	{#if series.titles.length === 0}
		<p class="empty">No titles in this series.</p>
	{:else}
		<section>
			<h2>Titles ({series.titles.length})</h2>
			<ClientFilteredGrid items={series.titles} showCount={false}>
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

	<CreditsList credits={series.credits} />
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
