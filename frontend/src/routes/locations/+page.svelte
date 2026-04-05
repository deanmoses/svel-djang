<script lang="ts">
	import client from '$lib/api/client';
	import { createAsyncLoader } from '$lib/async-loader.svelte';
	import { resolveHref } from '$lib/utils';
	import { pageTitle } from '$lib/constants';

	const locations = createAsyncLoader(
		async () => {
			const { data } = await client.GET('/api/locations/');
			return data ?? { countries: [] };
		},
		{ countries: [] }
	);
</script>

<svelte:head>
	<title>{pageTitle('Locations')}</title>
	<link rel="preload" as="fetch" href="/api/locations/" crossorigin="anonymous" />
</svelte:head>

<article>
	<header>
		<h1>Locations</h1>
		<p class="subtitle">Browse pinball manufacturers by country, state, and city.</p>
	</header>

	{#if locations.loading}
		<p class="status">Loading...</p>
	{:else if locations.error}
		<p class="status error">Failed to load locations.</p>
	{:else if locations.data.countries.length === 0}
		<p class="status">No locations found.</p>
	{:else}
		<div class="countries">
			{#each locations.data.countries as country (country.location_path)}
				<section class="country-section">
					<h2>
						<a href={resolveHref(`/locations/${country.location_path}`)}>
							{country.name}
						</a>
						<span class="count">{country.manufacturer_count}</span>
					</h2>

					{#if country.children.length > 0}
						<ul class="child-list">
							{#each country.children as child (child.location_path)}
								<li>
									<a href={resolveHref(`/locations/${child.location_path}`)} class="location-row">
										<span class="location-name">{child.name}</span>
										<span class="count">{child.manufacturer_count}</span>
									</a>
								</li>
							{/each}
						</ul>
					{/if}
				</section>
			{/each}
		</div>
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

	.country-section {
		margin-bottom: var(--size-6);
	}

	.country-section h2 {
		display: flex;
		align-items: baseline;
		gap: var(--size-2);
		font-size: var(--font-size-5);
		font-weight: 600;
		color: var(--color-text-primary);
		margin-bottom: var(--size-3);
		padding-bottom: var(--size-2);
		border-bottom: 2px solid var(--color-border-soft);
	}

	.country-section h2 a {
		color: inherit;
		text-decoration: none;
	}

	.country-section h2 a:hover {
		color: var(--color-accent);
	}

	.child-list {
		list-style: none;
		padding: 0;
		margin: 0;
	}

	.location-row {
		display: flex;
		align-items: baseline;
		justify-content: space-between;
		padding: var(--size-2) 0;
		border-bottom: 1px solid var(--color-border-soft);
		text-decoration: none;
		color: inherit;
	}

	.location-row:hover .location-name {
		color: var(--color-accent);
	}

	.location-name {
		font-size: var(--font-size-2);
		color: var(--color-text-primary);
		font-weight: 500;
	}

	.count {
		font-size: var(--font-size-0);
		color: var(--color-text-muted);
		font-weight: 400;
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
