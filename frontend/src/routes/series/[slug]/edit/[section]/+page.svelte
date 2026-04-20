<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import SectionEditorForm from '$lib/components/SectionEditorForm.svelte';
	import { LAYOUT_BREAKPOINT } from '$lib/constants';
	import type { SectionEditorHandle } from '$lib/components/editors/editor-contract';
	import { getEditLayoutContext } from '$lib/components/editors/edit-layout-context';
	import {
		defaultSeriesSectionSegment,
		findSeriesSectionBySegment
	} from '$lib/components/editors/series-edit-sections';
	import { createIsMobileFlag } from '$lib/use-is-mobile.svelte';
	import type { SaveMeta } from '../save-series-claims';
	import SeriesEditorSwitch from '../SeriesEditorSwitch.svelte';

	let { data } = $props();
	let series = $derived(data.series);
	let slug = $derived(page.params.slug);
	let sectionSegment = $derived(page.params.section);
	let section = $derived(sectionSegment ? findSeriesSectionBySegment(sectionSegment) : undefined);

	const editLayout = getEditLayoutContext();

	let editorRef = $state<SectionEditorHandle>();
	let editError = $state('');
	let saveCounter = $state(0);
	const isMobileFlag = createIsMobileFlag(LAYOUT_BREAKPOINT, null);
	let isMobile = $derived(isMobileFlag.current);

	$effect(() => {
		if (isMobile === true && !section) {
			goto(resolve(`/series/${slug}/edit/${defaultSeriesSectionSegment()}`), {
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
		goto(resolve(`/series/${slug}`));
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
			<SeriesEditorSwitch
				sectionKey={section.key}
				initialData={series}
				slug={series.slug}
				bind:editorRef
				onsaved={handleSaved}
				onerror={(msg) => (editError = msg)}
				ondirtychange={handleDirtyChange}
			/>
		</SectionEditorForm>
	{/key}
{/if}
