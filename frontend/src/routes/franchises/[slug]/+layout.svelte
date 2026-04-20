<script lang="ts">
	import { goto } from '$app/navigation';
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import { SITE_NAME } from '$lib/constants';
	import { auth } from '$lib/auth.svelte';
	import MetaTags from '$lib/components/MetaTags.svelte';
	import PageActionBar from '$lib/components/PageActionBar.svelte';
	import RecordDetailShell from '$lib/components/RecordDetailShell.svelte';
	import SectionEditorHost from '$lib/components/SectionEditorHost.svelte';
	import { type EditSectionMenuItem } from '$lib/components/edit-section-menu';
	import {
		findFranchiseSectionByKey,
		findFranchiseSectionBySegment,
		FRANCHISE_EDIT_SECTIONS,
		type FranchiseEditSectionKey
	} from '$lib/components/editors/franchise-edit-sections';
	import { LAYOUT_BREAKPOINT } from '$lib/constants';
	import { resolveDetailSubrouteMode } from '$lib/detail-subroute-mode';
	import { createIsMobileFlag } from '$lib/use-is-mobile.svelte';
	import FranchiseEditorSwitch from './edit/FranchiseEditorSwitch.svelte';

	let { data, children } = $props();
	let franchise = $derived(data.franchise);
	let slug = $derived(page.params.slug);

	let metaDescription = $derived(franchise.description?.text || `${franchise.name} — ${SITE_NAME}`);
	let mode = $derived(resolveDetailSubrouteMode(page.url.pathname));
	let isDetail = $derived(mode === 'detail');
	let isEdit = $derived(mode === 'edit');
	const isMobileFlag = createIsMobileFlag(LAYOUT_BREAKPOINT);
	let isMobile = $derived(isMobileFlag.current);
	let editing = $state<FranchiseEditSectionKey | null>(null);
	let syncEnabled = $derived(!isMobile && !isEdit);
	// Tracks the last URL-derived edit section so local modal state doesn't immediately write it back.
	let lastUrlEditing = $state<FranchiseEditSectionKey | null>(null);

	$effect(() => {
		auth.load();
	});

	function updateEditQuery(nextEditing: FranchiseEditSectionKey | null) {
		const current = page.url.searchParams.get('edit') ?? null;
		const desired = nextEditing ? (findFranchiseSectionByKey(nextEditing)?.segment ?? null) : null;
		if (current === desired) return;
		const url = new URL(page.url);
		if (desired) url.searchParams.set('edit', desired);
		else url.searchParams.delete('edit');
		goto(`${url.pathname}${url.search}`, { replaceState: true, noScroll: true, keepFocus: true });
	}

	function resolveEditingFromUrl(): FranchiseEditSectionKey | null {
		if (!syncEnabled) return null;
		const section = page.url.searchParams.get('edit');
		const matched = section ? findFranchiseSectionBySegment(section) : undefined;
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
		FRANCHISE_EDIT_SECTIONS.map((section) =>
			isMobile
				? {
						key: section.key,
						label: section.label,
						href: resolve(`/franchises/${slug}/edit/${section.segment}`)
					}
				: {
						key: section.key,
						label: section.label,
						onclick: () => (editing = section.key)
					}
		)
	);
</script>

<MetaTags title={franchise.name} description={metaDescription} url={page.url.href} />

{#if isEdit}
	{@render children()}
{:else}
	{#snippet actionBar()}
		<PageActionBar
			detailHref={isDetail ? undefined : resolve(`/franchises/${slug}`)}
			editSections={auth.isAuthenticated ? editSections : undefined}
			historyHref={resolve(`/franchises/${slug}/edit-history`)}
			sourcesHref={resolve(`/franchises/${slug}/sources`)}
		/>
	{/snippet}

	{#snippet main()}
		{@render children()}
	{/snippet}

	<RecordDetailShell
		name={franchise.name}
		parentLink={{ text: 'Franchises', href: resolve('/franchises') }}
		{actionBar}
		{main}
	/>

	<SectionEditorHost
		bind:editingKey={editing}
		sections={FRANCHISE_EDIT_SECTIONS}
		switcherItems={editSections}
	>
		{#snippet editor(key, { ref, onsaved, onerror, ondirtychange })}
			<FranchiseEditorSwitch
				sectionKey={key}
				initialData={franchise}
				slug={franchise.slug}
				bind:editorRef={ref.current}
				{onsaved}
				{onerror}
				{ondirtychange}
			/>
		{/snippet}
	</SectionEditorHost>
{/if}
