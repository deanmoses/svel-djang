<script lang="ts" generics="T extends { slug: string; name: string; aliases?: string[] }">
	import type { Snippet } from 'svelte';
	import PageHeader from './PageHeader.svelte';
	import SearchBox from './SearchBox.svelte';
	import NoResultsCreatePrompt from './NoResultsCreatePrompt.svelte';
	import EditSectionMenu from './EditSectionMenu.svelte';
	import type { EditSectionMenuItem } from './edit-section-menu';
	import { SEARCH_THRESHOLD } from './grid/search-threshold';
	import { auth } from '$lib/auth.svelte';
	import { normalizeText, resolveHref } from '$lib/utils';
	import { pageTitle } from '$lib/constants';
	import { CATALOG_META, type CatalogEntityKey } from '$lib/api/catalog-meta';

	interface Props {
		/** Catalog entity key. Title, basePath, singular/plural labels, and endpoint are derived from CATALOG_META. */
		catalogKey: CatalogEntityKey;
		subtitle?: string;
		items: T[];
		loading: boolean;
		error: string | null;
		rowStyle?: string;
		headerSnippet?: Snippet;
		rowSnippet?: Snippet<[item: T]>;
		/**
		 * When true, the page renders create affordances (auth-gated) pointing
		 * at `/{entity_type_plural}/new`:
		 *  - below SEARCH_THRESHOLD: a "+ New {entity}" link in the header
		 *  - at/above the threshold: a SearchBox + inline filter; zero-match
		 *    renders NoResultsCreatePrompt with the typed query.
		 */
		canCreate?: boolean;
	}

	let {
		catalogKey,
		subtitle,
		items,
		loading,
		error,
		rowStyle,
		headerSnippet,
		rowSnippet,
		canCreate = false
	}: Props = $props();

	let meta = $derived(CATALOG_META[catalogKey]);
	let title = $derived(meta.label_plural);
	let basePath = $derived(`/${meta.entity_type_plural}`);
	let entityLabel = $derived(meta.label_plural.toLowerCase());
	let singularLabel = $derived(meta.label.toLowerCase());
	let singularTitle = $derived(meta.label);
	let endpoint = $derived(`/api${basePath}/`);
	let createHref = $derived(canCreate ? `${basePath}/new` : undefined);

	let searchQuery = $state('');

	$effect(() => {
		void auth.load();
	});

	let showSearch = $derived(items.length >= SEARCH_THRESHOLD || searchQuery.trim() !== '');

	let filteredItems = $derived.by(() => {
		const q = normalizeText(searchQuery.trim());
		if (!q) return items;
		// Per RecordCreateDelete.md:115, aliases must count as results for the
		// duplicate-prevention gate — otherwise a search for an existing alias
		// would wrongly trigger NoResultsCreatePrompt.
		return items.filter((item) => {
			if (normalizeText(item.name).includes(q)) return true;
			return (item.aliases ?? []).some((alias) => normalizeText(alias).includes(q));
		});
	});

	let actionItems: EditSectionMenuItem[] = $derived(
		createHref
			? [{ key: 'new', label: `+ New ${singularTitle}`, href: resolveHref(createHref) }]
			: []
	);

	let showActionMenu = $derived(
		actionItems.length > 0 && auth.isAuthenticated && !loading && !error
	);
</script>

<svelte:head>
	<title>{pageTitle(title)}</title>
	<link rel="preload" as="fetch" href={endpoint} crossorigin="anonymous" />
</svelte:head>

<article>
	<div class="page-head">
		<div class="page-head-title">
			<PageHeader {title} --page-header-title-mb="0">
				{#if headerSnippet}
					{@render headerSnippet()}
				{:else if subtitle}
					<p class="subtitle">{subtitle}</p>
				{/if}
			</PageHeader>
		</div>
		{#if showActionMenu}
			<div class="page-actions">
				<EditSectionMenu items={actionItems} />
			</div>
		{/if}
	</div>

	{#if loading}
		<p class="status">Loading...</p>
	{:else if error}
		<p class="status error">Failed to load {entityLabel}.</p>
	{:else}
		{#if showSearch}
			<SearchBox bind:value={searchQuery} placeholder={`Search ${entityLabel}...`} />
		{/if}

		{#if items.length === 0}
			<p class="status">No {entityLabel} found.</p>
		{:else if filteredItems.length === 0}
			{#if createHref && auth.isAuthenticated && searchQuery.trim() !== ''}
				<NoResultsCreatePrompt
					entityLabel={singularLabel}
					query={searchQuery.trim()}
					createHref={`${createHref}?name=${encodeURIComponent(searchQuery.trim())}`}
				/>
			{:else}
				<p class="status">No matching {entityLabel}.</p>
			{/if}
		{:else}
			<ul class="item-list">
				{#each filteredItems as item (item.slug)}
					<li>
						<a href={resolveHref(`${basePath}/${item.slug}`)} class="item-row" style={rowStyle}>
							{#if rowSnippet}
								{@render rowSnippet(item)}
							{:else}
								<span class="item-name">{item.name}</span>
							{/if}
						</a>
					</li>
				{/each}
			</ul>
		{/if}
	{/if}
</article>

<style>
	article {
		max-width: 48rem;
	}

	.subtitle {
		font-size: var(--font-size-2);
		color: var(--color-text-muted);
		margin-top: var(--size-2);
	}

	.page-head {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		gap: var(--size-4);
	}

	.page-head-title {
		flex: 1;
		min-width: 0;
	}

	.page-actions {
		flex-shrink: 0;
	}

	.item-list {
		list-style: none;
		padding: 0;
	}

	.item-row {
		display: flex;
		align-items: baseline;
		padding: var(--size-3) 0;
		border-bottom: 1px solid var(--color-border-soft);
		text-decoration: none;
		color: var(--color-text-primary);
	}

	.item-row:hover {
		color: var(--color-accent);
	}

	.item-name {
		font-size: var(--font-size-2);
		color: inherit;
		font-weight: 500;
	}

	.status {
		font-size: var(--font-size-2);
		color: var(--color-text-muted);
		padding: var(--size-8) 0;
		text-align: center;
	}

	.status.error {
		color: var(--color-error);
	}
</style>
