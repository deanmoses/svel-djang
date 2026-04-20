<script lang="ts">
	import AccordionSection from '$lib/components/AccordionSection.svelte';
	import ReferencesSection from '$lib/components/ReferencesSection.svelte';
	import { deduplicateCitations } from '$lib/components/citation-refs';
	import type { InlineCitation } from '$lib/components/citation-tooltip';
	import type { RichTextAccordionState } from '$lib/components/rich-text-accordion-state.svelte';

	type RichTextValue = {
		citations?: InlineCitation[];
	} | null;

	let {
		richText = null,
		state
	}: {
		richText?: RichTextValue;
		state: RichTextAccordionState;
	} = $props();

	let citations = $derived(richText?.citations ?? []);
	let uniqueCount = $derived(deduplicateCitations(citations).length);
</script>

{#if citations.length > 0}
	<AccordionSection heading="References ({uniqueCount})" bind:open={state.refsAccordionOpen}>
		<div bind:this={state.refsContentEl}>
			<ReferencesSection
				{citations}
				open={true}
				showToggle={false}
				onBackLink={state.scrollToInlineMarker}
			/>
		</div>
	</AccordionSection>
{/if}
