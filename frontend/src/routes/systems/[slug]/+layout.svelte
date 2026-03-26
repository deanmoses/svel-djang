<script lang="ts">
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import { pageTitle } from '$lib/constants';
	import { auth } from '$lib/auth.svelte';
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';
	import AttributionLine from '$lib/components/AttributionLine.svelte';
	import Markdown from '$lib/components/Markdown.svelte';
	import SidebarList from '$lib/components/SidebarList.svelte';
	import SidebarListItem from '$lib/components/SidebarListItem.svelte';
	import SidebarSection from '$lib/components/SidebarSection.svelte';
	import TabNav from '$lib/components/TabNav.svelte';
	import Tab from '$lib/components/Tab.svelte';
	import TwoColumnLayout from '$lib/components/TwoColumnLayout.svelte';

	let { data, children } = $props();
	let system = $derived(data.system);
	let slug = $derived(page.params.slug);

	$effect(() => {
		auth.load();
	});

	let isDetail = $derived(
		!page.url.pathname.endsWith('/edit') &&
			!page.url.pathname.endsWith('/activity') &&
			!page.url.pathname.endsWith('/edit-history')
	);
	let isEdit = $derived(page.url.pathname.endsWith('/edit'));
	let isActivity = $derived(page.url.pathname.endsWith('/activity'));
	let isEditHistory = $derived(page.url.pathname.endsWith('/edit-history'));
</script>

<svelte:head>
	<title>{pageTitle(system.name)}</title>
</svelte:head>

<article>
	<header>
		<Breadcrumb crumbs={[{ label: 'Systems', href: '/systems' }]} current={system.name} />
		<h1>{system.name}</h1>
	</header>

	<TwoColumnLayout>
		{#snippet main()}
			{#if system.description?.html}
				<div class="description">
					<Markdown html={system.description.html} />
					<AttributionLine attribution={system.description.attribution} />
				</div>
			{/if}

			<TabNav>
				<Tab active={isDetail} href={resolve(`/systems/${slug}`)}>Detail</Tab>
				{#if auth.isAuthenticated}
					<Tab active={isEdit} href={resolve(`/systems/${slug}/edit`)}>Edit</Tab>
				{/if}
				<Tab active={isActivity} href={resolve(`/systems/${slug}/activity`)}>Activity</Tab>
				<Tab active={isEditHistory} href={resolve(`/systems/${slug}/edit-history`)}
					>Edit History</Tab
				>
			</TabNav>

			{@render children()}
		{/snippet}

		{#snippet sidebar()}
			{#if system.manufacturer}
				<SidebarSection heading="Manufacturer">
					<a href={resolve(`/manufacturers/${system.manufacturer.slug}`)}
						>{system.manufacturer.name}</a
					>
				</SidebarSection>
			{/if}

			{#if system.sibling_systems.length > 0}
				<SidebarSection heading="Other Systems By This Manufacturer">
					<SidebarList>
						{#each system.sibling_systems as sibling (sibling.slug)}
							<SidebarListItem>
								<a href={resolve(`/systems/${sibling.slug}`)}>{sibling.name}</a>
							</SidebarListItem>
						{/each}
					</SidebarList>
				</SidebarSection>
			{/if}
		{/snippet}
	</TwoColumnLayout>
</article>

<style>
	header {
		margin-bottom: var(--size-6);
	}

	h1 {
		font-size: var(--font-size-7);
		font-weight: 700;
		color: var(--color-text-primary);
		margin-bottom: var(--size-2);
	}

	.description {
		margin-bottom: var(--size-6);
	}
</style>
