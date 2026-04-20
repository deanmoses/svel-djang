<script lang="ts">
	import type { Snippet } from 'svelte';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { resolveHref } from '$lib/utils';
	import EditSectionShell from '$lib/components/EditSectionShell.svelte';
	import type { EditSectionMenuItem } from '$lib/components/edit-section-menu';
	import {
		defaultSimpleTaxonomySectionSegment,
		findSimpleTaxonomySectionBySegment,
		SIMPLE_TAXONOMY_EDIT_SECTIONS
	} from '$lib/components/editors/simple-taxonomy-edit-sections';
	import { setEditLayoutContext } from '$lib/components/editors/edit-layout-context';
	import { LAYOUT_BREAKPOINT } from '$lib/constants';
	import { createIsMobileFlag } from '$lib/use-is-mobile.svelte';

	let {
		basePath,
		children
	}: {
		basePath: string;
		children: Snippet;
	} = $props();

	let slug = $derived(page.params.slug);
	let sectionSegment = $derived(page.params.section);
	let currentSection = $derived(
		sectionSegment ? findSimpleTaxonomySectionBySegment(sectionSegment) : undefined
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
		SIMPLE_TAXONOMY_EDIT_SECTIONS.map((section) => ({
			key: section.key,
			label: section.label,
			href: resolveHref(`${basePath}/${slug}/edit/${section.segment}`)
		}))
	);

	$effect(() => {
		if (isMobile !== false) return;
		const segment = currentSection?.segment ?? defaultSimpleTaxonomySectionSegment();
		goto(resolveHref(`${basePath}/${slug}?edit=${segment}`), { replaceState: true });
	});
</script>

{#if isMobile === true}
	<EditSectionShell
		detailHref={resolveHref(`${basePath}/${slug}`)}
		{switcherItems}
		currentSectionKey={currentSection?.key}
		{editorDirty}
	>
		{@render children()}
	</EditSectionShell>
{/if}
