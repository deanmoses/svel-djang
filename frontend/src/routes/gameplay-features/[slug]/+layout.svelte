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
	let profile = $derived(data.profile);
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
	<title>{pageTitle(profile.name)}</title>
</svelte:head>

<article>
	<header>
		<Breadcrumb
			crumbs={[{ label: 'Gameplay Features', href: '/gameplay-features' }]}
			current={profile.name}
		/>
		<h1>{profile.name}</h1>
	</header>

	<TwoColumnLayout>
		{#snippet main()}
			{#if profile.description?.html}
				<div class="description">
					<Markdown html={profile.description.html} />
					<AttributionLine attribution={profile.description.attribution} />
				</div>
			{/if}

			<TabNav>
				<Tab active={isDetail} href={resolve(`/gameplay-features/${slug}`)}>Machines</Tab>
				{#if auth.isAuthenticated}
					<Tab active={isEdit} href={resolve(`/gameplay-features/${slug}/edit`)}>Edit</Tab>
				{/if}
				<Tab active={isActivity} href={resolve(`/gameplay-features/${slug}/activity`)}>Activity</Tab
				>
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
			{#if profile.aliases && profile.aliases.length > 0}
				<SidebarSection heading="Also known as">
					<p class="aliases">{profile.aliases.join(', ')}</p>
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
