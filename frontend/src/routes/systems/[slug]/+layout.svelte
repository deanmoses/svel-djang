<script lang="ts">
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import { SITE_NAME } from '$lib/constants';
	import { auth } from '$lib/auth.svelte';
	import MetaTags from '$lib/components/MetaTags.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
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
			!page.url.pathname.endsWith('/sources') &&
			!page.url.pathname.endsWith('/edit-history')
	);
	let isEdit = $derived(page.url.pathname.endsWith('/edit'));
	let isSources = $derived(page.url.pathname.endsWith('/sources'));
	let isEditHistory = $derived(page.url.pathname.endsWith('/edit-history'));
</script>

<MetaTags
	title={system.name}
	description={system.description?.text || `${system.name} — ${SITE_NAME}`}
	url={page.url.href}
/>

<article>
	<PageHeader
		title={system.name}
		breadcrumbs={[{ label: 'Systems', href: '/systems' }]}
		--page-header-title-mb="var(--size-2)"
	/>

	<TwoColumnLayout>
		{#snippet main()}
			{#if system.description?.html}
				<div class="description">
					<Markdown html={system.description.html} citations={system.description.citations} />
					<AttributionLine attribution={system.description.attribution} />
				</div>
			{/if}

			<TabNav>
				<Tab active={isDetail} href={resolve(`/systems/${slug}`)}>Detail</Tab>
				{#if auth.isAuthenticated}
					<Tab active={isEdit} href={resolve(`/systems/${slug}/edit`)}>Edit</Tab>
				{/if}
				<Tab active={isSources} href={resolve(`/systems/${slug}/sources`)}>Sources</Tab>
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
	.description {
		margin-bottom: var(--size-6);
	}
</style>
