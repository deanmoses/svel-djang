<script lang="ts">
	import type { Snippet } from 'svelte';
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { resolveHref } from '$lib/utils';
	import { SITE_NAME } from '$lib/constants';
	import { auth } from '$lib/auth.svelte';
	import MetaTags from '$lib/components/MetaTags.svelte';
	import PageActionBar from '$lib/components/PageActionBar.svelte';
	import RecordDetailShell from '$lib/components/RecordDetailShell.svelte';
	import SectionEditorHost from '$lib/components/SectionEditorHost.svelte';
	import { type EditSectionMenuItem } from '$lib/components/edit-section-menu';
	import {
		findSimpleTaxonomySectionByKey,
		findSimpleTaxonomySectionBySegment,
		SIMPLE_TAXONOMY_EDIT_SECTIONS,
		type SimpleTaxonomyEditSectionKey
	} from '$lib/components/editors/simple-taxonomy-edit-sections';
	import SimpleTaxonomyEditorSwitch from '$lib/components/editors/SimpleTaxonomyEditorSwitch.svelte';
	import type {
		SaveSimpleTaxonomyClaims,
		SimpleTaxonomyEditView
	} from '$lib/components/editors/simple-taxonomy-edit-types';
	import { LAYOUT_BREAKPOINT } from '$lib/constants';
	import { resolveDetailSubrouteMode } from '$lib/detail-subroute-mode';
	import { createIsMobileFlag } from '$lib/use-is-mobile.svelte';

	let {
		profile,
		parentLabel,
		basePath,
		saveClaims,
		children
	}: {
		profile: SimpleTaxonomyEditView;
		parentLabel: string;
		basePath: string;
		saveClaims: SaveSimpleTaxonomyClaims;
		children: Snippet;
	} = $props();

	let slug = $derived(page.params.slug);

	let metaDescription = $derived(profile.description.text || `${profile.name} — ${SITE_NAME}`);
	let mode = $derived(resolveDetailSubrouteMode(page.url.pathname));
	let isDetail = $derived(mode === 'detail');
	let isEdit = $derived(mode === 'edit');
	const isMobileFlag = createIsMobileFlag(LAYOUT_BREAKPOINT);
	let isMobile = $derived(isMobileFlag.current);
	let editing = $state<SimpleTaxonomyEditSectionKey | null>(null);
	let syncEnabled = $derived(!isMobile && !isEdit);
	let lastUrlEditing = $state<SimpleTaxonomyEditSectionKey | null>(null);

	$effect(() => {
		auth.load();
	});

	function updateEditQuery(nextEditing: SimpleTaxonomyEditSectionKey | null) {
		const current = page.url.searchParams.get('edit') ?? null;
		const desired = nextEditing
			? (findSimpleTaxonomySectionByKey(nextEditing)?.segment ?? null)
			: null;
		if (current === desired) return;
		const url = new URL(page.url);
		if (desired) url.searchParams.set('edit', desired);
		else url.searchParams.delete('edit');
		goto(`${url.pathname}${url.search}`, { replaceState: true, noScroll: true, keepFocus: true });
	}

	function resolveEditingFromUrl(): SimpleTaxonomyEditSectionKey | null {
		if (!syncEnabled) return null;
		const section = page.url.searchParams.get('edit');
		const matched = section ? findSimpleTaxonomySectionBySegment(section) : undefined;
		return matched?.key ?? null;
	}

	$effect(() => {
		const nextEditing = resolveEditingFromUrl();
		lastUrlEditing = nextEditing;
		editing = nextEditing;
	});

	$effect(() => {
		if (!syncEnabled) return;
		if (editing === lastUrlEditing) return;
		lastUrlEditing = editing;
		updateEditQuery(editing);
	});

	let editSections: EditSectionMenuItem[] = $derived(
		SIMPLE_TAXONOMY_EDIT_SECTIONS.map((section) =>
			isMobile
				? {
						key: section.key,
						label: section.label,
						href: resolveHref(`${basePath}/${slug}/edit/${section.segment}`)
					}
				: {
						key: section.key,
						label: section.label,
						onclick: () => (editing = section.key)
					}
		)
	);
</script>

<MetaTags title={profile.name} description={metaDescription} url={page.url.href} />

{#if isEdit}
	{@render children()}
{:else}
	{#snippet actionBar()}
		<PageActionBar
			detailHref={isDetail ? undefined : resolveHref(`${basePath}/${slug}`)}
			editSections={auth.isAuthenticated ? editSections : undefined}
			historyHref={resolveHref(`${basePath}/${slug}/edit-history`)}
			sourcesHref={resolveHref(`${basePath}/${slug}/sources`)}
		/>
	{/snippet}

	{#snippet main()}
		{@render children()}
	{/snippet}

	<RecordDetailShell
		name={profile.name}
		parentLink={{ text: parentLabel, href: resolveHref(basePath) }}
		{actionBar}
		{main}
	/>

	<SectionEditorHost
		bind:editingKey={editing}
		sections={SIMPLE_TAXONOMY_EDIT_SECTIONS.map((section) => ({
			...section,
			usesSectionEditorForm: true
		}))}
		switcherItems={editSections}
	>
		{#snippet editor(key, { ref, onsaved, onerror, ondirtychange })}
			<SimpleTaxonomyEditorSwitch
				sectionKey={key}
				initialData={profile}
				slug={profile.slug}
				{saveClaims}
				bind:editorRef={ref.current}
				{onsaved}
				{onerror}
				{ondirtychange}
			/>
		{/snippet}
	</SectionEditorHost>
{/if}
