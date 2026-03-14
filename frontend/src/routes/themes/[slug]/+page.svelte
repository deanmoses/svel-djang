<script lang="ts">
	import EntityDetailLayout from '$lib/components/EntityDetailLayout.svelte';
	import ClientFilteredGrid from '$lib/components/grid/ClientFilteredGrid.svelte';
	import MachineCard from '$lib/components/cards/MachineCard.svelte';

	let { data } = $props();
	let theme = $derived(data.theme);
</script>

<EntityDetailLayout
	name={theme.name}
	descriptionHtml={theme.description_html}
	breadcrumbs={[{ label: 'Themes', href: '/themes' }]}
>
	{#if theme.machines.length === 0}
		<p class="empty">No machines with this theme.</p>
	{:else}
		<section>
			<h2>Machines ({theme.machines.length})</h2>
			<ClientFilteredGrid items={theme.machines} showCount={false}>
				{#snippet children(machine)}
					<MachineCard
						slug={machine.slug}
						name={machine.name}
						thumbnailUrl={machine.thumbnail_url}
						manufacturerName={machine.manufacturer_name}
						year={machine.year}
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
