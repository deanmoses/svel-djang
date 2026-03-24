<script lang="ts">
	import { resolve } from '$app/paths';
	import client from '$lib/api/client';
	import { createPaginatedLoader } from '$lib/paginated-loader.svelte';
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';
	import Markdown from '$lib/components/Markdown.svelte';
	import TwoColumnLayout from '$lib/components/TwoColumnLayout.svelte';
	import SidebarSection from '$lib/components/SidebarSection.svelte';
	import SidebarList from '$lib/components/SidebarList.svelte';
	import SidebarListItem from '$lib/components/SidebarListItem.svelte';
	import PaginatedSection from '$lib/components/grid/PaginatedSection.svelte';
	import MachineCard from '$lib/components/cards/MachineCard.svelte';
	import { pageTitle } from '$lib/constants';

	let { data } = $props();
	let profile = $derived(data.profile);

	const machines = createPaginatedLoader(async (page) => {
		const { data: result } = await client.GET('/api/models/', {
			params: { query: { feature: profile.slug, page } }
		});
		return result ?? { items: [], count: 0 };
	});
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
				</div>
			{/if}
			<PaginatedSection
				loader={machines}
				heading="Machines"
				emptyMessage="No machines with this feature."
			>
				{#snippet children(machine)}
					<MachineCard
						slug={machine.slug}
						name={machine.name}
						thumbnailUrl={machine.thumbnail_url}
						manufacturerName={machine.manufacturer_name}
						year={machine.year}
					/>
				{/snippet}
			</PaginatedSection>
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
