<script lang="ts">
	import FieldGroup from './FieldGroup.svelte';
	import { fetchLinkTypes, searchLinkTargets } from '$lib/api/link-types';
	import type { LinkType, LinkTarget } from '$lib/api/link-types';
	import { detectTrigger, formatLinkText, spliceLink } from './wikilink-helpers';
	import {
		toggleMarker,
		wrapSelection,
		insertLink as insertMdLink,
		pasteLink,
		indentLines,
		listEnter,
		applyResult
	} from './markdown-shortcuts';
	import type { EditResult } from './markdown-shortcuts';

	let {
		label,
		value = $bindable(''),
		id = '',
		rows = 4
	}: {
		label: string;
		value?: string;
		id?: string;
		rows?: number;
	} = $props();

	// -----------------------------------------------------------------------
	// State
	// -----------------------------------------------------------------------

	let textareaEl: HTMLTextAreaElement | undefined = $state();
	let wrapperEl: HTMLDivElement | undefined = $state();
	let mirrorEl: HTMLDivElement | undefined = $state();

	// Dropdown state
	let open = $state(false);
	let stage = $state<'type' | 'search'>('type');
	let triggerStart = $state(-1);
	let dropdownLeft = $state(0);
	let dropdownTop = $state(0);

	// Type picker
	let linkTypes = $state<LinkType[]>([]);
	let typeIndex = $state(-1);

	// Search
	let selectedType = $state<LinkType | null>(null);
	let searchQuery = $state('');
	let searchResults = $state<LinkTarget[]>([]);
	let searchIndex = $state(-1);
	let searchInputEl: HTMLInputElement | undefined = $state();
	let debounceTimer: ReturnType<typeof setTimeout> | undefined;
	let searchGeneration = 0;

	// Prefetch link types on mount so they're cached by the time user types [[
	fetchLinkTypes();

	// -----------------------------------------------------------------------
	// Cursor position via mirror div
	// -----------------------------------------------------------------------

	function getCursorPosition(): { left: number; top: number } {
		if (!textareaEl || !mirrorEl) return { left: 0, top: 0 };

		// Copy textarea styles to mirror
		const computed = window.getComputedStyle(textareaEl);
		mirrorEl.style.fontFamily = computed.fontFamily;
		mirrorEl.style.fontSize = computed.fontSize;
		mirrorEl.style.fontWeight = computed.fontWeight;
		mirrorEl.style.lineHeight = computed.lineHeight;
		mirrorEl.style.padding = computed.padding;
		mirrorEl.style.border = computed.border;
		mirrorEl.style.boxSizing = computed.boxSizing;
		mirrorEl.style.width = textareaEl.offsetWidth + 'px';

		// Render text up to cursor with a marker span
		const text = textareaEl.value.substring(0, textareaEl.selectionStart);
		const escaped = text
			.replace(/&/g, '&amp;')
			.replace(/</g, '&lt;')
			.replace(/>/g, '&gt;')
			.replace(/\n/g, '<br>');
		// eslint-disable-next-line svelte/no-dom-manipulating -- mirror div is not Svelte-managed
		mirrorEl.innerHTML = escaped + '<span data-cursor></span>';

		const cursorSpan = mirrorEl.querySelector('[data-cursor]');
		if (!cursorSpan) return { left: 0, top: 0 };

		const cursorRect = cursorSpan.getBoundingClientRect();
		const textareaRect = textareaEl.getBoundingClientRect();

		let left = cursorRect.left - textareaRect.left + textareaEl.scrollLeft;
		let top = cursorRect.top - textareaRect.top - textareaEl.scrollTop + cursorSpan.clientHeight;
		top = Math.min(top, textareaEl.offsetHeight - 20);

		return { left, top };
	}

	// -----------------------------------------------------------------------
	// Trigger detection
	// -----------------------------------------------------------------------

	function handleInput() {
		if (!textareaEl || open) return;

		const pos = detectTrigger(textareaEl.value, textareaEl.selectionStart);
		if (pos >= 0) {
			triggerStart = pos;
			openTypePicker();
		}
	}

	// -----------------------------------------------------------------------
	// Type picker stage
	// -----------------------------------------------------------------------

	async function openTypePicker() {
		const pos = getCursorPosition();
		dropdownLeft = pos.left;
		dropdownTop = pos.top;

		linkTypes = await fetchLinkTypes();
		typeIndex = 0;
		stage = 'type';
		open = true;
	}

	function selectType(lt: LinkType) {
		selectedType = lt;
		searchQuery = '';
		searchResults = [];
		searchIndex = -1;
		stage = 'search';

		requestAnimationFrame(() => searchInputEl?.focus());
		doSearch('');
	}

	// -----------------------------------------------------------------------
	// Search stage
	// -----------------------------------------------------------------------

	function handleSearchInput(e: Event) {
		searchQuery = (e.currentTarget as HTMLInputElement).value;
		searchIndex = -1;
		clearTimeout(debounceTimer);
		// Immediate fetch for empty query (showing all results), debounced otherwise
		const delay = searchQuery ? 200 : 0;
		debounceTimer = setTimeout(() => doSearch(searchQuery), delay);
	}

	async function doSearch(q: string) {
		if (!selectedType) return;
		const gen = ++searchGeneration;
		const response = await searchLinkTargets(selectedType.name, q);
		if (gen !== searchGeneration) return;
		searchResults = response.results;
	}

	function selectResult(target: LinkTarget) {
		if (!textareaEl || !selectedType || triggerStart < 0) return;
		insertWikilink(formatLinkText(selectedType.name, target.ref));
	}

	// -----------------------------------------------------------------------
	// Wikilink insertion (preserves undo stack)
	// -----------------------------------------------------------------------

	function insertWikilink(linkText: string) {
		if (!textareaEl) return;

		const replaceEnd = textareaEl.selectionStart;
		textareaEl.focus();
		textareaEl.setSelectionRange(triggerStart, replaceEnd);

		if (!document.execCommand('insertText', false, linkText)) {
			const result = spliceLink(textareaEl.value, triggerStart, replaceEnd, linkText);
			textareaEl.value = result.newText;
		}

		value = textareaEl.value;

		const newPos = triggerStart + linkText.length;
		textareaEl.setSelectionRange(newPos, newPos);

		closeDropdown();
	}

	// -----------------------------------------------------------------------
	// Markdown shortcuts
	// -----------------------------------------------------------------------

	function applyAndSync(result: EditResult | null): boolean {
		if (!result || !textareaEl) return false;
		applyResult(textareaEl, result);
		value = textareaEl.value;
		return true;
	}

	function handleTextareaKeydown(e: KeyboardEvent) {
		if (e.isComposing) return;

		// Wikilink dropdown keyboard nav takes priority when open
		if (open && stage === 'type') {
			handleTypeKeydown(e);
			return;
		}
		if (open) return;

		if (!textareaEl) return;
		const { value: v, selectionStart: s, selectionEnd: end } = textareaEl;
		const mod = e.metaKey || e.ctrlKey;

		// Cmd/Ctrl shortcuts
		if (mod && !e.shiftKey) {
			if (e.key === 'b') {
				e.preventDefault();
				applyAndSync(toggleMarker(v, s, end, '**'));
				return;
			}
			if (e.key === 'i') {
				e.preventDefault();
				applyAndSync(toggleMarker(v, s, end, '*'));
				return;
			}
			if (e.key === 'k') {
				e.preventDefault();
				applyAndSync(insertMdLink(v, s, end));
				return;
			}
		}

		// Tab / Shift+Tab
		if (e.key === 'Tab') {
			e.preventDefault();
			applyAndSync(indentLines(v, s, end, e.shiftKey));
			return;
		}

		// Enter — list continuation
		if (e.key === 'Enter' && !mod && !e.shiftKey) {
			const result = listEnter(v, s, end);
			if (result) {
				e.preventDefault();
				applyAndSync(result);
			}
			return;
		}

		// Smart wrapping (`, *, _)
		if (s !== end && (e.key === '`' || e.key === '*' || e.key === '_')) {
			const result = wrapSelection(v, s, end, e.key);
			if (result) {
				e.preventDefault();
				applyAndSync(result);
			}
		}
	}

	function handlePaste(e: ClipboardEvent) {
		if (!textareaEl) return;
		const { value: v, selectionStart: s, selectionEnd: end } = textareaEl;
		const pasted = e.clipboardData?.getData('text/plain') ?? '';
		const result = pasteLink(v, s, end, pasted);
		if (result) {
			e.preventDefault();
			applyAndSync(result);
		}
	}

	// -----------------------------------------------------------------------
	// Dropdown management
	// -----------------------------------------------------------------------

	function closeDropdown() {
		open = false;
		stage = 'type';
		selectedType = null;
		searchQuery = '';
		searchResults = [];
		typeIndex = -1;
		searchIndex = -1;
		triggerStart = -1;
		clearTimeout(debounceTimer);
	}

	// Click outside to close
	$effect(() => {
		if (!open) return;
		function onPointerDown(e: PointerEvent) {
			if (!wrapperEl?.contains(e.target as Node)) {
				closeDropdown();
			}
		}
		document.addEventListener('pointerdown', onPointerDown);
		return () => document.removeEventListener('pointerdown', onPointerDown);
	});

	// Clicking the textarea itself closes the dropdown
	function handleTextareaClick() {
		if (open) closeDropdown();
	}

	// Close on blur, with delay to allow focus to move between textarea and search input
	const BLUR_DELAY_MS = 150;

	function handleTextareaBlur() {
		if (!open || stage !== 'type') return;
		setTimeout(() => {
			if (!searchInputEl?.matches(':focus')) {
				closeDropdown();
			}
		}, BLUR_DELAY_MS);
	}

	function handleSearchBlur() {
		if (!open) return;
		setTimeout(() => {
			if (!textareaEl?.matches(':focus') && !searchInputEl?.matches(':focus')) {
				closeDropdown();
			}
		}, BLUR_DELAY_MS);
	}

	// -----------------------------------------------------------------------
	// Dropdown keyboard navigation
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
				closeDropdown();
				textareaEl?.focus();
				break;
			case 'Backspace':
			case 'ArrowLeft':
				// Browser will delete a [ / move cursor — close since trigger is being left
				closeDropdown();
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
				searchIndex = Math.max(searchIndex - 1, 0);
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
				closeDropdown();
				textareaEl?.focus();
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

	function goBackToTypePicker() {
		stage = 'type';
		selectedType = null;
		searchQuery = '';
		searchResults = [];
		searchIndex = -1;
		typeIndex = 0;
		clearTimeout(debounceTimer);
		requestAnimationFrame(() => {
			textareaEl?.focus();
			// Restore cursor to right after [[
			if (textareaEl && triggerStart >= 0) {
				textareaEl.setSelectionRange(triggerStart + 2, triggerStart + 2);
			}
		});
	}

	function scrollActiveIntoView() {
		requestAnimationFrame(() => {
			wrapperEl?.querySelector('[data-active="true"]')?.scrollIntoView({ block: 'nearest' });
		});
	}
