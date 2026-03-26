<script lang="ts">
	import ClientFilteredGrid from '$lib/components/grid/ClientFilteredGrid.svelte';
	import MachineCard from '$lib/components/cards/MachineCard.svelte';

	let { data } = $props();
	let theme = $derived(data.theme);
</script>

{#if theme.machines.length === 0}
	<p class="empty">No machines with this theme.</p>
{:else}
	<ClientFilteredGrid items={theme.machines} showCount={false}>
		{#snippet children(machine)}
			<MachineCard
				slug={machine.slug}
				name={machine.name}
				thumbnailUrl={machine.thumbnail_url}
				manufacturerName={machine.manufacturer?.name}
				year={machine.year}
			/>
		{/snippet}
	</ClientFilteredGrid>
{/if}

<style>
	.empty {
		color: var(--color-text-muted);
		font-size: var(--font-size-2);
		padding: var(--size-8) 0;
		text-align: center;
	}
</style>
