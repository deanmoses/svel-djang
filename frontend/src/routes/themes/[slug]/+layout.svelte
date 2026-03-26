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
	let theme = $derived(data.theme);
	let slug = $derived(page.params.slug);

	$effect(() => {
		auth.load();
	});

	let isDetail = $derived(
		!page.url.pathname.endsWith('/edit') && !page.url.pathname.endsWith('/activity')
	);
	let isEdit = $derived(page.url.pathname.endsWith('/edit'));
	let isActivity = $derived(page.url.pathname.endsWith('/activity'));
</script>

<svelte:head>
	<title>{pageTitle(theme.name)}</title>
</svelte:head>

<article>
	<header>
		<Breadcrumb crumbs={[{ label: 'Themes', href: '/themes' }]} current={theme.name} />
		<h1>{theme.name}</h1>
	</header>

	<TwoColumnLayout>
		{#snippet main()}
			{#if theme.description?.html}
				<div class="description">
					<Markdown html={theme.description.html} />
					<AttributionLine attribution={theme.description.attribution} />
				</div>
			{/if}

			<TabNav>
				<Tab active={isDetail} href={resolve(`/themes/${slug}`)}>Machines</Tab>
				{#if auth.isAuthenticated}
					<Tab active={isEdit} href={resolve(`/themes/${slug}/edit`)}>Edit</Tab>
				{/if}
				<Tab active={isActivity} href={resolve(`/themes/${slug}/activity`)}>Activity</Tab>
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
				<SidebarSection heading="Sub-themes">
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

	header {
		margin-bottom: var(--size-6);
	}

	h1 {
		font-size: var(--font-size-7);
		font-weight: 700;
		color: var(--color-text-primary);
		margin-bottom: var(--size-4);
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
