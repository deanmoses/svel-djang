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
		findSeriesSectionByKey,
		findSeriesSectionBySegment,
		SERIES_EDIT_SECTIONS,
		type SeriesEditSectionKey
	} from '$lib/components/editors/series-edit-sections';
	import { LAYOUT_BREAKPOINT } from '$lib/constants';
	import { resolveDetailSubrouteMode } from '$lib/detail-subroute-mode';
	import { createIsMobileFlag } from '$lib/use-is-mobile.svelte';
	import SeriesEditorSwitch from './edit/SeriesEditorSwitch.svelte';

	let { data, children } = $props();
	let series = $derived(data.series);
	let slug = $derived(page.params.slug);

	let metaDescription = $derived(series.description?.text || `${series.name} — ${SITE_NAME}`);
	let mode = $derived(resolveDetailSubrouteMode(page.url.pathname));
	let isDetail = $derived(mode === 'detail');
	let isEdit = $derived(mode === 'edit');
	const isMobileFlag = createIsMobileFlag(LAYOUT_BREAKPOINT);
	let isMobile = $derived(isMobileFlag.current);
	let editing = $state<SeriesEditSectionKey | null>(null);
	let syncEnabled = $derived(!isMobile && !isEdit);
	// Tracks the last URL-derived edit section so local modal state doesn't immediately write it back.
	let lastUrlEditing = $state<SeriesEditSectionKey | null>(null);

	$effect(() => {
		auth.load();
	});

	function updateEditQuery(nextEditing: SeriesEditSectionKey | null) {
		const current = page.url.searchParams.get('edit') ?? null;
		const desired = nextEditing ? (findSeriesSectionByKey(nextEditing)?.segment ?? null) : null;
		if (current === desired) return;
		const url = new URL(page.url);
		if (desired) url.searchParams.set('edit', desired);
		else url.searchParams.delete('edit');
		goto(`${url.pathname}${url.search}`, { replaceState: true, noScroll: true, keepFocus: true });
	}

	function resolveEditingFromUrl(): SeriesEditSectionKey | null {
		if (!syncEnabled) return null;
		const section = page.url.searchParams.get('edit');
		const matched = section ? findSeriesSectionBySegment(section) : undefined;
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
		SERIES_EDIT_SECTIONS.map((section) =>
			isMobile
				? {
						key: section.key,
						label: section.label,
						href: resolve(`/series/${slug}/edit/${section.segment}`)
					}
				: {
						key: section.key,
						label: section.label,
						onclick: () => (editing = section.key)
					}
		)
	);
</script>

<MetaTags title={series.name} description={metaDescription} url={page.url.href} />

{#if isEdit}
	{@render children()}
{:else}
	{#snippet actionBar()}
		<PageActionBar
			detailHref={isDetail ? undefined : resolve(`/series/${slug}`)}
			editSections={auth.isAuthenticated ? editSections : undefined}
			historyHref={resolve(`/series/${slug}/edit-history`)}
			sourcesHref={resolve(`/series/${slug}/sources`)}
		/>
	{/snippet}

	{#snippet main()}
		{@render children()}
	{/snippet}

	<RecordDetailShell
		name={series.name}
		parentLink={{ text: 'Series', href: resolve('/series') }}
		{actionBar}
		{main}
	/>

	<SectionEditorHost
		bind:editingKey={editing}
		sections={SERIES_EDIT_SECTIONS.map((section) => ({
			...section,
			usesSectionEditorForm: true
		}))}
		switcherItems={editSections}
	>
		{#snippet editor(key, { ref, onsaved, onerror, ondirtychange })}
			<SeriesEditorSwitch
				sectionKey={key}
				initialData={series}
				slug={series.slug}
				bind:editorRef={ref.current}
				{onsaved}
				{onerror}
				{ondirtychange}
			/>
		{/snippet}
	</SectionEditorHost>
{/if}
