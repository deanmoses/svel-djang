<script lang="ts">
	import AccordionSection from '$lib/components/AccordionSection.svelte';
	import AttributionLine from '$lib/components/AttributionLine.svelte';
	import Markdown from '$lib/components/Markdown.svelte';
	import type { InlineCitation } from '$lib/components/citation-tooltip';
	import type { RichTextAccordionState } from '$lib/components/rich-text-accordion-state.svelte';

	type RichTextValue = {
		text?: string;
		html?: string;
		citations?: InlineCitation[];
		attribution?: object | null;
	} | null;

	let {
		richText = null,
		state,
		heading = 'Overview',
		open = true,
		onEdit = undefined
	}: {
		richText?: RichTextValue;
		state: RichTextAccordionState;
		heading?: string;
		open?: boolean;
		onEdit?: (() => void) | undefined;
	} = $props();
</script>

{#if richText?.html}
	<AccordionSection {heading} {open} {onEdit}>
		<div bind:this={state.descriptionContentEl}>
			<Markdown
				html={richText.html}
				citations={richText.citations ?? []}
				showReferences={false}
				onNavigateToRef={state.scrollToRefEntry}
			/>
			<AttributionLine attribution={richText.attribution} />
		</div>
	</AccordionSection>
{/if}
