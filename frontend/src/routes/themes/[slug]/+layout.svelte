<script lang="ts">
	import client from '$lib/api/client';
	import TaxonomyDetailBaseLayout from '$lib/components/TaxonomyDetailBaseLayout.svelte';
	import HierarchicalTaxonomySidebar from '$lib/components/HierarchicalTaxonomySidebar.svelte';
	import HierarchicalTaxonomyEditorSwitch from '$lib/components/editors/HierarchicalTaxonomyEditorSwitch.svelte';
	import { hierarchicalTaxonomyEditActionContext } from '$lib/components/editors/edit-action-context';
	import {
		HIERARCHICAL_TAXONOMY_EDIT_SECTIONS,
		type HierarchicalTaxonomyEditSectionKey
	} from '$lib/components/editors/hierarchical-taxonomy-edit-sections';
	import { saveThemeClaims } from './save-theme-claims';

	let { data, children } = $props();
	let theme = $derived(data.theme);

	const BASE_PATH = '/themes';

	const sections = HIERARCHICAL_TAXONOMY_EDIT_SECTIONS.map((section) =>
		section.key === 'parents' ? { ...section, label: 'Parent Themes' } : section
	);

	// Unlike gameplay-features, themes has historically shown aliases verbatim
	// (no near-duplicate filter against the canonical name). Preserve that.
	let aliases = $derived(theme.aliases ?? []);
	let childHeading = $derived(`Sub-themes (${theme.children?.length ?? 0})`);

	async function loadParentOptions() {
		const { data: themes } = await client.GET('/api/themes/');
		if (!themes) return [];
		return themes.map((t) => ({
			slug: t.slug,
			label: t.name
		}));
	}
</script>

<TaxonomyDetailBaseLayout
	profile={theme}
	parentLabel="Themes"
	basePath={BASE_PATH}
	{sections}
	editActionContext={hierarchicalTaxonomyEditActionContext}
>
	{#snippet sidebar()}
		<HierarchicalTaxonomySidebar
			basePath={BASE_PATH}
			parents={theme.parents ?? []}
			children={theme.children ?? []}
			{aliases}
			parentHeading="Parent themes"
			{childHeading}
		/>
	{/snippet}

	{#snippet editor(
		key: HierarchicalTaxonomyEditSectionKey,
		{ ref, onsaved, onerror, ondirtychange }
	)}
		<HierarchicalTaxonomyEditorSwitch
			sectionKey={key}
			initialData={theme}
			slug={theme.slug}
			saveClaims={saveThemeClaims}
			parentOptionsLoader={loadParentOptions}
			bind:editorRef={ref.current}
			{onsaved}
			{onerror}
			{ondirtychange}
		/>
	{/snippet}

	{@render children()}
</TaxonomyDetailBaseLayout>
