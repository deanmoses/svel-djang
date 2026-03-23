<script lang="ts">
	import { page } from '$app/state';
	import client from '$lib/api/client';
	import { createAsyncLoader } from '$lib/async-loader.svelte';
	import { resolveHref } from '$lib/utils';
	import { pageTitle } from '$lib/constants';
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';
	import TwoColumnLayout from '$lib/components/TwoColumnLayout.svelte';
	import SidebarSection from '$lib/components/SidebarSection.svelte';
	import SidebarList from '$lib/components/SidebarList.svelte';
	import SidebarListItem from '$lib/components/SidebarListItem.svelte';
	import CardGrid from '$lib/components/grid/CardGrid.svelte';
	import ClientFilteredGrid from '$lib/components/grid/ClientFilteredGrid.svelte';
	import ManufacturerCard from '$lib/components/cards/ManufacturerCard.svelte';
	import SkeletonCard from '$lib/components/cards/SkeletonCard.svelte';

	const SKELETON_INDICES = Array.from({ length: 8 }, (_, i) => i);

	let countrySlug = $derived(page.params.countrySlug!);

	const country = createAsyncLoader(async () => {
		const { data } = await client.GET('/api/locations/{country_slug}', {
			params: { path: { country_slug: countrySlug } }
		});
		return data ?? null;
	}, null);

	type FlatCity = {
		name: string;
		slug: string;
		manufacturer_count: number;
		stateName: string | null;
		stateSlug: string | null;
		href: string;
	};

	let allCities = $derived.by((): FlatCity[] => {
		const d = country.data;
		if (!d) return [];
		const cities: FlatCity[] = [];
		for (const city of d.cities) {
			cities.push({
				...city,
				stateName: null,
				stateSlug: null,
				href: `/locations/${countrySlug}/cities/${city.slug}`
			});
		}
		for (const state of d.states) {
			for (const city of state.cities) {
				cities.push({
					...city,
					stateName: state.name,
					stateSlug: state.slug,
					href: `/locations/${countrySlug}/${state.slug}/${city.slug}`
				});
			}
		}
		cities.sort(
			(a, b) => b.manufacturer_count - a.manufacturer_count || a.name.localeCompare(b.name)
		);
		return cities;
	});

	let sortedStates = $derived.by(() => {
		const d = country.data;
		if (!d) return [];
		return [...d.states].sort(
			(a, b) => b.manufacturer_count - a.manufacturer_count || a.name.localeCompare(b.name)
		);
	});
</script>

<svelte:head>
	<title>{pageTitle(country.data?.name ?? 'Country')}</title>
</svelte:head>

<article>
	{#if country.loading}
		<header>
			<Breadcrumb crumbs={[{ label: 'Locations', href: '/locations' }]} current="Loading..." />
			<h1>Loading...</h1>
		</header>
		<CardGrid>
			{#each SKELETON_INDICES as i (i)}
				<SkeletonCard />
			{/each}
		</CardGrid>
	{:else if country.error || !country.data}
		<header>
			<Breadcrumb crumbs={[{ label: 'Locations', href: '/locations' }]} current="Error" />
			<h1>Country not found</h1>
		</header>
		<p class="status error">Failed to load country.</p>
	{:else}
		{@const d = country.data}
		<header>
			<Breadcrumb crumbs={[{ label: 'Locations', href: '/locations' }]} current={d.name} />
			<h1>{d.name}</h1>
			<p class="subtitle">
				{d.manufacturer_count} manufacturer{d.manufacturer_count === 1 ? '' : 's'}
			</p>
		</header>

		<TwoColumnLayout>
			{#snippet main()}
				<ClientFilteredGrid items={d.manufacturers} entityName="manufacturer">
					{#snippet children(mfr)}
						<ManufacturerCard
							slug={mfr.slug}
							name={mfr.name}
							thumbnailUrl={mfr.thumbnail_url}
							modelCount={mfr.model_count}
						/>
					{/snippet}
				</ClientFilteredGrid>
			{/snippet}

			{#snippet sidebar()}
				{#if sortedStates.length > 0}
					<SidebarSection heading="States">
						<SidebarList>
							{#each sortedStates as state (state.slug)}
								<SidebarListItem>
									<a href={resolveHref(`/locations/${countrySlug}/${state.slug}`)}>
										{state.name}
									</a>
									<span class="count">{state.manufacturer_count}</span>
								</SidebarListItem>
							{/each}
						</SidebarList>
					</SidebarSection>
				{/if}

				{#if allCities.length > 0}
					<SidebarSection heading="Cities">
						<SidebarList>
							{#each allCities as city (city.href)}
								<SidebarListItem>
									<span class="city-entry">
										<a href={resolveHref(city.href)}>{city.name}</a
										>{#if city.stateName && city.stateSlug}, <a
												href={resolveHref(`/locations/${countrySlug}/${city.stateSlug}`)}
												class="state-link">{city.stateName}</a
											>{/if}
									</span>
									<span class="count">{city.manufacturer_count}</span>
								</SidebarListItem>
							{/each}
						</SidebarList>
					</SidebarSection>
				{/if}
			{/snippet}
		</TwoColumnLayout>
	{/if}
</article>

<style>
	header {
		margin-bottom: var(--size-5);
	}

	h1 {
		font-size: var(--font-size-7);
		font-weight: 700;
		color: var(--color-text-primary);
		margin-bottom: var(--size-2);
	}

	.subtitle {
		font-size: var(--font-size-2);
		color: var(--color-text-muted);
	}

	.count {
		font-size: var(--font-size-0);
		color: var(--color-text-muted);
	}

	.state-link {
		color: var(--color-text-muted);
		text-decoration: none;
	}

	.state-link:hover {
		color: var(--color-accent);
		text-decoration: underline;
	}

	.status.error {
		color: var(--color-error, #c0392b);
		text-align: center;
		padding: var(--size-8) 0;
	}
</style>
