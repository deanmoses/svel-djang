<script lang="ts">
	import { getContext } from 'svelte';
	import { page } from '$app/state';
	import { goto, invalidateAll } from '$app/navigation';
	import { resolve } from '$app/paths';
	import SectionEditorForm from '$lib/components/SectionEditorForm.svelte';
	import TitleBasicsEditor from '$lib/components/editors/TitleBasicsEditor.svelte';
	import TitleExternalDataEditor from '$lib/components/editors/TitleExternalDataEditor.svelte';
	import TitleOverviewEditor from '$lib/components/editors/TitleOverviewEditor.svelte';
	import type { SectionEditorHandle } from '$lib/components/editors/editor-contract';
	import type { SaveMeta } from '$lib/components/editors/save-claims-shared';
	import {
		defaultTitleSectionSegment,
		findTitleSectionBySegment,
		titleSectionsFor
	} from '$lib/components/editors/title-edit-sections';

	let { data } = $props();
	let title = $derived(data.title);
	let slug = $derived(page.params.slug);
	let sectionSegment = $derived(page.params.section);
	let isSingleModel = $derived(!!title.model_detail);
	let section = $derived(sectionSegment ? findTitleSectionBySegment(sectionSegment) : undefined);
	let sectionAvailable = $derived(
		section ? titleSectionsFor(isSingleModel).some((s) => s.key === section!.key) : false
	);

	$effect(() => {
		if (!sectionAvailable) {
			goto(resolve(`/titles/${slug}/edit/${defaultTitleSectionSegment(isSingleModel)}`), {
				replaceState: true
			});
		}
	});

	const editLayout = getContext<{ setDirty: (dirty: boolean) => void }>('edit-layout');

	let editorRef = $state<SectionEditorHandle>();
	let editError = $state('');
	let saveCounter = $state(0);

	async function handleSave(meta: SaveMeta) {
		editError = '';
		await editorRef?.save(meta);
	}

	function handleCancel() {
		if (editorRef?.isDirty() && !confirm('Discard unsaved changes?')) {
			return;
		}
		goto(resolve(`/titles/${slug}`));
	}

	async function handleSaved() {
		editLayout.setDirty(false);
		await invalidateAll();
		const updatedSlug = data.title.slug;
		if (updatedSlug !== slug) {
			await goto(resolve(`/titles/${updatedSlug}/edit/${sectionSegment}`), {
				replaceState: true
			});
		}
		saveCounter++;
	}

	function handleDirtyChange(dirty: boolean) {
		editLayout.setDirty(dirty);
	}
</script>

{#if section && sectionAvailable}
	{#key saveCounter}
		<SectionEditorForm
			error={editError}
			showCitation={section.showCitation}
			showMixedEditWarning={section.showMixedEditWarning}
			oncancel={handleCancel}
			onsave={handleSave}
		>
			{#if section.key === 'overview'}
				<TitleOverviewEditor
					bind:this={editorRef}
					initialData={title.description?.text ?? ''}
					slug={title.slug}
					onsaved={handleSaved}
					onerror={(msg) => (editError = msg)}
					ondirtychange={handleDirtyChange}
				/>
			{:else if section.key === 'basics'}
				<TitleBasicsEditor
					bind:this={editorRef}
					initialData={title}
					slug={title.slug}
					onsaved={handleSaved}
					onerror={(msg) => (editError = msg)}
					ondirtychange={handleDirtyChange}
				/>
			{:else if section.key === 'external-data'}
				<TitleExternalDataEditor
					bind:this={editorRef}
					initialData={title}
					slug={title.slug}
					onsaved={handleSaved}
					onerror={(msg) => (editError = msg)}
					ondirtychange={handleDirtyChange}
				/>
			{/if}
		</SectionEditorForm>
	{/key}
{/if}
