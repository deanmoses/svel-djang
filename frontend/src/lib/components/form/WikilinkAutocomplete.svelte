<script lang="ts">
	import { onDestroy, tick } from 'svelte';
	import { fetchLinkTypes, searchLinkTargets } from '$lib/api/link-types';
	import type { LinkType, LinkTarget } from '$lib/api/link-types';
	import { formatLinkText } from './wikilink-helpers';
	import { createDebouncedSearch } from './search-helpers';
	import CitationAutocomplete from './CitationAutocomplete.svelte';
	import DropdownHeader from './DropdownHeader.svelte';
	import DropdownItem from './DropdownItem.svelte';
	import DropdownSearchInput from './DropdownSearchInput.svelte';

	let {
		oncomplete,
		oncancel,
		onfocusreturn
	}: {
		oncomplete: (linkText: string) => void;
		oncancel: () => void;
		onfocusreturn?: () => void;
	} = $props();

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let stage = $state<'type' | 'search' | 'cite'>('type');

	// Type picker
	let linkTypes = $state<LinkType[]>([]);
	let typeIndex = $state(0);

	// Search
	let selectedType = $state<LinkType | null>(null);
	let searchQuery = $state('');
	let searchResults = $state<LinkTarget[]>([]);
	let searchIndex = $state(-1);
	let searchInputEl: HTMLInputElement | undefined = $state();
	let debouncedSearch: ReturnType<typeof createDebouncedSearch<LinkTarget>> | null = null;

	// ARIA — per-instance IDs for combobox pattern
	const uid = Math.random().toString(36).slice(2, 8);
	const listboxId = `wl-results-${uid}`;
	function resultItemId(ref: string) {
		return `wl-result-${uid}-${ref}`;
	}
	let activeDescendant = $derived(
		searchIndex >= 0 && searchIndex < searchResults.length
			? resultItemId(searchResults[searchIndex].ref)
			: undefined
	);

	onDestroy(() => debouncedSearch?.cancel());

	// Eagerly prefetch link types so they're ready before the user types [[.
	// Cached at module level, so this is a no-op after first call.
	fetchLinkTypes()
		.then((types) => {
			linkTypes = types;
		})
		.catch(() => {
			// Degraded state: type picker will be empty
		});

	// -----------------------------------------------------------------------
	// Type picker stage
	// -----------------------------------------------------------------------

	function selectType(lt: LinkType) {
		selectedType = lt;
		if (lt.flow === 'custom' && lt.name === 'cite') {
			stage = 'cite';
		} else {
			searchQuery = '';
			searchResults = [];
			searchIndex = -1;
			// Create a fresh debounced search bound to this type
			debouncedSearch = createDebouncedSearch<LinkTarget>(
				async (q: string) => {
					try {
						const response = await searchLinkTargets(lt.name, q);
						return response.results;
					} catch {
						return [];
					}
				},
				(results) => {
					searchResults = results;
				}
			);
			stage = 'search';
			tick().then(() => searchInputEl?.focus());
			debouncedSearch.search('');
		}
	}

	// -----------------------------------------------------------------------
	// Search stage
	// -----------------------------------------------------------------------

	function handleSearchInput(e: Event) {
		searchQuery = (e.currentTarget as HTMLInputElement).value;
		searchIndex = -1;
		debouncedSearch?.search(searchQuery);
	}

	function selectResult(target: LinkTarget) {
		if (!selectedType) return;
		oncomplete(formatLinkText(selectedType.name, target.ref));
	}

	function goBackToTypePicker() {
		debouncedSearch?.cancel();
		debouncedSearch = null;
		stage = 'type';
		selectedType = null;
		searchQuery = '';
		searchResults = [];
		searchIndex = -1;
		// Preserve typeIndex so the user returns to the type they selected
		onfocusreturn?.();
	}

	// -----------------------------------------------------------------------
	// Keyboard navigation
	// -----------------------------------------------------------------------

	function handleTypeKeydown(e: KeyboardEvent) {
		switch (e.key) {
			case 'ArrowDown':
				e.preventDefault();
				typeIndex = Math.min(typeIndex + 1, linkTypes.length - 1);
				break;
			case 'ArrowUp':
				e.preventDefault();
				typeIndex = Math.max(typeIndex - 1, 0);
				break;
			case 'Enter':
			case 'ArrowRight':
				e.preventDefault();
				if (typeIndex >= 0 && typeIndex < linkTypes.length) {
					selectType(linkTypes[typeIndex]);
				}
				break;
			case 'Escape':
				e.preventDefault();
				oncancel();
				break;
			case 'Backspace':
			case 'ArrowLeft':
				// Browser will delete a [ / move cursor — close since trigger is being left
				oncancel();
				break;
		}
	}

	function handleSearchKeydown(e: KeyboardEvent) {
		switch (e.key) {
			case 'ArrowDown':
				e.preventDefault();
				searchIndex = Math.min(searchIndex + 1, searchResults.length - 1);
				scrollActiveIntoView();
				break;
			case 'ArrowUp':
				e.preventDefault();
				searchIndex = Math.max(searchIndex - 1, -1);
				scrollActiveIntoView();
				break;
			case 'Enter':
				e.preventDefault();
				if (searchIndex >= 0 && searchIndex < searchResults.length) {
					selectResult(searchResults[searchIndex]);
				}
				break;
			case 'Escape':
				e.preventDefault();
				debouncedSearch?.cancel();
				oncancel();
				break;
			case 'Backspace':
				if (!searchQuery) {
					e.preventDefault();
					goBackToTypePicker();
				}
				break;
			case 'ArrowLeft':
				if (searchInputEl && searchInputEl.selectionStart === 0) {
					e.preventDefault();
					goBackToTypePicker();
				}
				break;
		}
	}

	function scrollActiveIntoView() {
		tick().then(() => {
			const el = searchInputEl?.closest('.wikilink-autocomplete');
			el?.querySelector('[data-active="true"]')?.scrollIntoView({ block: 'nearest' });
		});
	}

	// -----------------------------------------------------------------------
	// Public: let parent forward keydown events from the textarea
	// -----------------------------------------------------------------------

	export function handleExternalKeydown(e: KeyboardEvent) {
		if (stage === 'type') {
			handleTypeKeydown(e);
		}
	}
