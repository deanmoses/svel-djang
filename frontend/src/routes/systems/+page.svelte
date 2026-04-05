<script lang="ts">
	import { resolve } from '$app/paths';
	import client from '$lib/api/client';
	import { createAsyncLoader } from '$lib/async-loader.svelte';
	import { pageTitle } from '$lib/constants';

	const systems = createAsyncLoader(async () => {
		const { data } = await client.GET('/api/systems/all/');
		return data ?? [];
	}, []);
</script>

<svelte:head>
	<title>{pageTitle('Systems')}</title>
	<link rel="preload" as="fetch" href="/api/systems/all/" crossorigin="anonymous" />
</svelte:head>

<article>
	<header>
		<h1>Systems</h1>
	</header>

	{#if systems.loading}
		<p class="status">Loading...</p>
	{:else if systems.error}
		<p class="status error">Failed to load systems.</p>
	{:else if systems.data.length === 0}
		<p class="status">No systems found.</p>
	{:else}
		<ul class="system-list">
			{#each systems.data as system (system.slug)}
				<li>
					<a href={resolve(`/systems/${system.slug}`)} class="system-row">
						<span class="system-name">{system.name}</span>
						<span class="system-meta">
							{#if system.manufacturer}
								<span class="manufacturer">{system.manufacturer.name}</span>
							{/if}
							<span class="count"
								>{system.machine_count} machine{system.machine_count === 1 ? '' : 's'}</span
							>
						</span>
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

	.system-list {
		list-style: none;
		padding: 0;
	}

	.system-row {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		padding: var(--size-3) 0;
		border-bottom: 1px solid var(--color-border-soft);
		text-decoration: none;
		color: inherit;
		gap: var(--size-4);
	}

	.system-row:hover .system-name {
		color: var(--color-accent);
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
