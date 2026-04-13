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
	let theme = $derived(data.theme);
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
	title={theme.name}
	description={theme.description?.text || `${theme.name} — ${SITE_NAME}`}
	url={page.url.href}
/>

<article>
	<PageHeader title={theme.name} breadcrumbs={[{ label: 'Themes', href: '/themes' }]} />

	<TwoColumnLayout>
		{#snippet main()}
			{#if theme.description?.html}
				<div class="description">
					<Markdown html={theme.description.html} citations={theme.description.citations} />
					<AttributionLine attribution={theme.description.attribution} />
				</div>
			{/if}

			<TabNav>
				<Tab active={isDetail} href={resolve(`/themes/${slug}`)}>Machines</Tab>
				{#if auth.isAuthenticated}
					<Tab active={isEdit} href={resolve(`/themes/${slug}/edit`)}>Edit</Tab>
				{/if}
				<Tab active={isSources} href={resolve(`/themes/${slug}/sources`)}>Sources</Tab>
				<Tab active={isEditHistory} href={resolve(`/themes/${slug}/edit-history`)}>Edit History</Tab
				>
			</TabNav>

			{@render children()}
		{/snippet}

		{#snippet sidebar()}
			{#if theme.parents && theme.parents.length > 0}
				<SidebarSection heading="Parent themes">
					<SidebarList>
						{#each theme.parents as parent (parent.slug)}
							<SidebarListItem>
								<a href={resolve(`/themes/${parent.slug}`)}>{parent.name}</a>
							</SidebarListItem>
						{/each}
					</SidebarList>
				</SidebarSection>
			{/if}
			{#if theme.children && theme.children.length > 0}
				<SidebarSection heading={`Sub-themes (${theme.children.length})`}>
					<SidebarList>
						{#each theme.children as child (child.slug)}
							<SidebarListItem>
								<a href={resolve(`/themes/${child.slug}`)}>{child.name}</a>
							</SidebarListItem>
						{/each}
					</SidebarList>
				</SidebarSection>
			{/if}
			{#if theme.aliases && theme.aliases.length > 0}
				<SidebarSection heading="Also known as">
					<p class="aliases">{theme.aliases.join(', ')}</p>
				</SidebarSection>
			{/if}
		{/snippet}
	</TwoColumnLayout>
</article>

<style>
	article {
		max-width: 64rem;
	}

	.description {
		margin-bottom: var(--size-6);
	}

	.aliases {
		font-size: var(--font-size-0);
		color: var(--color-text-muted);
		margin: 0;
	}
</style>
