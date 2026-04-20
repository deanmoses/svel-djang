<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import EditSectionShell from '$lib/components/EditSectionShell.svelte';
	import type { EditSectionMenuItem } from '$lib/components/edit-section-menu';
	import {
		defaultSeriesSectionSegment,
		findSeriesSectionBySegment,
		SERIES_EDIT_SECTIONS
	} from '$lib/components/editors/series-edit-sections';
	import { setEditLayoutContext } from '$lib/components/editors/edit-layout-context';
	import { LAYOUT_BREAKPOINT } from '$lib/constants';
	import { createIsMobileFlag } from '$lib/use-is-mobile.svelte';

	let { children } = $props();
	let slug = $derived(page.params.slug);
	let sectionSegment = $derived(page.params.section);
	let currentSection = $derived(
		sectionSegment ? findSeriesSectionBySegment(sectionSegment) : undefined
	);
	let editorDirty = $state(false);
	const isMobileFlag = createIsMobileFlag(LAYOUT_BREAKPOINT, null);
	let isMobile = $derived(isMobileFlag.current);

	setEditLayoutContext({
		setDirty(dirty: boolean) {
			editorDirty = dirty;
		}
	});

	let switcherItems: EditSectionMenuItem[] = $derived(
		SERIES_EDIT_SECTIONS.map((section) => ({
			key: section.key,
			label: section.label,
			href: resolve(`/series/${slug}/edit/${section.segment}`)
		}))
	);

	$effect(() => {
		if (isMobile !== false) return;
		const segment = currentSection?.segment ?? defaultSeriesSectionSegment();
		goto(resolve(`/series/${slug}?edit=${segment}`), { replaceState: true });
	});
</script>

{#if isMobile === true}
	<EditSectionShell
		detailHref={resolve(`/series/${slug}`)}
		{switcherItems}
		currentSectionKey={currentSection?.key}
		{editorDirty}
	>
		{@render children()}
	</EditSectionShell>
{/if}
