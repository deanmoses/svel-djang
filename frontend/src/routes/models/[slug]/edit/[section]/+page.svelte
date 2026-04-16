<script lang="ts">
	import { getContext } from 'svelte';
	import { page } from '$app/state';
	import { goto, invalidateAll } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { MEDIA_CATEGORIES } from '$lib/api/catalog-meta';
	import SectionEditorForm from '$lib/components/SectionEditorForm.svelte';
	import Button from '$lib/components/Button.svelte';
	import BasicsEditor from '$lib/components/editors/BasicsEditor.svelte';
	import OverviewEditor from '$lib/components/editors/OverviewEditor.svelte';
	import SpecificationsEditor from '$lib/components/editors/SpecificationsEditor.svelte';
	import FeaturesEditor from '$lib/components/editors/FeaturesEditor.svelte';
	import PeopleEditor from '$lib/components/editors/PeopleEditor.svelte';
	import RelationshipsEditor from '$lib/components/editors/RelationshipsEditor.svelte';
	import ExternalDataEditor from '$lib/components/editors/ExternalDataEditor.svelte';
	import MediaEditor from '$lib/components/editors/MediaEditor.svelte';
	import type { SectionEditorHandle } from '$lib/components/editors/editor-contract';
	import type { SaveMeta } from '$lib/components/editors/save-model-claims';
	import { findSectionBySegment } from '$lib/components/editors/model-edit-sections';

	let { data } = $props();
	let model = $derived(data.model);
	let slug = $derived(page.params.slug);
	let sectionSegment = $derived(page.params.section);
	let section = $derived(sectionSegment ? findSectionBySegment(sectionSegment) : undefined);

	// Redirect invalid sections to basics
	$effect(() => {
		if (!section) {
			goto(resolve(`/models/${slug}/edit/basics`), { replaceState: true });
		}
	});

	const editLayout = getContext<{ setDirty: (dirty: boolean) => void }>('edit-layout');

	let editorRef = $state<SectionEditorHandle>();
	let editError = $state('');

	async function handleSave(meta: SaveMeta) {
		editError = '';
		await editorRef?.save(meta);
	}

	function handleCancel() {
		goto(resolve(`/models/${slug}`));
	}

	async function handleSaved() {
		await invalidateAll();
		// BasicsEditor can change the slug — redirect if needed
		const updatedSlug = data.model.slug;
		if (updatedSlug !== slug) {
			await goto(resolve(`/models/${updatedSlug}/edit/${sectionSegment}`), {
				replaceState: true
			});
		}
	}

	function handleDirtyChange(dirty: boolean) {
		editLayout.setDirty(dirty);
	}
</script>

{#if section}
	{#if section.usesSectionEditorForm}
		<SectionEditorForm
			error={editError}
			showCitation={section.showCitation}
			showMixedEditWarning={section.showMixedEditWarning}
			oncancel={handleCancel}
			onsave={handleSave}
		>
			{#if section.key === 'basics'}
				<BasicsEditor
					bind:this={editorRef}
					initialModel={model}
					slug={model.slug}
					onsaved={handleSaved}
					onerror={(msg) => (editError = msg)}
					ondirtychange={handleDirtyChange}
				/>
			{:else if section.key === 'overview'}
				<OverviewEditor
					bind:this={editorRef}
					initialDescription={model.description?.text ?? ''}
					slug={model.slug}
					onsaved={handleSaved}
					onerror={(msg) => (editError = msg)}
					ondirtychange={handleDirtyChange}
				/>
			{:else if section.key === 'specifications'}
				<SpecificationsEditor
					bind:this={editorRef}
					initialModel={model}
					slug={model.slug}
					onsaved={handleSaved}
					onerror={(msg) => (editError = msg)}
					ondirtychange={handleDirtyChange}
				/>
			{:else if section.key === 'features'}
				<FeaturesEditor
					bind:this={editorRef}
					initialModel={model}
					slug={model.slug}
					onsaved={handleSaved}
					onerror={(msg) => (editError = msg)}
					ondirtychange={handleDirtyChange}
				/>
			{:else if section.key === 'people'}
				<PeopleEditor
					bind:this={editorRef}
					initialCredits={model.credits}
					slug={model.slug}
					onsaved={handleSaved}
					onerror={(msg) => (editError = msg)}
					ondirtychange={handleDirtyChange}
				/>
			{:else if section.key === 'relationships'}
				<RelationshipsEditor
					bind:this={editorRef}
					initialModel={model}
					slug={model.slug}
					onsaved={handleSaved}
					onerror={(msg) => (editError = msg)}
					ondirtychange={handleDirtyChange}
				/>
			{:else if section.key === 'external-data'}
				<ExternalDataEditor
					bind:this={editorRef}
					initialModel={model}
					slug={model.slug}
					onsaved={handleSaved}
					onerror={(msg) => (editError = msg)}
					ondirtychange={handleDirtyChange}
				/>
			{/if}
		</SectionEditorForm>
	{:else if section.key === 'media'}
		<MediaEditor
			entityType="model"
			slug={model.slug}
			media={model.uploaded_media}
			categories={[...MEDIA_CATEGORIES.model]}
		/>
		<div class="media-footer">
			<Button onclick={handleCancel}>Done</Button>
		</div>
	{/if}
{/if}

<style>
	.media-footer {
		display: flex;
		justify-content: flex-end;
		margin-top: var(--size-4);
	}
</style>
