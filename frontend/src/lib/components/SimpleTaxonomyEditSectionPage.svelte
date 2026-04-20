<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { resolveHref } from '$lib/utils';
	import SectionEditorForm from '$lib/components/SectionEditorForm.svelte';
	import { LAYOUT_BREAKPOINT } from '$lib/constants';
	import type { SectionEditorHandle } from '$lib/components/editors/editor-contract';
	import { getEditLayoutContext } from '$lib/components/editors/edit-layout-context';
	import {
		defaultSimpleTaxonomySectionSegment,
		findSimpleTaxonomySectionBySegment
	} from '$lib/components/editors/simple-taxonomy-edit-sections';
	import SimpleTaxonomyEditorSwitch from '$lib/components/editors/SimpleTaxonomyEditorSwitch.svelte';
	import type { SaveMeta } from '$lib/components/editors/save-claims-shared';
	import type {
		SaveSimpleTaxonomyClaims,
		SimpleTaxonomyEditView
	} from '$lib/components/editors/simple-taxonomy-edit-types';
	import { createIsMobileFlag } from '$lib/use-is-mobile.svelte';

	let {
		profile,
		basePath,
		saveClaims
	}: {
		profile: SimpleTaxonomyEditView;
		basePath: string;
		saveClaims: SaveSimpleTaxonomyClaims;
	} = $props();

	let slug = $derived(page.params.slug);
	let sectionSegment = $derived(page.params.section);
	let section = $derived(
		sectionSegment ? findSimpleTaxonomySectionBySegment(sectionSegment) : undefined
	);

	const editLayout = getEditLayoutContext();

	let editorRef = $state<SectionEditorHandle>();
	let editError = $state('');
	let saveCounter = $state(0);
	const isMobileFlag = createIsMobileFlag(LAYOUT_BREAKPOINT, null);
	let isMobile = $derived(isMobileFlag.current);

	$effect(() => {
		if (isMobile === true && !section) {
			goto(resolveHref(`${basePath}/${slug}/edit/${defaultSimpleTaxonomySectionSegment()}`), {
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
		goto(resolveHref(`${basePath}/${slug}`));
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
			<SimpleTaxonomyEditorSwitch
				sectionKey={section.key}
				initialData={profile}
				slug={profile.slug}
				{saveClaims}
				bind:editorRef
				onsaved={handleSaved}
				onerror={(msg) => (editError = msg)}
				ondirtychange={handleDirtyChange}
			/>
		</SectionEditorForm>
	{/key}
{/if}
