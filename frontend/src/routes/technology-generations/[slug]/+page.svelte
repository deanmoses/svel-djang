<script lang="ts">
	import client from '$lib/api/client';
	import { createAsyncLoader } from '$lib/async-loader.svelte';
	import CardGrid from '$lib/components/grid/CardGrid.svelte';
	import MachineCard from '$lib/components/cards/MachineCard.svelte';
	import { pageTitle } from '$lib/constants';

	let { data } = $props();
	let profile = $derived(data.profile);

	const machines = createAsyncLoader(async () => {
		const { data: result } = await client.GET('/api/models/', {
			params: { query: { type: profile.slug, ordering: 'year', page_size: 500 } }
		});
		return result?.items ?? [];
	}, []);
</script>

<svelte:head>
	<title>{pageTitle(profile.name)}</title>
</svelte:head>

<article>
	<header>
		<h1>{profile.name}</h1>
		{#if profile.description}
			<div class="description">
				{#each profile.description.split('\n\n') as paragraph, i (i)}
					<p>{paragraph}</p>
				{/each}
			</div>
		{/if}
	</header>

	{#if machines.loading}
		<p class="empty">Loading machines…</p>
	{:else if machines.error}
		<p class="empty">Failed to load machines.</p>
	{:else if machines.data.length === 0}
		<p class="empty">No machines of this type.</p>
	{:else}
		<section>
			<h2>Machines ({machines.data.length})</h2>
			<CardGrid>
				{#each machines.data as machine (machine.slug)}
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
		margin-bottom: var(--size-4);
	}

	.description p {
		font-size: var(--font-size-2);
		color: var(--color-text-muted);
		line-height: var(--font-lineheight-3);
		margin-bottom: var(--size-3);
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
