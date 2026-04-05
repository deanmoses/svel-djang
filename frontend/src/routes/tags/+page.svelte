<script lang="ts">
	import { resolve } from '$app/paths';
	import client from '$lib/api/client';
	import { createAsyncLoader } from '$lib/async-loader.svelte';
	import { pageTitle } from '$lib/constants';

	const all = createAsyncLoader(async () => {
		const { data } = await client.GET('/api/tags/');
		return data ?? [];
	}, []);
</script>

<svelte:head>
	<title>{pageTitle('Tags')}</title>
	<link rel="preload" as="fetch" href="/api/tags/" crossorigin="anonymous" />
</svelte:head>

<article>
	<header>
		<h1>Tags</h1>
		<p class="subtitle">Descriptive tags applied to pinball machines.</p>
	</header>

	{#if all.loading}
		<p class="status">Loading...</p>
	{:else if all.error}
		<p class="status error">Failed to load tags.</p>
	{:else if all.data.length === 0}
		<p class="status">No tags found.</p>
	{:else}
		<ul class="feature-list">
			{#each all.data as item (item.slug)}
				<li>
					<a href={resolve(`/tags/${item.slug}`)} class="feature-row">
						<span class="feature-name">{item.name}</span>
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
