<script lang="ts">
	import type { components } from '$lib/api/schema';
	import type { SectionEditorHandle } from '$lib/components/editors/editor-contract';
	import type { ModelEditSectionKey } from '$lib/components/editors/model-edit-sections';
	import BasicsEditor from '$lib/components/editors/BasicsEditor.svelte';
	import DescriptionEditor from '$lib/components/editors/DescriptionEditor.svelte';
	import ExternalDataEditor from '$lib/components/editors/ExternalDataEditor.svelte';
	import FeaturesEditor from '$lib/components/editors/FeaturesEditor.svelte';
	import NameEditor from '$lib/components/editors/NameEditor.svelte';
	import PeopleEditor from '$lib/components/editors/PeopleEditor.svelte';
	import RelatedModelsEditor from '$lib/components/editors/RelatedModelsEditor.svelte';
	import { saveModelClaims } from '$lib/components/editors/save-model-claims';
	import TechnologyEditor from '$lib/components/editors/TechnologyEditor.svelte';

	type ModelDetail = components['schemas']['MachineModelDetailSchema'];

	let {
		sectionKey,
		initialData,
		slug,
		slim = false,
		editorRef = $bindable<SectionEditorHandle | undefined>(undefined),
		onsaved,
		onerror,
		ondirtychange
	}: {
		sectionKey: ModelEditSectionKey;
		initialData: ModelDetail;
		slug: string;
		slim?: boolean;
		editorRef?: SectionEditorHandle | undefined;
		onsaved: () => void;
		onerror: (message: string) => void;
		ondirtychange: (dirty: boolean) => void;
	} = $props();
</script>

{#if sectionKey === 'name'}
	<NameEditor
		bind:this={editorRef}
		initialData={{ name: initialData.name, slug: initialData.slug }}
		initialAbbreviations={initialData.abbreviations}
		{slug}
		save={saveModelClaims}
		{onsaved}
		{onerror}
		{ondirtychange}
	/>
{:else if sectionKey === 'basics'}
	<BasicsEditor
		bind:this={editorRef}
		{initialData}
		{slug}
		{slim}
		{onsaved}
		{onerror}
		{ondirtychange}
	/>
{:else if sectionKey === 'overview'}
	<DescriptionEditor
		bind:this={editorRef}
		initialData={initialData.description?.text ?? ''}
		{slug}
		save={saveModelClaims}
		{onsaved}
		{onerror}
		{ondirtychange}
	/>
{:else if sectionKey === 'technology'}
	<TechnologyEditor
		bind:this={editorRef}
		{initialData}
		{slug}
		{onsaved}
		{onerror}
		{ondirtychange}
	/>
{:else if sectionKey === 'features'}
	<FeaturesEditor bind:this={editorRef} {initialData} {slug} {onsaved} {onerror} {ondirtychange} />
{:else if sectionKey === 'people'}
	<PeopleEditor
		bind:this={editorRef}
		initialData={initialData.credits}
		{slug}
		{onsaved}
		{onerror}
		{ondirtychange}
	/>
{:else if sectionKey === 'related-models'}
	<RelatedModelsEditor
		bind:this={editorRef}
		{initialData}
		{slug}
		{onsaved}
		{onerror}
		{ondirtychange}
	/>
{:else if sectionKey === 'external-data'}
	<ExternalDataEditor
		bind:this={editorRef}
		{initialData}
		{slug}
		{onsaved}
		{onerror}
		{ondirtychange}
	/>
{/if}
