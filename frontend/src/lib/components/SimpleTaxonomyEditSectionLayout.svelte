<script lang="ts">
	import type { Snippet } from 'svelte';
	import TaxonomyEditSectionLayoutBase from '$lib/components/TaxonomyEditSectionLayoutBase.svelte';
	import {
		defaultSimpleTaxonomySectionSegment,
		SIMPLE_TAXONOMY_EDIT_SECTIONS
	} from '$lib/components/editors/simple-taxonomy-edit-sections';

	let {
		basePath,
		children
	}: {
		basePath: string;
		children: Snippet;
	} = $props();
</script>

<TaxonomyEditSectionLayoutBase
	{basePath}
	sections={SIMPLE_TAXONOMY_EDIT_SECTIONS}
	defaultSegment={defaultSimpleTaxonomySectionSegment()}
>
	{@render children()}
</TaxonomyEditSectionLayoutBase>
