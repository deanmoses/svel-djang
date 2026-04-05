<script lang="ts">
	import { resolve } from '$app/paths';
	import client from '$lib/api/client';
	import { createAsyncLoader } from '$lib/async-loader.svelte';
	import { pageTitle } from '$lib/constants';

	const allFranchises = createAsyncLoader(async () => {
		const { data } = await client.GET('/api/franchises/all/');
		return data ?? [];
	}, []);
</script>

<svelte:head>
	<title>{pageTitle('Franchises')}</title>
	<link rel="preload" as="fetch" href="/api/franchises/all/" crossorigin="anonymous" />
</svelte:head>

<article>
	<header>
		<h1>Franchises</h1>
		<p class="subtitle">Licensed and original franchises featured in pinball.</p>
	</header>

	{#if allFranchises.loading}
		<p class="status">Loading...</p>
	{:else if allFranchises.error}
		<p class="status error">Failed to load franchises.</p>
	{:else if allFranchises.data.length === 0}
		<p class="status">No franchises found.</p>
	{:else}
		<ul class="feature-list">
			{#each allFranchises.data as franchise (franchise.slug)}
				<li>
					<a href={resolve(`/franchises/${franchise.slug}`)} class="feature-row">
						<span class="feature-name">{franchise.name}</span>
						{#if franchise.title_count}
							<span class="feature-count">{franchise.title_count}</span>
						{/if}
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

	.feature-list {
		list-style: none;
		padding: 0;
	}

	.feature-row {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		padding: var(--size-3) 0;
		border-bottom: 1px solid var(--color-border-soft);
		text-decoration: none;
		color: inherit;
	}

	.feature-row:hover .feature-name {
		color: var(--color-accent);
	}

	.feature-name {
		font-size: var(--font-size-2);
		color: var(--color-text-primary);
		font-weight: 500;
	}

	.feature-count {
		font-size: var(--font-size-1);
		color: var(--color-text-muted);
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
