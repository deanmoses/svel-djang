<script lang="ts">
	import { onDestroy } from 'svelte';
	import FieldGroup from './FieldGroup.svelte';
	import WikilinkAutocomplete from './WikilinkAutocomplete.svelte';
	import { fetchLinkTypes } from '$lib/api/link-types';
	import { detectTrigger, spliceLink } from './wikilink-helpers';
	import {
		toggleMarker,
		wrapSelection,
		insertLink as insertMdLink,
		pasteLink,
		indentLines,
		listEnter,
		toggleList,
		applyResult
	} from './markdown-shortcuts';
	import type { EditResult } from './markdown-shortcuts';
	import MarkdownToolbar from './MarkdownToolbar.svelte';

	// Prefetch link types on mount so the cache is warm by the time user types [[
	fetchLinkTypes();

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
	let autocompleteEl: HTMLDivElement | undefined = $state();
	let autocompleteRef: WikilinkAutocomplete | undefined = $state();

	// Dropdown state
	let open = $state(false);
	let triggerStart = $state(-1);
	let initialType: string | undefined = $state();
	let dropdownLeft = $state(0);
	let dropdownTop = $state(0);
	let textareaBlurTimeout: ReturnType<typeof setTimeout> | undefined;
	let autocompleteBlurTimeout: ReturnType<typeof setTimeout> | undefined;

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
			openDropdown();
		}
	}

	// -----------------------------------------------------------------------
	// Dropdown management
	// -----------------------------------------------------------------------

	function openDropdown() {
		clearBlurTimeouts();
		const pos = getCursorPosition();
		dropdownLeft = pos.left;
		dropdownTop = pos.top;
		open = true;
	}

	function closeDropdown() {
		clearBlurTimeouts();
		open = false;
		triggerStart = -1;
		initialType = undefined;
	}

	/** Open the link/citation picker from the toolbar (no [[ trigger needed). */
	function openLinkPicker(mode?: string) {
		if (!textareaEl) return;
		triggerStart = textareaEl.selectionStart;
		initialType = mode;
		openDropdown();
	}

	function clearBlurTimeouts() {
		clearTimeout(textareaBlurTimeout);
		clearTimeout(autocompleteBlurTimeout);
		textareaBlurTimeout = undefined;
		autocompleteBlurTimeout = undefined;
	}

	// -----------------------------------------------------------------------
	// Wikilink insertion (preserves undo stack)
	// -----------------------------------------------------------------------

	function insertWikilink(linkText: string) {
		if (!textareaEl) return;

		textareaEl.focus();
		const replaceEnd = textareaEl.selectionStart;
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
		if (open) {
			autocompleteRef?.handleExternalKeydown(e);
			return;
		}

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

	// Click outside to close
	$effect(() => {
		if (!open) return;
		function onPointerDown(e: PointerEvent) {
			if (!wrapperEl?.contains(e.target as Node)) {
				closeDropdown();
			}
		}
		document.addEventListener('pointerdown', onPointerDown, true);
		return () => document.removeEventListener('pointerdown', onPointerDown, true);
	});

	// Clicking the textarea itself closes the dropdown
	function handleTextareaClick() {
		if (open) closeDropdown();
	}

	// Close on blur, with delay to allow focus to settle between elements
	const BLUR_DELAY_MS = 150;

	function handleTextareaBlur() {
		if (!open) return;
		clearTimeout(textareaBlurTimeout);
		textareaBlurTimeout = setTimeout(() => {
			textareaBlurTimeout = undefined;
			if (!autocompleteEl?.contains(document.activeElement)) {
				closeDropdown();
			}
		}, BLUR_DELAY_MS);
	}

	function handleAutocompleteFocusout() {
		if (!open) return;
		clearTimeout(autocompleteBlurTimeout);
		autocompleteBlurTimeout = setTimeout(() => {
			autocompleteBlurTimeout = undefined;
			const active = document.activeElement;
			if (active !== textareaEl && !autocompleteEl?.contains(active)) {
				closeDropdown();
			}
		}, BLUR_DELAY_MS);
	}

	onDestroy(() => {
		clearBlurTimeouts();
	});
</script>

<div class="markdown-textarea" bind:this={wrapperEl}>
	<FieldGroup {label} {id}>
		{#snippet children(inputId)}
			<MarkdownToolbar
				onbold={() => {
					if (!textareaEl) return;
					applyAndSync(
						toggleMarker(textareaEl.value, textareaEl.selectionStart, textareaEl.selectionEnd, '**')
					);
				}}
				onitalic={() => {
					if (!textareaEl) return;
					applyAndSync(
						toggleMarker(textareaEl.value, textareaEl.selectionStart, textareaEl.selectionEnd, '*')
					);
				}}
				onlink={() => openLinkPicker()}
				onbulletlist={() => {
					if (!textareaEl) return;
					applyAndSync(
						toggleList(textareaEl.value, textareaEl.selectionStart, textareaEl.selectionEnd, false)
					);
				}}
				onnumberedlist={() => {
					if (!textareaEl) return;
					applyAndSync(
						toggleList(textareaEl.value, textareaEl.selectionStart, textareaEl.selectionEnd, true)
					);
				}}
				oncitation={() => openLinkPicker('cite')}
			/>
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
			role="presentation"
			style:left="{dropdownLeft}px"
			style:top="{dropdownTop}px"
			bind:this={autocompleteEl}
			onmousedown={(e) => {
				if (!(e.target instanceof HTMLInputElement)) e.preventDefault();
			}}
			onfocusout={handleAutocompleteFocusout}
		>
			<WikilinkAutocomplete
				bind:this={autocompleteRef}
				{initialType}
				oncomplete={(linkText) => insertWikilink(linkText)}
				oncancel={() => {
					closeDropdown();
					textareaEl?.focus();
				}}
				onfocusreturn={() => textareaEl?.focus()}
			/>
		</div>
	{/if}
</div>

<style>
	.markdown-textarea {
		position: relative;
	}

	.markdown-textarea textarea {
		border-top-left-radius: 0;
		border-top-right-radius: 0;
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
		min-width: 16rem;
		max-width: 24rem;
		max-height: 20rem;
		overflow-y: auto;
		background-color: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: var(--radius-2);
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
	}
</style>
