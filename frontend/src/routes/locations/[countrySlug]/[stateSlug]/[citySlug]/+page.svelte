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
	import ClientFilteredGrid from '$lib/components/grid/ClientFilteredGrid.svelte';
	import ManufacturerCard from '$lib/components/cards/ManufacturerCard.svelte';
	import CardGrid from '$lib/components/grid/CardGrid.svelte';
	import SkeletonCard from '$lib/components/cards/SkeletonCard.svelte';

	const SKELETON_INDICES = Array.from({ length: 8 }, (_, i) => i);

	let countrySlug = $derived(page.params.countrySlug!);
	let stateSlug = $derived(page.params.stateSlug!);
	let citySlug = $derived(page.params.citySlug!);

	const cityData = createAsyncLoader(async () => {
		const { data } = await client.GET('/api/locations/{country_slug}/{state_slug}/{city_slug}', {
			params: {
				path: {
					country_slug: countrySlug,
					state_slug: stateSlug,
					city_slug: citySlug
				}
			}
		});
		return data ?? null;
	}, null);
</script>

<svelte:head>
	<title
		>{pageTitle(
			cityData.data ? `${cityData.data.name}, ${cityData.data.state_name}` : 'City'
		)}</title
	>
</svelte:head>

<article>
	{#if cityData.loading}
		<header>
			<Breadcrumb crumbs={[{ label: 'Locations', href: '/locations' }]} current="Loading..." />
			<h1>Loading...</h1>
		</header>
		<CardGrid>
			{#each SKELETON_INDICES as i (i)}
				<SkeletonCard />
			{/each}
		</CardGrid>
	{:else if cityData.error || !cityData.data}
		<header>
			<Breadcrumb crumbs={[{ label: 'Locations', href: '/locations' }]} current="Error" />
			<h1>City not found</h1>
		</header>
		<p class="status error">Failed to load city.</p>
	{:else}
		{@const c = cityData.data}
		<header>
			<Breadcrumb
				crumbs={[
					{ label: 'Locations', href: '/locations' },
					{ label: c.country_name, href: `/locations/${c.country_slug}` },
					{ label: c.state_name!, href: `/locations/${c.country_slug}/${c.state_slug}` }
				]}
				current={c.name}
			/>
			<h1>{c.name}, {c.state_name}</h1>
			<p class="subtitle">
				{c.manufacturer_count} manufacturer{c.manufacturer_count === 1 ? '' : 's'}
			</p>
		</header>

		<TwoColumnLayout>
			{#snippet main()}
				<ClientFilteredGrid items={c.manufacturers} entityName="manufacturer">
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
				<SidebarSection heading="Country">
					<SidebarList>
						<SidebarListItem>
							<a href={resolveHref(`/locations/${c.country_slug}`)}>
								{c.country_name}
							</a>
						</SidebarListItem>
					</SidebarList>
				</SidebarSection>

				<SidebarSection heading="State">
					<SidebarList>
						<SidebarListItem>
							<a href={resolveHref(`/locations/${c.country_slug}/${c.state_slug}`)}>
								{c.state_name}
							</a>
						</SidebarListItem>
					</SidebarList>
				</SidebarSection>
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

	.status.error {
		color: var(--color-error, #c0392b);
		text-align: center;
		padding: var(--size-8) 0;
	}
</style>
