<script lang="ts">
	import { getContext } from 'svelte';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import SectionEditorForm from '$lib/components/SectionEditorForm.svelte';
	import { LAYOUT_BREAKPOINT } from '$lib/constants';
	import type { SectionEditorHandle } from '$lib/components/editors/editor-contract';
	import {
		defaultManufacturerSectionSegment,
		findManufacturerSectionBySegment
	} from '$lib/components/editors/manufacturer-edit-sections';
	import type { SaveMeta } from '$lib/components/editors/save-model-claims';
	import ManufacturerBasicsEditor from '../ManufacturerBasicsEditor.svelte';
	import ManufacturerDescriptionEditor from '../ManufacturerDescriptionEditor.svelte';
	import ManufacturerNameEditor from '../ManufacturerNameEditor.svelte';

	let { data } = $props();
	let manufacturer = $derived(data.manufacturer);
	let slug = $derived(page.params.slug);
	let sectionSegment = $derived(page.params.section);
	let section = $derived(
		sectionSegment ? findManufacturerSectionBySegment(sectionSegment) : undefined
	);

	const editLayout = getContext<{ setDirty: (dirty: boolean) => void }>('edit-layout');

	let editorRef = $state<SectionEditorHandle>();
	let editError = $state('');
	let saveCounter = $state(0);
	let isMobile = $state<boolean | null>(null);

	$effect(() => {
		if (!section) {
			goto(resolve(`/manufacturers/${slug}/edit/${defaultManufacturerSectionSegment()}`), {
				replaceState: true
			});
		}
	});

	$effect(() => {
		const mql = matchMedia(`(max-width: ${LAYOUT_BREAKPOINT}rem)`);
		isMobile = mql.matches;
		function onChange(e: MediaQueryListEvent) {
			isMobile = e.matches;
		}
		mql.addEventListener('change', onChange);
		return () => mql.removeEventListener('change', onChange);
	});

	$effect(() => {
		if (isMobile === false && section) {
			goto(resolve(`/manufacturers/${slug}?edit=${section.segment}`), { replaceState: true });
		}
	});

	async function handleSave(meta: SaveMeta) {
		editError = '';
		await editorRef?.save(meta);
	}

	function handleCancel() {
		if (editorRef?.isDirty() && !confirm('Discard unsaved changes?')) {
			return;
		}
		goto(resolve(`/manufacturers/${slug}`));
	}

	function handleSaved() {
		editLayout.setDirty(false);
		saveCounter++;
	}

	function handleDirtyChange(dirty: boolean) {
		editLayout.setDirty(dirty);
	}
</script>

{#if isMobile && section}
	{#key `${section.key}:${saveCounter}`}
		<SectionEditorForm
			error={editError}
			showCitation={section.showCitation}
			showMixedEditWarning={section.showMixedEditWarning}
			oncancel={handleCancel}
			onsave={handleSave}
		>
			{#if section.key === 'name'}
				<ManufacturerNameEditor
					bind:this={editorRef}
					initialData={manufacturer}
					slug={manufacturer.slug}
					onsaved={handleSaved}
					onerror={(msg) => (editError = msg)}
					ondirtychange={handleDirtyChange}
				/>
			{:else if section.key === 'description'}
				<ManufacturerDescriptionEditor
					bind:this={editorRef}
					initialData={manufacturer}
					slug={manufacturer.slug}
					onsaved={handleSaved}
					onerror={(msg) => (editError = msg)}
					ondirtychange={handleDirtyChange}
				/>
			{:else if section.key === 'basics'}
				<ManufacturerBasicsEditor
					bind:this={editorRef}
					initialData={manufacturer}
					slug={manufacturer.slug}
					onsaved={handleSaved}
					onerror={(msg) => (editError = msg)}
					ondirtychange={handleDirtyChange}
				/>
			{/if}
		</SectionEditorForm>
	{/key}
{/if}
