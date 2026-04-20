<script lang="ts">
	import DescriptionEditor from '$lib/components/editors/DescriptionEditor.svelte';
	import NameEditor from '$lib/components/editors/NameEditor.svelte';
	import type { SectionEditorHandle } from '$lib/components/editors/editor-contract';
	import type { SeriesEditSectionKey } from '$lib/components/editors/series-edit-sections';
	import { saveSeriesClaims } from './save-series-claims';
	import type { SeriesEditView } from './series-edit-types';

	let {
		sectionKey,
		initialData,
		slug,
		editorRef = $bindable<SectionEditorHandle | undefined>(undefined),
		onsaved,
		onerror,
		ondirtychange
	}: {
		sectionKey: SeriesEditSectionKey;
		initialData: SeriesEditView;
		slug: string;
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
		save={saveSeriesClaims}
		{onsaved}
		{onerror}
		{ondirtychange}
	/>
{:else if sectionKey === 'description'}
	<DescriptionEditor
		bind:this={editorRef}
		initialData={initialData.description?.text ?? ''}
		{slug}
		save={saveSeriesClaims}
		{onsaved}
		{onerror}
		{ondirtychange}
	/>
{/if}
