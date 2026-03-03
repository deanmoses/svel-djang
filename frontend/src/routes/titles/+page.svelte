<script lang="ts">
	import { replaceState } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { page } from '$app/state';
	import client from '$lib/api/client';
	import { createAsyncLoader } from '$lib/async-loader.svelte';
	import ActiveFilterChips from '$lib/components/ActiveFilterChips.svelte';
	import FaIcon from '$lib/components/FaIcon.svelte';
	import CardGrid from '$lib/components/grid/CardGrid.svelte';
	import InfiniteGrid from '$lib/components/grid/InfiniteGrid.svelte';
	import SearchBox from '$lib/components/SearchBox.svelte';
	import SkeletonCard from '$lib/components/cards/SkeletonCard.svelte';
	import TitleCard from '$lib/components/cards/TitleCard.svelte';
	import TitleFilterSidebar from '$lib/components/TitleFilterSidebar.svelte';
	import { pageTitle } from '$lib/constants';
	import {
		filterTitles,
		filtersFromParams,
		filtersToParams,
		type FacetedTitle
	} from '$lib/facet-engine';
	import { faSliders, faXmark } from '@fortawesome/free-solid-svg-icons';

	const SKELETON_INDICES = Array.from({ length: 12 }, (_, i) => i);

	// -----------------------------------------------------------------------
	// Data loading
	// -----------------------------------------------------------------------
	const titles = createAsyncLoader(async () => {
		const { data } = await client.GET('/api/titles/all/');
		return (data ?? []) as FacetedTitle[];
	}, [] as FacetedTitle[]);

	// -----------------------------------------------------------------------
	// Filter state — initialized from URL, synced back on change
	// -----------------------------------------------------------------------
	let filters = $state(filtersFromParams(page.url.searchParams));

	let initialRun = true;
	$effect(() => {
		const sp = filtersToParams(filters, new URLSearchParams());
		const search = sp.toString();
		if (initialRun) {
			initialRun = false;
			return;
		}
		// eslint-disable-next-line svelte/no-navigation-without-resolve -- resolve() is used in the template literal
		replaceState(`${resolve('/titles')}${search ? `?${search}` : ''}`, {});
	});

	let filteredTitles = $derived(filterTitles(titles.data, filters));

	// -----------------------------------------------------------------------
	// Mobile filter drawer
	// -----------------------------------------------------------------------
	let drawerOpen = $state(false);
	let filterToggleEl: HTMLButtonElement | undefined = $state();
	let drawerEl: HTMLDivElement | undefined = $state();

	function openDrawer() {
		drawerOpen = true;
	}
	function closeDrawer() {
		drawerOpen = false;
		requestAnimationFrame(() => filterToggleEl?.focus());
	}

	$effect(() => {
		if (drawerOpen) {
			document.body.style.overflow = 'hidden';
			// Focus the close button inside the drawer
			const closeBtn = drawerEl?.querySelector<HTMLElement>('.drawer-close');
			closeBtn?.focus();
			return () => {
				document.body.style.overflow = '';
			};
		}
	});

	$effect(() => {
		if (!drawerOpen) return;
		function handleKeydown(e: KeyboardEvent) {
			if (e.key === 'Escape') closeDrawer();
		}
		document.addEventListener('keydown', handleKeydown);
		return () => document.removeEventListener('keydown', handleKeydown);
	});
</script>

<svelte:head>
	<title>{pageTitle('Titles')}</title>
	<link rel="preload" as="fetch" href="/api/titles/all/" crossorigin="anonymous" />
</svelte:head>

