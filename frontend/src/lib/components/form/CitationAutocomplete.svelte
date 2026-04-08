<script lang="ts">
	import client from '$lib/api/client';
	import { createDebouncedSearch, formatCitationResult } from './search-helpers';
	import DropdownHeader from './DropdownHeader.svelte';
	import DropdownItem from './DropdownItem.svelte';
	import DropdownSearchInput from './DropdownSearchInput.svelte';

	let {
		oncomplete,
		oncancel,
		onback
	}: {
		oncomplete: (linkText: string) => void;
		oncancel: () => void;
		onback: () => void;
	} = $props();

	// -----------------------------------------------------------------------
	// Types
	// -----------------------------------------------------------------------

	type CitationSourceResult = {
		id: number;
		name: string;
		source_type: string;
		author: string;
		publisher: string;
		year: number | null;
		isbn: string | null;
	};

	type SourceType = 'book' | 'magazine' | 'web';
	type CiteStage = 'search' | 'create' | 'locator';

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let stage = $state<CiteStage>('search');

	// Search
	let searchQuery = $state('');
	let searchResults = $state<CitationSourceResult[]>([]);
	let activeIndex = $state(-1);
	let searchInputEl: HTMLInputElement | undefined = $state();

	// Create
	let createName = $state('');
	let createType = $state<SourceType>('book');
	let createAuthor = $state('');
	let createUrl = $state('');
	let createError = $state('');
	let createSubmitting = $state(false);
	let createNameInputEl: HTMLInputElement | undefined = $state();

	// Locator
	let selectedSourceId = $state<number | null>(null);
	let selectedSourceName = $state('');
	let locator = $state('');
	let locatorInputEl: HTMLInputElement | undefined = $state();
	let locatorSubmitting = $state(false);
	let locatorError = $state('');

	// -----------------------------------------------------------------------
	// Search
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
			searchResults = results;
		},
		100
	);

	function handleSearchInput(e: Event) {
		searchQuery = (e.currentTarget as HTMLInputElement).value;
		activeIndex = -1;
		debouncedSearch.search(searchQuery);
	}

	// The "Create new" item sits after the search results
	let createNewIndex = $derived(searchResults.length);
	let showCreateNew = $derived(searchQuery.trim().length > 0);
	let totalItems = $derived(searchResults.length + (showCreateNew ? 1 : 0));

	function selectSource(source: CitationSourceResult) {
		debouncedSearch.cancel();
		selectedSourceId = source.id;
		selectedSourceName = source.name;
		locator = '';
		locatorError = '';
		stage = 'locator';
		requestAnimationFrame(() => locatorInputEl?.focus());
	}

	function startCreate() {
		debouncedSearch.cancel();
		createName = searchQuery;
		createType = 'book';
		createAuthor = '';
		createUrl = '';
		createError = '';
		stage = 'create';
	}

	// Auto-focus the primary input when entering search or create stage
	$effect(() => {
		if (stage === 'search') {
			requestAnimationFrame(() => searchInputEl?.focus());
		} else if (stage === 'create') {
			requestAnimationFrame(() => createNameInputEl?.focus());
		}
	});

	// -----------------------------------------------------------------------
	// Create
	// -----------------------------------------------------------------------

	let showUrlField = $derived(createType === 'web');
	let showAuthorField = $derived(createType === 'book' || createType === 'magazine');

	async function submitCreate() {
		if (!createName.trim()) {
			createError = 'Name is required.';
			return;
		}
		if (createType === 'web' && !createUrl.trim()) {
			createError = 'URL is required for web sources.';
			return;
		}

		createSubmitting = true;
		createError = '';

		const { data, error } = await client.POST('/api/citation-sources/', {
			body: {
				name: createName,
				source_type: createType,
				author: showAuthorField ? createAuthor : '',
				publisher: '',
				date_note: '',
				description: '',
				url: showUrlField && createUrl.trim() ? createUrl : null,
				link_label: '',
				link_type: 'homepage'
			}
		});
		createSubmitting = false;

		if (error) {
			createError = typeof error === 'string' ? error : 'Failed to create source.';
			return;
		}

		selectedSourceId = data.id;
		selectedSourceName = data.name;
		locator = '';
		locatorError = '';
		stage = 'locator';
		requestAnimationFrame(() => locatorInputEl?.focus());
	}

	function goBackToSearch() {
		stage = 'search';
		requestAnimationFrame(() => searchInputEl?.focus());
	}

	// -----------------------------------------------------------------------
	// Locator
	// -----------------------------------------------------------------------

	async function submitLocator() {
		if (selectedSourceId === null) return;

		locatorSubmitting = true;
		locatorError = '';

		const { data, error } = await client.POST('/api/citation-instances/', {
			body: { citation_source_id: selectedSourceId, locator }
		});
		locatorSubmitting = false;

		if (error) {
			locatorError = 'Failed to create citation.';
			return;
		}

		oncomplete(`[[cite:${data.id}]]`);
	}

	function skipLocator() {
		locator = '';
		submitLocator();
	}

	// -----------------------------------------------------------------------
	// Keyboard navigation
	// -----------------------------------------------------------------------

	function handleSearchKeydown(e: KeyboardEvent) {
		switch (e.key) {
			case 'ArrowDown':
				e.preventDefault();
				activeIndex = Math.min(activeIndex + 1, totalItems - 1);
				scrollActiveIntoView();
				break;
			case 'ArrowUp':
				e.preventDefault();
				activeIndex = Math.max(activeIndex - 1, -1);
				scrollActiveIntoView();
				break;
			case 'Enter':
				e.preventDefault();
				if (activeIndex >= 0 && activeIndex < searchResults.length) {
					selectSource(searchResults[activeIndex]);
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

	function handleCreateKeydown(e: KeyboardEvent) {
		if (e.key === 'Escape') {
			e.preventDefault();
			oncancel();
		}
	}

	function handleLocatorKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter') {
			e.preventDefault();
			submitLocator();
		} else if (e.key === 'Escape') {
			e.preventDefault();
			oncancel();
		} else if (e.key === 'Backspace' && !locator) {
			e.preventDefault();
			goBackToSearch();
		} else if (e.key === 'ArrowLeft' && locatorInputEl?.selectionStart === 0) {
			e.preventDefault();
			goBackToSearch();
		}
	}

	function scrollActiveIntoView() {
		requestAnimationFrame(() => {
			const container = searchInputEl?.closest('.citation-autocomplete');
			container?.querySelector('[data-active="true"]')?.scrollIntoView({ block: 'nearest' });
		});
	}
</script>

<div class="citation-autocomplete">
	{#if stage === 'search'}
		<DropdownHeader {onback}>Citation</DropdownHeader>
		<DropdownSearchInput
			placeholder="Search sources..."
			value={searchQuery}
			oninput={handleSearchInput}
			onkeydown={handleSearchKeydown}
			bind:inputRef={searchInputEl}
		/>
		<div class="results-list">
			{#each searchResults as source, i (source.id)}
				<DropdownItem
					active={i === activeIndex}
					onselect={() => selectSource(source)}
					onhover={() => (activeIndex = i)}
				>
					<span class="item-label">{formatCitationResult(source)}</span>
					<span class="item-desc">{source.source_type}</span>
				</DropdownItem>
			{/each}
			{#if showCreateNew}
				<DropdownItem
					active={activeIndex === createNewIndex}
					onselect={() => startCreate()}
					onhover={() => (activeIndex = createNewIndex)}
				>
					<span class="item-label create-new">+ Create "{searchQuery}"</span>
				</DropdownItem>
			{/if}
			{#if !searchResults.length && !searchQuery.trim()}
				<div class="no-results">Type to search sources...</div>
			{:else if !searchResults.length && searchQuery.trim()}
				<div class="no-results">No matches</div>
			{/if}
		</div>
	{:else if stage === 'create'}
		<DropdownHeader onback={goBackToSearch}>New source</DropdownHeader>
		<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
		<form
			class="create-form"
			onsubmit={(e) => {
				e.preventDefault();
				submitCreate();
			}}
			onkeydown={handleCreateKeydown}
		>
			<div class="type-chips">
				{#each ['book', 'magazine', 'web'] as t (t)}
					<button
						type="button"
						class="type-chip"
						class:selected={createType === t}
						onpointerdown={(e) => {
							e.preventDefault();
							createType = t as SourceType;
						}}
					>
						{t}
					</button>
				{/each}
			</div>
			<input
				bind:this={createNameInputEl}
				type="text"
				class="form-input"
				placeholder="Name"
				bind:value={createName}
			/>
			{#if showAuthorField}
				<input
					type="text"
					class="form-input"
					placeholder="Author (optional)"
					bind:value={createAuthor}
				/>
			{/if}
			{#if showUrlField}
				<input type="url" class="form-input" placeholder="URL" bind:value={createUrl} />
			{/if}
			{#if createError}
				<div class="form-error">{createError}</div>
			{/if}
			<button type="submit" class="submit-btn" disabled={createSubmitting}>
				{createSubmitting ? 'Creating...' : 'Create & cite'}
			</button>
		</form>
	{:else if stage === 'locator'}
		<DropdownHeader>Citing: {selectedSourceName}</DropdownHeader>
		<div class="locator-form">
			<input
				bind:this={locatorInputEl}
				type="text"
				class="form-input"
				aria-label="Citation locator"
				placeholder="p. 42, Chapter 3, timestamp..."
				bind:value={locator}
				onkeydown={handleLocatorKeydown}
			/>
			{#if locatorError}
				<div class="form-error">{locatorError}</div>
			{/if}
			<div class="locator-actions">
				<button
					class="submit-btn"
					disabled={locatorSubmitting}
					onpointerdown={(e) => {
						e.preventDefault();
						submitLocator();
					}}
				>
					{locatorSubmitting ? 'Inserting...' : 'Insert'}
				</button>
				<button
					class="skip-btn"
					disabled={locatorSubmitting}
					onpointerdown={(e) => {
						e.preventDefault();
						skipLocator();
					}}
				>
					Skip
				</button>
			</div>
		</div>
	{/if}
</div>

<style>
	/* ----- Item content (inside DropdownItem) ----- */

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

	.create-new {
		color: var(--color-text-muted);
		font-style: italic;
	}

	/* ----- Results list ----- */

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

	/* ----- Form inputs (create + locator) ----- */

	.form-input {
		width: 100%;
		padding: var(--size-1) var(--size-2);
		font-size: var(--font-size-1);
		font-family: inherit;
		background-color: var(--color-input-bg);
		color: var(--color-text-primary);
		border: 1px solid var(--color-input-border);
		border-radius: var(--radius-2);
	}

	.form-input:focus {
		outline: none;
		border-color: var(--color-input-focus);
		box-shadow: 0 0 0 2px var(--color-input-focus-ring);
	}

	/* ----- Create form ----- */

	.create-form {
		padding: var(--size-2) var(--size-3);
		display: flex;
		flex-direction: column;
		gap: var(--size-2);
	}

	.type-chips {
		display: flex;
		gap: var(--size-1);
	}

	.type-chip {
		padding: var(--size-1) var(--size-2);
		font-size: var(--font-size-0);
		font-family: inherit;
		border: 1px solid var(--color-input-border);
		border-radius: var(--radius-2);
		background-color: var(--color-input-bg);
		color: var(--color-text-primary);
		cursor: pointer;
		text-transform: capitalize;
	}

	.type-chip.selected {
		background-color: var(--color-input-focus-ring);
		border-color: var(--color-input-focus);
	}

	.form-error {
		color: var(--color-danger, #c00);
		font-size: var(--font-size-0);
	}

	.submit-btn {
		padding: var(--size-1) var(--size-2);
		font-size: var(--font-size-1);
		font-family: inherit;
		border: 1px solid var(--color-input-border);
		border-radius: var(--radius-2);
		background-color: var(--color-input-focus-ring);
		color: var(--color-text-primary);
		cursor: pointer;
	}

	.submit-btn:hover:not(:disabled) {
		border-color: var(--color-input-focus);
	}

	.submit-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	/* ----- Locator ----- */

	.locator-form {
		padding: var(--size-2) var(--size-3);
		display: flex;
		flex-direction: column;
		gap: var(--size-2);
	}

	.locator-actions {
		display: flex;
		gap: var(--size-2);
		align-items: center;
	}

	.skip-btn {
		background: none;
		border: none;
		color: var(--color-text-muted);
		font-size: var(--font-size-0);
		cursor: pointer;
		text-decoration: underline;
		padding: 0;
	}

	.skip-btn:hover {
		color: var(--color-text-primary);
	}

	.skip-btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}
</style>
