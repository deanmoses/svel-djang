<script lang="ts">
	import AliasesSectionEditor from './AliasesSectionEditor.svelte';
	import DescriptionEditor from './DescriptionEditor.svelte';
	import NameEditor from './NameEditor.svelte';
	import ParentsSectionEditor from './ParentsSectionEditor.svelte';
	import type { SectionEditorHandle } from './editor-contract';
	import type { HierarchicalTaxonomyEditSectionKey } from './hierarchical-taxonomy-edit-sections';
	import type {
		HierarchicalTaxonomyEditView,
		SaveHierarchicalTaxonomyClaims
	} from './hierarchical-taxonomy-edit-types';

	type ParentOption = { slug: string; label: string; count?: number };
	type ParentOptionsLoader = () => Promise<ParentOption[]>;

	let {
		sectionKey,
		initialData,
		slug,
		saveClaims,
		parentOptionsLoader,
		parentsLabel,
		editorRef = $bindable<SectionEditorHandle | undefined>(undefined),
		onsaved,
		onerror,
		ondirtychange
	}: {
		sectionKey: HierarchicalTaxonomyEditSectionKey;
		initialData: HierarchicalTaxonomyEditView;
		slug: string;
		saveClaims: SaveHierarchicalTaxonomyClaims;
		parentOptionsLoader: ParentOptionsLoader;
		/** Field label for the parents picker (e.g. "This feature is a type of..."). Defaults to ParentsSectionEditor's default. */
		parentsLabel?: string;
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
{:else if sectionKey === 'aliases'}
	<AliasesSectionEditor
		bind:this={editorRef}
		initialData={{ aliases: initialData.aliases }}
		{slug}
		save={saveClaims}
		{onsaved}
		{onerror}
		{ondirtychange}
	/>
{:else if sectionKey === 'parents'}
	<ParentsSectionEditor
		bind:this={editorRef}
		initialData={{ parents: initialData.parents }}
		{slug}
		save={saveClaims}
		optionsLoader={parentOptionsLoader}
		label={parentsLabel}
		{onsaved}
		{onerror}
		{ondirtychange}
	/>
{/if}
