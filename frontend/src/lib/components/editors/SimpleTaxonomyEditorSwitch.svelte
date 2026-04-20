<script lang="ts">
	import DescriptionEditor from './DescriptionEditor.svelte';
	import NameEditor from './NameEditor.svelte';
	import DisplayOrderEditor from './DisplayOrderEditor.svelte';
	import type { SectionEditorHandle } from './editor-contract';
	import type { SimpleTaxonomyEditSectionKey } from './simple-taxonomy-edit-sections';
	import type {
		SaveSimpleTaxonomyClaims,
		SimpleTaxonomyEditView
	} from './simple-taxonomy-edit-types';

	let {
		sectionKey,
		initialData,
		slug,
		saveClaims,
		editorRef = $bindable<SectionEditorHandle | undefined>(undefined),
		onsaved,
		onerror,
		ondirtychange
	}: {
		sectionKey: SimpleTaxonomyEditSectionKey;
		initialData: SimpleTaxonomyEditView;
		slug: string;
		saveClaims: SaveSimpleTaxonomyClaims;
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
		{slug}
		save={saveClaims}
		{onsaved}
		{onerror}
		{ondirtychange}
	/>
{:else if sectionKey === 'description'}
	<DescriptionEditor
		bind:this={editorRef}
		initialData={initialData.description.text}
		{slug}
		save={saveClaims}
		{onsaved}
		{onerror}
		{ondirtychange}
	/>
{:else if sectionKey === 'display-order'}
	<DisplayOrderEditor
		bind:this={editorRef}
		initialData={initialData.display_order}
		{slug}
		save={saveClaims}
		{onsaved}
		{onerror}
		{ondirtychange}
	/>
{/if}
