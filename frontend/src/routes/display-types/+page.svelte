<script lang="ts">
	import { resolve } from '$app/paths';
	import client from '$lib/api/client';
	import { createAsyncLoader } from '$lib/async-loader.svelte';
	import { pageTitle } from '$lib/constants';

	const allDisplayTypes = createAsyncLoader(async () => {
		const { data } = await client.GET('/api/display-types/');
		return data ?? [];
	}, []);
</script>

<svelte:head>
	<title>{pageTitle('Display Types')}</title>
	<link rel="preload" as="fetch" href="/api/display-types/" crossorigin="anonymous" />
</svelte:head>

<article>
	<header>
		<h1>Display Types</h1>
		<p class="subtitle">Score display technologies used in pinball machines.</p>
	</header>

	{#if allDisplayTypes.loading}
		<p class="status">Loading...</p>
	{:else if allDisplayTypes.error}
		<p class="status error">Failed to load display types.</p>
	{:else if allDisplayTypes.data.length === 0}
		<p class="status">No display types found.</p>
	{:else}
		<ul class="feature-list">
			{#each allDisplayTypes.data as displayType (displayType.slug)}
				<li>
					<a href={resolve(`/display-types/${displayType.slug}`)} class="feature-row">
						<span class="feature-name">{displayType.name}</span>
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
