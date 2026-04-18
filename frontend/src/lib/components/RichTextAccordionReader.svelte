<script lang="ts">
	import { tick } from 'svelte';
	import AccordionSection from '$lib/components/AccordionSection.svelte';
	import AttributionLine from '$lib/components/AttributionLine.svelte';
	import Markdown from '$lib/components/Markdown.svelte';
	import ReferencesSection from '$lib/components/ReferencesSection.svelte';
	import type { InlineCitation } from '$lib/components/citation-tooltip';
	import {
		deduplicateCitations,
		findFirstInlineMarker,
		findRefEntry,
		scrollToAndHighlight
	} from '$lib/components/citation-refs';

	type RichTextValue = {
		text?: string;
		html?: string;
		citations?: InlineCitation[];
		attribution?: object | null;
	} | null;

	let {
		heading = 'Overview',
		richText = null,
		emptyText = 'No description yet.',
		open = true,
		onEdit = undefined
	}: {
		heading?: string;
		richText?: RichTextValue;
		emptyText?: string;
		open?: boolean;
		onEdit?: (() => void) | undefined;
	} = $props();

	let descriptionContentEl: HTMLDivElement | undefined = $state();
	let refsContentEl: HTMLDivElement | undefined = $state();
	let refsAccordionOpen = $state(false);

	let citations = $derived(richText?.citations ?? []);
	let uniqueCitationCount = $derived(deduplicateCitations(citations).length);

	function scrollToInlineMarker(index: number) {
		if (!descriptionContentEl) return;
		const marker = findFirstInlineMarker(descriptionContentEl, index);
		if (marker) scrollToAndHighlight(marker);
	}

	async function scrollToRefEntry(index: number) {
		refsAccordionOpen = true;
		await tick();
		if (!refsContentEl) return;
		const entry = findRefEntry(refsContentEl, index);
		if (entry) scrollToAndHighlight(entry);
	}
</script>

<AccordionSection {heading} {open} {onEdit}>
	{#if richText?.html}
		<div bind:this={descriptionContentEl}>
			<Markdown
				html={richText.html}
				{citations}
				showReferences={false}
				onNavigateToRef={scrollToRefEntry}
			/>
			<AttributionLine attribution={richText.attribution} />
		</div>
	{:else}
		<p class="muted">{emptyText}</p>
	{/if}
</AccordionSection>

{#if citations.length > 0}
	<AccordionSection heading="References ({uniqueCitationCount})" bind:open={refsAccordionOpen}>
		<div bind:this={refsContentEl}>
			<ReferencesSection
				{citations}
				open={true}
				showToggle={false}
				onBackLink={scrollToInlineMarker}
			/>
		</div>
	</AccordionSection>
{/if}

<style>
	.muted {
		color: var(--color-text-muted);
		font-size: var(--font-size-0);
	}
</style>
