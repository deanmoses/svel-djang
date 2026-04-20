<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import SectionEditorForm from '$lib/components/SectionEditorForm.svelte';
	import { LAYOUT_BREAKPOINT } from '$lib/constants';
	import type { SectionEditorHandle } from '$lib/components/editors/editor-contract';
	import { getEditLayoutContext } from '$lib/components/editors/edit-layout-context';
	import {
		defaultFranchiseSectionSegment,
		findFranchiseSectionBySegment
	} from '$lib/components/editors/franchise-edit-sections';
	import { createIsMobileFlag } from '$lib/use-is-mobile.svelte';
	import type { SaveMeta } from '../save-franchise-claims';
	import FranchiseEditorSwitch from '../FranchiseEditorSwitch.svelte';

	let { data } = $props();
	let franchise = $derived(data.franchise);
	let slug = $derived(page.params.slug);
	let sectionSegment = $derived(page.params.section);
	let section = $derived(
		sectionSegment ? findFranchiseSectionBySegment(sectionSegment) : undefined
	);

	const editLayout = getEditLayoutContext();

	let editorRef = $state<SectionEditorHandle>();
	let editError = $state('');
	let saveCounter = $state(0);
	const isMobileFlag = createIsMobileFlag(LAYOUT_BREAKPOINT, null);
	let isMobile = $derived(isMobileFlag.current);

	$effect(() => {
		if (isMobile === true && !section) {
			goto(resolve(`/franchises/${slug}/edit/${defaultFranchiseSectionSegment()}`), {
				replaceState: true
			});
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
		goto(resolve(`/franchises/${slug}`));
	}

	function handleSaved() {
		editLayout.setDirty(false);
		saveCounter++;
	}

	function handleDirtyChange(dirty: boolean) {
		editLayout.setDirty(dirty);
	}
</script>

{#if section}
	{#key `${section.key}:${saveCounter}`}
		<SectionEditorForm
			error={editError}
			showCitation={section.showCitation}
			showMixedEditWarning={section.showMixedEditWarning}
			oncancel={handleCancel}
			onsave={handleSave}
		>
			<FranchiseEditorSwitch
				sectionKey={section.key}
				initialData={franchise}
				slug={franchise.slug}
				bind:editorRef
				onsaved={handleSaved}
				onerror={(msg) => (editError = msg)}
				ondirtychange={handleDirtyChange}
			/>
		</SectionEditorForm>
	{/key}
{/if}
