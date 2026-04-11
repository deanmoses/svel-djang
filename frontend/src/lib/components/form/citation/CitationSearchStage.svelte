<script lang="ts">
	import client from '$lib/api/client';
	import { createDebouncedSearch, formatCitationResult } from '../search-helpers';
	import {
		suppressChildResults,
		detectSourceFromUrl,
		findMatchingChild,
		createChildSource,
		parentContextFromSource,
		type CitationSourceResult,
		type ChildSource
	} from './citation-types';
	import DropdownHeader from '../DropdownHeader.svelte';
	import DropdownItem from '../DropdownItem.svelte';
	import DropdownSearchInput from '../DropdownSearchInput.svelte';

	let {
		onsourceselected,
		onsourceidentified,
		onsourcecreatestarted,
		oncancel,
		onback
	}: {
		onsourceselected: (source: CitationSourceResult, prefillIdentifier?: string) => void;
		onsourceidentified: (child: {
			sourceId: number;
			sourceName: string;
			skipLocator: boolean;
		}) => void;
		onsourcecreatestarted: (prefillName: string) => void;
		oncancel: () => void;
		onback: () => void;
	} = $props();

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let searchQuery = $state('');
	let searchResults = $state<CitationSourceResult[]>([]);
	let activeIndex = $state(-1);
	let searchInputEl: HTMLInputElement | undefined = $state();
	let resultsListEl: HTMLDivElement | undefined = $state();
	let resolving = $state(false);
	let resolveError = $state(false);
	let resolveGeneration = 0;

	// ARIA — per-instance IDs for combobox pattern
	const uid = Math.random().toString(36).slice(2, 8);
	const listboxId = `cite-search-${uid}`;
	function itemId(key: string | number) {
		return `cite-search-item-${uid}-${key}`;
	}

	// -----------------------------------------------------------------------
	// URL detection (synchronous, runs on every input change)
	// -----------------------------------------------------------------------

	let detected = $derived(detectSourceFromUrl(searchQuery));

	// -----------------------------------------------------------------------
	// Debounced search
	// -----------------------------------------------------------------------

	const debouncedSearch = createDebouncedSearch<CitationSourceResult>(
		async (q: string) => {
			if (!q.trim()) return [];
			const { data } = await client.GET('/api/citation-sources/search/', {
				params: { query: { q } }
			});
			return (data ?? []) as CitationSourceResult[];
		},
		(results) => {
			searchResults = suppressChildResults(results);
		},
		100
	);

	function handleSearchInput(e: Event) {
		searchQuery = (e.currentTarget as HTMLInputElement).value;
		activeIndex = -1;
		if (resolving || resolveError) {
			resolving = false;
			resolveError = false;
			resolveGeneration++;
		}
		debouncedSearch.search(searchQuery);
	}

	// -----------------------------------------------------------------------
	// Item index math
	// -----------------------------------------------------------------------

	let showCreateNew = $derived(searchQuery.trim().length > 0);
	let resultsStartIndex = $derived(detected ? 1 : 0);
	let createNewIndex = $derived(resultsStartIndex + searchResults.length);
	let totalItems = $derived((detected ? 1 : 0) + searchResults.length + (showCreateNew ? 1 : 0));
	let activeDescendant = $derived.by(() => {
		if (activeIndex < 0 || activeIndex >= totalItems) return undefined;
		if (detected && activeIndex === 0) return itemId(`detected-${detected.machineId}`);
		if (activeIndex >= resultsStartIndex && activeIndex < createNewIndex)
			return itemId(searchResults[activeIndex - resultsStartIndex].id);
		if (activeIndex === createNewIndex) return itemId('create');
		return undefined;
	});

	// -----------------------------------------------------------------------
	// Actions
	// -----------------------------------------------------------------------

	$effect(() => {
		if (searchInputEl) {
			searchInputEl.focus();
		}
	});

	$effect(() => {
		if (activeIndex < 0 || !resultsListEl) return;
		resultsListEl.querySelector('[data-active="true"]')?.scrollIntoView({ block: 'nearest' });
	});

	function selectSource(source: CitationSourceResult) {
		debouncedSearch.cancel();
		onsourceselected(source);
	}

	/**
	 * Fully resolve a recognized URL to a citable source.
	 *
	 * 1. Find the abstract parent (e.g. "IPDB") by searching for the source name.
	 * 2. Look up existing children matching the extracted identifier.
	 * 3. If a child exists, dispatch source_identified directly.
	 * 4. If not, create the child source, then dispatch source_identified.
	 * 5. On failure, fall back to source_selected (lands on the identify stage).
	 */
	async function resolveRecognizedUrl() {
		if (!detected || resolving) return;
		debouncedSearch.cancel();
		resolving = true;
		const gen = ++resolveGeneration;
		const { sourceName, machineId } = detected;

		try {
			// Step 1: Find abstract parent
			const { data: searchData } = await client.GET('/api/citation-sources/search/', {
				params: { query: { q: sourceName } }
			});
			if (gen !== resolveGeneration) return;

			const results = (searchData ?? []) as CitationSourceResult[];
			const parent = results.find((r) => r.is_abstract);

			if (!parent) {
				resolving = false;
				resolveError = true;
				console.warn(`Citation search: no abstract parent found for "${sourceName}"`);
				return;
			}

			// Step 2: Look up existing children
			const { data: childrenData, error: childrenError } = await client.GET(
				'/api/citation-sources/{source_id}/children/',
				{ params: { path: { source_id: parent.id }, query: { q: machineId } } }
			);
			if (gen !== resolveGeneration) return;

			if (!childrenError && childrenData) {
				const children = childrenData as ChildSource[];
				const match = findMatchingChild(
					children,
					parent.source_type,
					parent.identifier_key || null,
					machineId
				);

				if (match) {
					// Step 3: Existing child found
					resolving = false;
					onsourceidentified({
						sourceId: match.id,
						sourceName: match.name,
						skipLocator: match.skip_locator
					});
					return;
				}
			}

			// Step 4: No existing child — create one
			const parentCtx = parentContextFromSource(parent);
			const result = await createChildSource(client, parentCtx, machineId);
			if (gen !== resolveGeneration) return;

			if (!result.ok) {
				// Fall back to identify stage with identifier pre-filled
				resolving = false;
				onsourceselected(parent, machineId);
				return;
			}

			resolving = false;
			onsourceidentified({
				sourceId: result.data.id,
				sourceName: result.data.name,
				skipLocator: result.data.skip_locator
			});
		} catch (err) {
			if (gen === resolveGeneration) {
				resolving = false;
				resolveError = true;
				console.warn('Citation search: failed to resolve recognized URL', err);
			}
		}
	}

	function startCreate() {
		debouncedSearch.cancel();
		onsourcecreatestarted(searchQuery);
	}

	// -----------------------------------------------------------------------
	// Keyboard navigation
	// -----------------------------------------------------------------------

	function handleKeydown(e: KeyboardEvent) {
		switch (e.key) {
			case 'ArrowDown':
				e.preventDefault();
				activeIndex = Math.min(activeIndex + 1, totalItems - 1);
				break;
			case 'ArrowUp':
				e.preventDefault();
				activeIndex = Math.max(activeIndex - 1, -1);
				break;
			case 'Enter':
				e.preventDefault();
				if (activeIndex < 0) break;
				if (detected && activeIndex === 0) {
					resolveRecognizedUrl();
				} else if (activeIndex >= resultsStartIndex && activeIndex < createNewIndex) {
					selectSource(searchResults[activeIndex - resultsStartIndex]);
				} else if (showCreateNew && activeIndex === createNewIndex) {
					startCreate();
				}
				break;
			case 'Escape':
				e.preventDefault();
				oncancel();
				break;
			case 'Backspace':
				if (!searchQuery) {
					e.preventDefault();
					onback();
				}
				break;
			case 'ArrowLeft':
				if (searchInputEl && searchInputEl.selectionStart === 0) {
					e.preventDefault();
					onback();
				}
				break;
		}
	}
