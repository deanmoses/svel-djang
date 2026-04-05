<script lang="ts">
	import { resolve } from '$app/paths';
	import client from '$lib/api/client';
	import { createAsyncLoader } from '$lib/async-loader.svelte';
	import { pageTitle } from '$lib/constants';

	const allFeatures = createAsyncLoader(async () => {
		const { data } = await client.GET('/api/gameplay-features/');
		return data ?? [];
	}, []);
</script>

<svelte:head>
	<title>{pageTitle('Gameplay Features')}</title>
	<link rel="preload" as="fetch" href="/api/gameplay-features/" crossorigin="anonymous" />
</svelte:head>

<article>
	<header>
		<h1>Gameplay Features</h1>
		<p class="subtitle">Mechanical and digital features that define how a pinball machine plays.</p>
	</header>

	{#if allFeatures.loading}
		<p class="status">Loading...</p>
	{:else if allFeatures.error}
		<p class="status error">Failed to load gameplay features.</p>
	{:else if allFeatures.data.length === 0}
		<p class="status">No gameplay features found.</p>
	{:else}
		<ul class="feature-list">
			{#each allFeatures.data as feature (feature.slug)}
				<li>
					<a href={resolve(`/gameplay-features/${feature.slug}`)} class="feature-row">
						<span class="feature-name">{feature.name}</span>
						{#if feature.model_count > 0}
							<span class="model-count">{feature.model_count}</span>
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
		flex: 1;
	}

	.model-count {
		font-size: var(--font-size-0);
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