<div class="titles-page">
	<SearchBox bind:value={filters.query} placeholder="Search titles..." />

	{#if titles.loading}
		<CardGrid>
			{#each SKELETON_INDICES as i (i)}
				<SkeletonCard />
			{/each}
		</CardGrid>
	{:else if titles.error}
		<p class="error">{titles.error}</p>
	{:else}
		<div class="layout">
			<button class="mobile-filter-toggle" bind:this={filterToggleEl} onclick={openDrawer}>
				<FaIcon icon={faSliders} class="filter-icon" />
				Filters
			</button>

			{#if drawerOpen}
				<!-- svelte-ignore a11y_no_static_element_interactions -->
				<div class="drawer-backdrop" onclick={closeDrawer}></div>
			{/if}

			<div
				class="sidebar-drawer"
				class:open={drawerOpen}
				bind:this={drawerEl}
				role="dialog"
				aria-modal={drawerOpen}
				aria-label="Filter titles"
			>
				<div class="drawer-header">
					<button class="drawer-close" onclick={closeDrawer} aria-label="Close filters">
						<FaIcon icon={faXmark} class="close-icon" />
					</button>
				</div>
				<TitleFilterSidebar allTitles={titles.data} bind:filters />
			</div>

			<main class="results">
				<ActiveFilterChips bind:filters allTitles={titles.data} />
				<InfiniteGrid items={filteredTitles} entityName="title">
					{#snippet children(title)}
						<TitleCard
							slug={title.slug}
							name={title.name}
							thumbnailUrl={title.thumbnail_url}
							manufacturerName={title.manufacturer_name}
							year={title.year}
						/>
					{/snippet}
				</InfiniteGrid>
			</main>
		</div>
	{/if}
</div>

<style>
	.titles-page {
		padding: var(--size-5) 0;
	}

	.layout {
		display: grid;
		grid-template-columns: 16rem 1fr;
		gap: var(--size-5);
		align-items: start;
	}

	.results {
		min-width: 0;
	}

	.error {
		text-align: center;
		color: var(--color-error);
		padding: var(--size-6) 0;
	}

	/* Mobile filter toggle — hidden on desktop */
	.mobile-filter-toggle {
		display: none;
		align-items: center;
		gap: var(--size-2);
		padding: var(--size-2) var(--size-3);
		font-size: var(--font-size-1);
		font-family: var(--font-body);
		background-color: var(--color-surface);
		color: var(--color-text-primary);
		border: 1px solid var(--color-border);
		border-radius: var(--radius-2);
		cursor: pointer;
	}

	.mobile-filter-toggle:hover {
		border-color: var(--color-accent);
	}

	:global(.filter-icon) {
		width: 0.9rem;
		height: 0.9rem;
	}

	/* Drawer header (close button) — hidden on desktop */
	.drawer-header {
		display: none;
	}

	.drawer-close {
		background: none;
		border: none;
		color: var(--color-text-muted);
		cursor: pointer;
		padding: var(--size-1);
	}

	.drawer-close:hover {
		color: var(--color-text-primary);
	}

	:global(.close-icon) {
		width: 1.25rem;
		height: 1.25rem;
	}

	/* Backdrop — only visible on mobile */
	.drawer-backdrop {
		display: none;
	}

	/* Mobile overrides */
	@media (max-width: 640px) {
		.layout {
			grid-template-columns: 1fr;
		}

		.mobile-filter-toggle {
			display: inline-flex;
			margin-bottom: var(--size-3);
		}

		.drawer-header {
			display: flex;
			justify-content: flex-end;
			padding-bottom: var(--size-2);
			border-bottom: 1px solid var(--color-border-soft);
			margin-bottom: var(--size-3);
		}

		.sidebar-drawer {
			position: fixed;
			top: 0;
			left: 0;
			bottom: 0;
			width: min(20rem, 85vw);
			background-color: var(--color-background);
			z-index: 200;
			padding: var(--size-4);
			overflow-y: auto;
			transform: translateX(-100%);
			transition: transform 0.25s var(--ease-2);
		}

		.sidebar-drawer.open {
			transform: translateX(0);
		}

		.sidebar-drawer :global(.sidebar) {
			position: static;
			max-height: none;
		}

		.drawer-backdrop {
			display: block;
			position: fixed;
			inset: 0;
			background-color: rgba(0, 0, 0, 0.4);
			z-index: 199;
		}
	}
</style>