</script>

<div class="markdown-textarea" bind:this={wrapperEl}>
	<FieldGroup {label} {id}>
		{#snippet children(inputId)}
			<textarea
				bind:this={textareaEl}
				id={inputId}
				{rows}
				bind:value
				oninput={handleInput}
				onkeydown={handleTextareaKeydown}
				onpaste={handlePaste}
				onclick={handleTextareaClick}
				onblur={handleTextareaBlur}
			></textarea>
		{/snippet}
	</FieldGroup>

	<!-- Mirror div for cursor position measurement -->
	<div class="cursor-mirror" bind:this={mirrorEl} aria-hidden="true"></div>

	{#if open}
		<div
			class="link-dropdown"
			role="listbox"
			style:left="{dropdownLeft}px"
			style:top="{dropdownTop}px"
		>
			{#if stage === 'type'}
				<div class="dropdown-header">Insert link</div>
				{#each linkTypes as lt, i (lt.name)}
					<div
						role="option"
						tabindex="-1"
						aria-selected={i === typeIndex}
						data-active={i === typeIndex}
						class="dropdown-item"
						class:active={i === typeIndex}
						onpointerdown={(e) => {
							e.preventDefault();
							selectType(lt);
						}}
					>
						<span class="item-label">{lt.label}</span>
						<span class="item-desc">{lt.description}</span>
					</div>
				{/each}
			{:else}
				<div class="dropdown-header">
					<button
						class="back-btn"
						onpointerdown={(e) => {
							e.preventDefault();
							goBackToTypePicker();
						}}
					>
						&larr;
					</button>
					{selectedType?.label}
				</div>
				<div class="search-wrap">
					<input
						bind:this={searchInputEl}
						type="text"
						class="search-input"
						placeholder="Search {selectedType?.label ?? ''}..."
						value={searchQuery}
						oninput={handleSearchInput}
						onkeydown={handleSearchKeydown}
						onblur={handleSearchBlur}
					/>
				</div>
				<div class="results-list">
					{#each searchResults as target, i (target.ref)}
						<div
							role="option"
							tabindex="-1"
							aria-selected={i === searchIndex}
							data-active={i === searchIndex}
							class="dropdown-item"
							class:active={i === searchIndex}
							onpointerdown={(e) => {
								e.preventDefault();
								selectResult(target);
							}}
						>
							<span class="item-label">{target.label}</span>
						</div>
					{:else}
						<div class="no-results">
							{searchQuery ? 'No matches' : 'Type to search...'}
						</div>
					{/each}
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.markdown-textarea {
		position: relative;
	}

	/* ----- Mirror (hidden, for cursor measurement) ----- */

	.cursor-mirror {
		position: absolute;
		top: 0;
		left: 0;
		visibility: hidden;
		pointer-events: none;
		white-space: pre-wrap;
		word-wrap: break-word;
		overflow: hidden;
		height: auto;
	}

	/* ----- Dropdown ----- */

	.link-dropdown {
		position: absolute;
		z-index: 10;
		max-width: 24rem;
		max-height: 20rem;
		overflow-y: auto;
		background-color: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: var(--radius-2);
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
	}

	.dropdown-header {
		display: flex;
		align-items: center;
		gap: var(--size-2);
		padding: var(--size-2) var(--size-3);
		font-size: var(--font-size-0);
		font-weight: 600;
		color: var(--color-text-muted);
		border-bottom: 1px solid var(--color-border);
	}

	.back-btn {
		background: none;
		border: none;
		color: var(--color-text-muted);
		cursor: pointer;
		padding: 0;
		font-size: var(--font-size-1);
		line-height: 1;
	}

	.back-btn:hover {
		color: var(--color-text-primary);
	}

	.dropdown-item {
		display: flex;
		align-items: baseline;
		gap: var(--size-2);
		padding: var(--size-2) var(--size-3);
		cursor: pointer;
		font-size: var(--font-size-1);
	}

	.dropdown-item:hover,
	.dropdown-item.active {
		background-color: var(--color-input-focus-ring);
	}

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

	/* ----- Search ----- */

	.search-wrap {
		padding: var(--size-2) var(--size-3);
		border-bottom: 1px solid var(--color-border);
	}

	.search-input {
		width: 100%;
		padding: var(--size-1) var(--size-2);
		font-size: var(--font-size-1);
		font-family: inherit;
		background-color: var(--color-input-bg);
		color: var(--color-text-primary);
		border: 1px solid var(--color-input-border);
		border-radius: var(--radius-2);
	}

	.search-input:focus {
		outline: none;
		border-color: var(--color-input-focus);
		box-shadow: 0 0 0 2px var(--color-input-focus-ring);
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
