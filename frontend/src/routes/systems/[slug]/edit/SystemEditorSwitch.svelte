<script lang="ts">
	import DescriptionEditor from '$lib/components/editors/DescriptionEditor.svelte';
	import NameEditor from '$lib/components/editors/NameEditor.svelte';
	import SystemManufacturerEditor from '$lib/components/editors/SystemManufacturerEditor.svelte';
	import SystemTechnologyEditor from '$lib/components/editors/SystemTechnologyEditor.svelte';
	import type { SectionEditorHandle } from '$lib/components/editors/editor-contract';
	import type { SystemEditSectionKey } from '$lib/components/editors/system-edit-sections';
	import { saveSystemClaims } from './save-system-claims';
	import type { SystemEditView } from './system-edit-types';

	let {
		sectionKey,
		initialData,
		slug,
		editorRef = $bindable<SectionEditorHandle | undefined>(undefined),
		onsaved,
		onerror,
		ondirtychange
	}: {
		sectionKey: SystemEditSectionKey;
		initialData: SystemEditView;
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
		save={saveSystemClaims}
		{onsaved}
		{onerror}
		{ondirtychange}
	/>
{:else if sectionKey === 'description'}
	<DescriptionEditor
		bind:this={editorRef}
		initialData={initialData.description?.text ?? ''}
		{slug}
		save={saveSystemClaims}
		{onsaved}
		{onerror}
		{ondirtychange}
	/>
{:else if sectionKey === 'manufacturer'}
	<SystemManufacturerEditor
		bind:this={editorRef}
		initialData={{ manufacturer: initialData.manufacturer }}
		{slug}
		save={saveSystemClaims}
		{onsaved}
		{onerror}
		{ondirtychange}
	/>
{:else if sectionKey === 'technology'}
	<SystemTechnologyEditor
		bind:this={editorRef}
		initialData={{ technology_subgeneration: initialData.technology_subgeneration }}
		{slug}
		save={saveSystemClaims}
		{onsaved}
		{onerror}
		{ondirtychange}
	/>
{/if}
