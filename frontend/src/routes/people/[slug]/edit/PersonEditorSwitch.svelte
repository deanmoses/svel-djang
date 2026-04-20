<script lang="ts">
	import DescriptionEditor from '$lib/components/editors/DescriptionEditor.svelte';
	import NameEditor from '$lib/components/editors/NameEditor.svelte';
	import type { SectionEditorHandle } from '$lib/components/editors/editor-contract';
	import type { PersonEditSectionKey } from '$lib/components/editors/person-edit-sections';
	import PersonDetailsEditor from './PersonDetailsEditor.svelte';
	import { savePersonClaims } from './save-person-claims';
	import type { PersonEditView } from './person-edit-types';

	let {
		sectionKey,
		initialData,
		slug,
		editorRef = $bindable<SectionEditorHandle | undefined>(undefined),
		onsaved,
		onerror,
		ondirtychange
	}: {
		sectionKey: PersonEditSectionKey;
		initialData: PersonEditView;
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
		save={savePersonClaims}
		{onsaved}
		{onerror}
		{ondirtychange}
	/>
{:else if sectionKey === 'bio'}
	<DescriptionEditor
		bind:this={editorRef}
		initialData={initialData.description?.text ?? ''}
		{slug}
		save={savePersonClaims}
		label="Bio"
		{onsaved}
		{onerror}
		{ondirtychange}
	/>
{:else if sectionKey === 'details'}
	<PersonDetailsEditor
		bind:this={editorRef}
		{initialData}
		{slug}
		{onsaved}
		{onerror}
		{ondirtychange}
	/>
{/if}
