<script lang="ts">
	import { resolve } from '$app/paths';
	import CardGrid from '$lib/components/grid/CardGrid.svelte';
	import MachineCard from '$lib/components/cards/MachineCard.svelte';
	import { pageTitle } from '$lib/constants';

	let { data } = $props();
	let title = $derived(data.title);
</script>

<svelte:head>
	<title>{pageTitle(title.name)}</title>
</svelte:head>

<article>
	<header>
		<h1>{title.name}</h1>
		{#if title.short_name && title.short_name !== title.name}
			<p class="short_name">{title.short_name}</p>
		{/if}
		{#if title.series.length > 0}
			<p class="series-list">
				Series:
				{#each title.series as s, i (s.slug)}
					{#if i > 0},{/if}
					<a href={resolve(`/series/${s.slug}`)}>{s.name}</a>
				{/each}
			</p>
		{/if}
	</header>

	{#if title.machines.length === 0}
		<p class="empty">No machines in this title.</p>
	{:else}
		<section>
			<h2>Machines ({title.machines.length})</h2>
			<CardGrid>
				{#each title.machines as machine (machine.slug)}
					<MachineCard
						slug={machine.slug}
						name={machine.name}
						thumbnailUrl={machine.thumbnail_url}
						manufacturerName={machine.manufacturer_name}
						year={machine.year}
						machineType={machine.technology_generation_name}
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

	.short_name {
		font-size: var(--font-size-2);
		color: var(--color-text-muted);
	}

	.series-list {
		font-size: var(--font-size-1);
		color: var(--color-text-muted);
		margin-top: var(--size-1);
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
