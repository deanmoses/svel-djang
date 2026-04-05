<script lang="ts">
	import type { Snippet } from 'svelte';
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';
	import TwoColumnLayout from '$lib/components/TwoColumnLayout.svelte';
	import CardGrid from '$lib/components/grid/CardGrid.svelte';
	import SkeletonCard from '$lib/components/cards/SkeletonCard.svelte';
	import ManufacturerCardGrid from '$lib/components/ManufacturerCardGrid.svelte';

	const SKELETON_INDICES = Array.from({ length: 8 }, (_, i) => i);

	let {
		loading,
		error,
		heading,
		subtitle,
		crumbs,
		manufacturers,
		sidebar: sidebarContent
	}: {
		loading: boolean;
		error: boolean;
		heading: string;
		subtitle: string;
		crumbs: { label: string; href: string }[];
		manufacturers: {
			name: string;
			slug: string;
			model_count: number;
			thumbnail_url?: string | null;
		}[];
		sidebar: Snippet;
	} = $props();
</script>

<article>
	{#if loading}
		<header>
			<Breadcrumb {crumbs} current="Loading..." />
			<h1>Loading...</h1>
		</header>
		<CardGrid>
			{#each SKELETON_INDICES as i (i)}
				<SkeletonCard />
			{/each}
		</CardGrid>
	{:else if error}
		<header>
			<Breadcrumb {crumbs} current="Error" />
			<h1>Not found</h1>
		</header>
		<p class="status error">Failed to load location.</p>
	{:else}
		<header>
			<Breadcrumb {crumbs} current={heading} />
			<h1>{heading}</h1>
			<p class="subtitle">{subtitle}</p>
		</header>

		<TwoColumnLayout>
			{#snippet main()}
				<ManufacturerCardGrid {manufacturers} showCount={false} />
			{/snippet}

			{#snippet sidebar()}
				{@render sidebarContent()}
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
		color: var(--color-error);
		text-align: center;
		padding: var(--size-8) 0;
	}
</style>
