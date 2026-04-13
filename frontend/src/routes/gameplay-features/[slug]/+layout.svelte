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
	let profile = $derived(data.profile);
	let slug = $derived(page.params.slug);

	/** Normalize for near-duplicate alias filtering (matches backend's old _normalize). */
	function normalizeAlias(s: string): string {
		let n = s.toLowerCase().replace(/-/g, '').replace(/ /g, '');
		if (n.endsWith('s')) n = n.slice(0, -1);
		return n;
	}

	let displayAliases = $derived.by(() => {
		const canonical = normalizeAlias(profile.name);
		return (profile.aliases ?? []).filter((a: string) => normalizeAlias(a) !== canonical);
	});

	$effect(() => {
		auth.load();
	});

	let isMedia = $derived(
		page.url.pathname.endsWith('/media') || page.url.pathname.includes('/media/')
	);
	let isDetail = $derived(
		!page.url.pathname.endsWith('/edit') &&
			!page.url.pathname.endsWith('/sources') &&
			!page.url.pathname.endsWith('/edit-history') &&
			!isMedia
	);
	let isEdit = $derived(page.url.pathname.endsWith('/edit'));
	let isSources = $derived(page.url.pathname.endsWith('/sources'));
	let isEditHistory = $derived(page.url.pathname.endsWith('/edit-history'));
</script>

<MetaTags
	title={profile.name}
	description={profile.description?.text || `${profile.name} — ${SITE_NAME}`}
	url={page.url.href}
/>

<article>
	<PageHeader
		title={profile.name}
		breadcrumbs={[{ label: 'Gameplay Features', href: '/gameplay-features' }]}
	/>

	<TwoColumnLayout>
		{#snippet main()}
			{#if profile.description?.html}
				<div class="description">
					<Markdown html={profile.description.html} citations={profile.description.citations} />
					<AttributionLine attribution={profile.description.attribution} />
				</div>
			{/if}

			<TabNav>
				<Tab active={isDetail} href={resolve(`/gameplay-features/${slug}`)}>Machines</Tab>
				<Tab active={isMedia} href={resolve(`/gameplay-features/${slug}/media`)}>Media</Tab>
				{#if auth.isAuthenticated}
					<Tab active={isEdit} href={resolve(`/gameplay-features/${slug}/edit`)}>Edit</Tab>
				{/if}
				<Tab active={isSources} href={resolve(`/gameplay-features/${slug}/sources`)}>Sources</Tab>
				<Tab active={isEditHistory} href={resolve(`/gameplay-features/${slug}/edit-history`)}
					>Edit History</Tab
				>
			</TabNav>

			{@render children()}
		{/snippet}

		{#snippet sidebar()}
			{#if profile.parents && profile.parents.length > 0}
				<SidebarSection heading="Type of">
					<SidebarList>
						{#each profile.parents as parent (parent.slug)}
							<SidebarListItem>
								<a href={resolve(`/gameplay-features/${parent.slug}`)}>{parent.name}</a>
							</SidebarListItem>
						{/each}
					</SidebarList>
				</SidebarSection>
			{/if}
			{#if profile.children && profile.children.length > 0}
				<SidebarSection heading="Subtypes">
					<SidebarList>
						{#each profile.children as child (child.slug)}
							<SidebarListItem>
								<a href={resolve(`/gameplay-features/${child.slug}`)}>{child.name}</a>
							</SidebarListItem>
						{/each}
					</SidebarList>
				</SidebarSection>
			{/if}
			{#if displayAliases.length > 0}
				<SidebarSection heading="Also known as">
					<p class="aliases">{displayAliases.join(', ')}</p>
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
