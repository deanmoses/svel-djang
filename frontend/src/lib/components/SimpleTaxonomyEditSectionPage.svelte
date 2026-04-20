<script lang="ts">
	import TaxonomyEditSectionPageBase from '$lib/components/TaxonomyEditSectionPageBase.svelte';
	import {
		defaultSimpleTaxonomySectionSegment,
		SIMPLE_TAXONOMY_EDIT_SECTIONS,
		type SimpleTaxonomyEditSectionKey
	} from '$lib/components/editors/simple-taxonomy-edit-sections';
	import SimpleTaxonomyEditorSwitch from '$lib/components/editors/SimpleTaxonomyEditorSwitch.svelte';
	import type {
		SaveSimpleTaxonomyClaims,
		SimpleTaxonomyEditView
	} from '$lib/components/editors/simple-taxonomy-edit-types';

	let {
		profile,
		basePath,
		saveClaims
	}: {
		profile: SimpleTaxonomyEditView;
		basePath: string;
		saveClaims: SaveSimpleTaxonomyClaims;
	} = $props();

	const sections = SIMPLE_TAXONOMY_EDIT_SECTIONS.map((section) => ({
		...section,
		usesSectionEditorForm: true
	}));
</script>

<TaxonomyEditSectionPageBase
	{basePath}
	{sections}
	defaultSegment={defaultSimpleTaxonomySectionSegment()}
>
	{#snippet editor(key: SimpleTaxonomyEditSectionKey, { ref, onsaved, onerror, ondirtychange })}
		<SimpleTaxonomyEditorSwitch
			sectionKey={key}
			initialData={profile}
			slug={profile.slug}
			{saveClaims}
			bind:editorRef={ref.current}
			{onsaved}
			{onerror}
			{ondirtychange}
		/>
	{/snippet}
</TaxonomyEditSectionPageBase>
