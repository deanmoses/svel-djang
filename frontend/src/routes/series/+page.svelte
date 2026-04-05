<script lang="ts">
	import { resolve } from '$app/paths';
	import client from '$lib/api/client';
	import { createAsyncLoader } from '$lib/async-loader.svelte';
	import { pageTitle } from '$lib/constants';

	const allSeries = createAsyncLoader(async () => {
		const { data } = await client.GET('/api/series/');
		return data ?? [];
	}, []);
</script>

<svelte:head>
	<title>{pageTitle('Series')}</title>
	<link rel="preload" as="fetch" href="/api/series/" crossorigin="anonymous" />
</svelte:head>

<article>
	<header>
		<h1>Series</h1>
		<p class="subtitle">Curated groups of related pinball titles sharing a franchise lineage.</p>
	</header>

	{#if allSeries.loading}
		<p class="status">Loading...</p>
	{:else if allSeries.error}
		<p class="status error">Failed to load series.</p>
	{:else if allSeries.data.length === 0}
		<p class="status">No series found.</p>
	{:else}
		<ul class="series-list">
			{#each allSeries.data as s (s.slug)}
				<li>
					<a href={resolve(`/series/${s.slug}`)} class="series-row">
						<span class="series-name">{s.name}</span>
						<span class="series-count">{s.title_count} title{s.title_count === 1 ? '' : 's'}</span>
					</a>
				</li>
			{/each}
		</ul>
	{/if}
</article>

<style>
	article {
		max-width: 48rem;
	}

	header {
		margin-bottom: var(--size-6);
	}

	h1 {
		font-size: var(--font-size-7);
		font-weight: 700;
		color: var(--color-text-primary);
	}

	.subtitle {
		font-size: var(--font-size-2);
		color: var(--color-text-muted);
		margin-top: var(--size-2);
	}

	.series-list {
		list-style: none;
		padding: 0;
	}

	.series-row {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		padding: var(--size-3) 0;
		border-bottom: 1px solid var(--color-border-soft);
		text-decoration: none;
		color: inherit;
		gap: var(--size-4);
	}

	.series-row:hover .series-name {
		color: var(--color-accent);
	}

	.series-name {
		font-size: var(--font-size-2);
		color: var(--color-text-primary);
		font-weight: 500;
	}

	.series-count {
		font-size: var(--font-size-1);
		color: var(--color-text-muted);
		flex-shrink: 0;
	}

	.status {
		font-size: var(--font-size-2);
		color: var(--color-text-muted);
		padding: var(--size-8) 0;
		text-align: center;
	}

	.status.error {
		color: var(--color-error);
	}
</style>