</script>

<div class="wikilink-autocomplete">
	{#if stage === 'type'}
		<DropdownHeader>Insert link</DropdownHeader>
		{#each linkTypes as lt, i (lt.name)}
			<DropdownItem
				active={i === typeIndex}
				onselect={() => selectType(lt)}
				onhover={() => (typeIndex = i)}
			>
				<span class="item-label">{lt.label}</span>
				<span class="item-desc">{lt.description}</span>
			</DropdownItem>
		{/each}
	{:else if stage === 'search'}
		<DropdownHeader onback={goBackToTypePicker}>{selectedType?.label}</DropdownHeader>
		<DropdownSearchInput
			placeholder="Search {selectedType?.label ?? ''}..."
			value={searchQuery}
			oninput={handleSearchInput}
			onkeydown={handleSearchKeydown}
			bind:inputRef={searchInputEl}
			{activeDescendant}
			{listboxId}
		/>
		<div class="results-list" role="listbox" id={listboxId}>
			{#each searchResults as target, i (target.ref)}
				<DropdownItem
					id={resultItemId(target.ref)}
					active={i === searchIndex}
					onselect={() => selectResult(target)}
					onhover={() => (searchIndex = i)}
				>
					<span class="item-label">{target.label}</span>
				</DropdownItem>
			{:else}
				<div class="no-results">No matches</div>
			{/each}
		</div>
	{:else if stage === 'cite'}
		<CitationAutocomplete
			oncomplete={(linkText) => oncomplete(linkText)}
			oncancel={() => oncancel()}
			onback={() => goBackToTypePicker()}
		/>
	{/if}
</div>

<style>
	.item-label {
		flex-shrink: 0;
	}

	.item-desc {
		color: var(--color-text-muted);
		font-size: var(--font-size-0);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
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
