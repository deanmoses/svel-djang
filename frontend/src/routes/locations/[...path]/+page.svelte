<script lang="ts">
	import { page } from '$app/state';
	import { resolveHref } from '$lib/utils';
	import { pageTitle } from '$lib/constants';
	import LocationDetailPage from '$lib/components/LocationDetailPage.svelte';
	import SidebarSection from '$lib/components/SidebarSection.svelte';
	import SidebarList from '$lib/components/SidebarList.svelte';
	import SidebarListItem from '$lib/components/SidebarListItem.svelte';
	import type { components } from '$lib/api/schema';

	type LocationDetail = components['schemas']['LocationDetailSchema'];
	type LocationChild = components['schemas']['LocationChildRef'];

	const CHILD_TYPE_LABELS: Record<string, string> = {
		state: 'States',
		region: 'Regions',
		department: 'Departments',
		province: 'Provinces',
		community: 'Communities',
		prefecture: 'Prefectures',
		district: 'Districts',
		county: 'Counties',
		city: 'Cities'
	};

	function childrenHeading(children: LocationChild[]): string {
		const type = children[0]?.location_type;
		return (type && CHILD_TYPE_LABELS[type]) ?? 'Subdivisions';
	}

	let locationPath = $derived(page.params.path ?? '');

	let loc = $state<LocationDetail | null>(null);
	let loading = $state(true);
	let fetchError = $state(false);

	$effect(() => {
		const path = locationPath;
		loading = true;
		fetchError = false;
		loc = null;
		fetch(`/api/locations/${path}`)
			.then((res) => {
				if (!res.ok) throw new Error('not found');
				return res.json();
			})
			.then((data: LocationDetail) => {
				loc = data;
			})
			.catch(() => {
				fetchError = true;
			})
			.finally(() => {
				loading = false;
			});
	});

	let crumbs = $derived.by(() => {
		const base = [{ label: 'Locations', href: '/locations' }];
		if (!loc) return base;
		return [
			...base,
			...loc.ancestors.map((a) => ({ label: a.name, href: `/locations/${a.location_path}` }))
		];
	});

	let heading = $derived(loc?.name ?? '');
	let subtitle = $derived(
		`${loc?.manufacturer_count ?? 0} manufacturer${loc?.manufacturer_count === 1 ? '' : 's'}`
	);
</script>

<svelte:head>
	<title>{pageTitle(heading || 'Location')}</title>
</svelte:head>

<LocationDetailPage
	{loading}
	error={!loading && (fetchError || !loc)}
	{heading}
	{subtitle}
	{crumbs}
	manufacturers={loc?.manufacturers ?? []}
>
	{#snippet sidebar()}
		{#if loc && loc.children.length > 0}
			<SidebarSection heading={childrenHeading(loc.children)}>
				<SidebarList>
					{#each loc.children as child (child.location_path)}
						<SidebarListItem>
							<a href={resolveHref(`/locations/${child.location_path}`)}>
								{child.name}
							</a>
							<span class="count">{child.manufacturer_count}</span>
						</SidebarListItem>
					{/each}
				</SidebarList>
			</SidebarSection>
		{/if}
	{/snippet}
</LocationDetailPage>

<style>
	.count {
		font-size: var(--font-size-0);
		color: var(--color-text-muted);
	}
</style>
