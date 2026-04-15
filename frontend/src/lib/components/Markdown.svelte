<script lang="ts">
	import { tick } from 'svelte';
	import CitationTooltip from './CitationTooltip.svelte';
	import ReferencesSection from './ReferencesSection.svelte';
	import type { InlineCitation } from './citation-tooltip';
	import { findRefEntry, findFirstInlineMarker, scrollToAndHighlight } from './citation-refs';

	let {
		html,
		citations = undefined,
		showReferences = true,
		onNavigateToRef = undefined
	}: {
		html: string;
		citations?: InlineCitation[];
		showReferences?: boolean;
		onNavigateToRef?: (index: number) => void;
	} = $props();

	let container: HTMLDivElement | undefined = $state();
	let refsSection: HTMLElement | undefined = $state();
	let refsOpen = $state(false);

	async function scrollToRef(index: number) {
		refsOpen = true;
		await tick();
		if (refsSection) {
			const entry = findRefEntry(refsSection, index);
			if (entry) scrollToAndHighlight(entry);
		}
	}

	function scrollToInlineMarker(index: number) {
		if (container) {
			const marker = findFirstInlineMarker(container, index);
			if (marker) scrollToAndHighlight(marker);
		}
	}
</script>

<!-- eslint-disable-next-line svelte/no-at-html-tags -- sanitized server-side by nh3 -->
<div class="content" bind:this={container}>{@html html}</div>
<CitationTooltip
	{container}
	htmlSignal={html}
	{citations}
	onNavigate={onNavigateToRef ?? (citations && citations.length > 0 ? scrollToRef : undefined)}
/>
{#if showReferences && citations && citations.length > 0}
	<div bind:this={refsSection}>
		<ReferencesSection {citations} bind:open={refsOpen} onBackLink={scrollToInlineMarker} />
	</div>
{/if}

<style>
	.content {
		font-size: var(--font-size-2);
		color: var(--color-text-primary);
		line-height: var(--font-lineheight-3);
	}

	/* Block elements injected by {@html} — need :global since Svelte
	   can't see them at compile time. Scoped to .content so they don't
	   leak into the references section wrapper. */
	.content :global(p) {
		margin-bottom: var(--size-3);
	}

	.content :global(p:last-child) {
		margin-bottom: 0;
	}

	.content :global(a) {
		color: var(--color-link);
		text-decoration: none;
	}

	.content :global(a:hover) {
		text-decoration: underline;
	}

	.content :global(strong) {
		font-weight: 700;
	}

	.content :global(ul),
	.content :global(ol) {
		padding-left: var(--size-5);
		margin-bottom: var(--size-3);
	}

	.content :global(li) {
		margin-bottom: var(--size-1);
	}

	.content :global(blockquote) {
		border-left: 3px solid var(--color-border);
		padding-left: var(--size-4);
		color: var(--color-text-muted);
		margin: 0 0 var(--size-3);
	}

	.content :global(code) {
		font-family: var(--font-mono);
		font-size: 0.9em;
		background: var(--color-surface);
		padding: 0.1em 0.3em;
		border-radius: var(--radius-1);
	}

	.content :global(pre) {
		background: var(--color-surface);
		padding: var(--size-3);
		border-radius: var(--radius-2);
		overflow-x: auto;
		margin-bottom: var(--size-3);
	}

	.content :global(pre code) {
		background: none;
		padding: 0;
	}

	.content :global(hr) {
		border: none;
		border-top: 1px solid var(--color-border-soft);
		margin: var(--size-4) 0;
	}

	.content :global(table) {
		border-collapse: collapse;
		margin-bottom: var(--size-3);
		width: 100%;
	}

	.content :global(th),
	.content :global(td) {
		border: 1px solid var(--color-border-soft);
		padding: var(--size-1) var(--size-2);
		text-align: left;
	}

	.content :global(th) {
		font-weight: 600;
	}

	.content :global(h1),
	.content :global(h2),
	.content :global(h3),
	.content :global(h4),
	.content :global(h5),
	.content :global(h6) {
		font-weight: 600;
		color: var(--color-text-primary);
		margin-bottom: var(--size-2);
	}

	.content :global(.task-list-item) {
		list-style: none;
	}

	.content :global(.task-list-item input[type='checkbox']) {
		margin-right: var(--size-1);
	}

	.content :global(sup[data-cite-id]) {
		cursor: pointer;
		color: var(--color-link);
	}

	.content :global(sup[data-cite-id]:hover),
	.content :global(sup[data-cite-id]:focus-visible) {
		text-decoration: underline;
		outline: none;
	}

	.content :global(.cite-highlight),
	:global(.cite-highlight) {
		background-color: var(--color-highlight, #fff3cd);
		transition: background-color 1.5s ease-out;
	}
</style>