</script>

<DropdownHeader {onback}>Citation</DropdownHeader>
<DropdownSearchInput
	placeholder="Search sources..."
	value={searchQuery}
	oninput={handleSearchInput}
	onkeydown={handleKeydown}
	bind:inputRef={searchInputEl}
	{activeDescendant}
	{listboxId}
/>
<div class="results-list" role="listbox" id={listboxId} bind:this={resultsListEl}>
	{#if detected}
		<DropdownItem
			id={itemId(`detected-${detected.machineId}`)}
			active={activeIndex === 0}
			onselect={resolveRecognizedUrl}
			onhover={() => (activeIndex = 0)}
		>
			<span class="item-label">{detected.sourceName} Machine {detected.machineId}</span>
			{#if resolving}
				<span class="item-desc">Loading…</span>
			{:else if resolveError}
				<span class="item-desc item-error">Not found</span>
			{/if}
		</DropdownItem>
	{/if}
	{#each searchResults as source, i (source.id)}
		<DropdownItem
			id={itemId(source.id)}
			active={i + resultsStartIndex === activeIndex}
			onselect={() => selectSource(source)}
			onhover={() => (activeIndex = i + resultsStartIndex)}
		>
			<span class="item-label">{formatCitationResult(source)}</span>
			<span class="item-desc">{source.source_type}</span>
		</DropdownItem>
	{/each}
	{#if showCreateNew}
		<DropdownItem
			id={itemId('create')}
			active={activeIndex === createNewIndex}
			onselect={startCreate}
			onhover={() => (activeIndex = createNewIndex)}
		>
			<span class="item-label create-new">+ Create "{searchQuery}"</span>
		</DropdownItem>
	{/if}
	{#if !detected && !searchResults.length && !searchQuery.trim()}
		<div class="no-results">Type to search sources…</div>
	{:else if !detected && !searchResults.length && searchQuery.trim()}
		<div class="no-results">No matches</div>
	{/if}
</div>

<style>
	.item-label {
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.item-desc {
		color: var(--color-text-muted);
		font-size: var(--font-size-0);
		flex-shrink: 0;
	}

	.item-error {
		color: var(--color-danger, #c00);
	}

	.create-new {
		color: var(--color-text-muted);
		font-style: italic;
	}

	.results-list {
		max-height: 14rem;
		overflow-y: auto;
	}

	.no-results {
		padding: var(--size-3);
		color: var(--color-text-muted);
		text-align: center;
		font-size: var(--font-size-1);
	}
</style>
