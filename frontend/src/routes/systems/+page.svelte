<script lang="ts">
	import client from '$lib/api/client';
	import { createAsyncLoader } from '$lib/async-loader.svelte';
	import TaxonomyListPage from '$lib/components/TaxonomyListPage.svelte';
	import type { components } from '$lib/api/schema';

	type SystemRow = components['schemas']['SystemListSchema'];

	const systems = createAsyncLoader(async () => {
		const { data } = await client.GET('/api/systems/all/');
		return data ?? [];
	}, []);

	let manufacturerFilter = $state<string>('');

	let manufacturerOptions = $derived.by(() => {
		const seen: Record<string, string> = {};
		for (const s of systems.data) {
			if (s.manufacturer && !(s.manufacturer.slug in seen)) {
				seen[s.manufacturer.slug] = s.manufacturer.name;
			}
		}
		return Object.entries(seen)
			.map(([slug, name]) => ({ slug, name }))
			.sort((a, b) => a.name.localeCompare(b.name));
	});

	function filterByManufacturer(s: SystemRow): boolean {
		if (!manufacturerFilter) return true;
		return s.manufacturer?.slug === manufacturerFilter;
	}
</script>

<svelte:head>
	<link rel="preload" as="fetch" href="/api/systems/all/" crossorigin="anonymous" />
</svelte:head>

<TaxonomyListPage
	catalogKey="system"
	items={systems.data}
	loading={systems.loading}
	error={systems.error}
	canCreate
	filterFn={filterByManufacturer}
	rowStyle="display: flex; justify-content: space-between; gap: var(--size-4);"
>
	{#snippet filters()}
		{#if manufacturerOptions.length > 1}
			<div class="mfr-filter">
				<label for="mfr-filter-select">Manufacturer</label>
				<select id="mfr-filter-select" bind:value={manufacturerFilter}>
					<option value="">All manufacturers</option>
					{#each manufacturerOptions as opt (opt.slug)}
						<option value={opt.slug}>{opt.name}</option>
					{/each}
				</select>
			</div>
		{/if}
	{/snippet}

	{#snippet rowSnippet(system)}
		<span class="system-name">{system.name}</span>
		<span class="system-meta">
			{#if system.manufacturer}
				<span class="manufacturer">{system.manufacturer.name}</span>
			{/if}
			<span class="count">
				{system.machine_count} machine{system.machine_count === 1 ? '' : 's'}
			</span>
		</span>
	{/snippet}
</TaxonomyListPage>

<style>
	.mfr-filter {
		display: flex;
		align-items: baseline;
		gap: var(--size-2);
		padding: var(--size-2) 0 var(--size-3);
	}

	.mfr-filter label {
		font-size: var(--font-size-1);
		color: var(--color-text-muted);
	}

	.mfr-filter select {
		font: inherit;
		padding: var(--size-1) var(--size-2);
	}

	.system-name {
		font-size: var(--font-size-2);
		color: var(--color-text-primary);
		font-weight: 500;
	}

	.system-meta {
		display: flex;
		gap: var(--size-4);
		flex-shrink: 0;
	}

	.manufacturer {
		font-size: var(--font-size-1);
		color: var(--color-text-muted);
	}

	.count {
		font-size: var(--font-size-1);
		color: var(--color-text-muted);
		min-width: 6rem;
		text-align: right;
	}
</style>
