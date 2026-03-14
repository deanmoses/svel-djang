<script lang="ts">
	import { resolve } from '$app/paths';
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';
	import CardGrid from '$lib/components/grid/CardGrid.svelte';
	import Markdown from '$lib/components/Markdown.svelte';
	import SidebarList from '$lib/components/SidebarList.svelte';
	import SidebarListItem from '$lib/components/SidebarListItem.svelte';
	import SidebarSection from '$lib/components/SidebarSection.svelte';
	import TitleCard from '$lib/components/cards/TitleCard.svelte';
	import TwoColumnLayout from '$lib/components/TwoColumnLayout.svelte';
	import { pageTitle } from '$lib/constants';

	let { data } = $props();
	let system = $derived(data.system);
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
			{#if system.description_html}
				<Markdown html={system.description_html} />
			{/if}

			{#if system.titles.length === 0}
				<p class="empty">No titles on this system.</p>
			{:else}
				<section>
					<h2>Titles ({system.titles.length})</h2>
					<CardGrid>
						{#each system.titles as title (title.slug)}
							<TitleCard
								slug={title.slug}
								name={title.name}
								thumbnailUrl={title.thumbnail_url}
								manufacturerName={title.manufacturer_name}
								year={title.year}
							/>
						{/each}
					</CardGrid>
				</section>
			{/if}
		{/snippet}

		{#snippet sidebar()}
			{#if system.manufacturer_name}
				<SidebarSection heading="Manufacturer">
					<a href={resolve(`/manufacturers/${system.manufacturer_slug}`)}
						>{system.manufacturer_name}</a
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

	h2 {
		font-size: var(--font-size-3);
		font-weight: 600;
		color: var(--color-text-primary);
		margin-bottom: var(--size-3);
	}

	.empty {
		color: var(--color-text-muted);
		font-size: var(--font-size-2);
		padding: var(--size-8) 0;
		text-align: center;
	}
</style>
