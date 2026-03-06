<script lang="ts">
	import CardGrid from '$lib/components/grid/CardGrid.svelte';
	import MachineCard from '$lib/components/cards/MachineCard.svelte';
	import { pageTitle } from '$lib/constants';

	let { data } = $props();
	let theme = $derived(data.theme);
</script>

<svelte:head>
	<title>{pageTitle(theme.name)}</title>
</svelte:head>

<article>
	<header>
		<h1>{theme.name}</h1>
		{#if theme.description}
			<p class="description">{theme.description}</p>
		{/if}
	</header>

	{#if theme.machines.length === 0}
		<p class="empty">No machines with this theme.</p>
	{:else}
		<section>
			<h2>Machines ({theme.machines.length})</h2>
			<CardGrid>
				{#each theme.machines as machine (machine.slug)}
					<MachineCard
						slug={machine.slug}
						name={machine.name}
						thumbnailUrl={machine.thumbnail_url}
						manufacturerName={machine.manufacturer_name}
						year={machine.year}
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
