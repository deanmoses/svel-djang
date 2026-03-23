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
		{
			countries: [] as {
				name: string;
				slug: string;
				manufacturer_count: number;
				cities: { name: string; slug: string; manufacturer_count: number }[];
				states: {
					name: string;
					slug: string;
					manufacturer_count: number;
					cities: { name: string; slug: string; manufacturer_count: number }[];
				}[];
			}[]
		}
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
			{#each locations.data.countries as country (country.slug)}
				<section class="country-section">
					<h2>
						<a href={resolveHref(`/locations/${country.slug}`)}>
							{country.name}
						</a>
						<span class="count">{country.manufacturer_count}</span>
					</h2>

					{#if country.cities.length > 0}
						<ul class="city-list top-level">
							{#each country.cities as city (city.slug)}
								<li>
									<a
										href={resolveHref(`/locations/${country.slug}/cities/${city.slug}`)}
										class="location-row"
									>
										<span class="location-name">{city.name}</span>
										<span class="count">{city.manufacturer_count}</span>
									</a>
								</li>
							{/each}
						</ul>
					{/if}

					{#if country.states.length > 0}
						<ul class="state-list">
							{#each country.states as state (state.slug)}
								<li>
									<a
										href={resolveHref(`/locations/${country.slug}/${state.slug}`)}
										class="location-row"
									>
										<span class="location-name">{state.name}</span>
										<span class="count">{state.manufacturer_count}</span>
									</a>

									{#if state.cities.length > 0}
										<ul class="city-list">
											{#each state.cities as city (city.slug)}
												<li>
													<a
														href={resolveHref(
															`/locations/${country.slug}/${state.slug}/${city.slug}`
														)}
														class="location-row"
													>
														<span class="location-name">{city.name}</span>
														<span class="count">{city.manufacturer_count}</span>
													</a>
												</li>
											{/each}
										</ul>
									{/if}
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

	.state-list,
	.city-list {
		list-style: none;
		padding: 0;
		margin: 0;
	}

	.city-list {
		padding-left: var(--size-5);
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
		color: var(--color-error, #c0392b);
	}
</style>
