<script lang="ts">
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { auth } from '$lib/auth.svelte';
	import MetaTags from '$lib/components/MetaTags.svelte';
	import ExternalLinksSidebarSection from '$lib/components/ExternalLinksSidebarSection.svelte';
	import ModelHierarchy from '$lib/components/ModelHierarchy.svelte';
	import ModelSpecsSidebar from '$lib/components/ModelSpecsSidebar.svelte';
	import PageActionBar from '$lib/components/PageActionBar.svelte';
	import RatingsSidebarSection from '$lib/components/RatingsSidebarSection.svelte';
	import RecordDetailShell from '$lib/components/RecordDetailShell.svelte';
	import SectionEditorHost from '$lib/components/SectionEditorHost.svelte';
	import SidebarList from '$lib/components/SidebarList.svelte';
	import SidebarListItem from '$lib/components/SidebarListItem.svelte';
	import SidebarSection from '$lib/components/SidebarSection.svelte';
	import TaxonomyLinkSidebarSection from '$lib/components/TaxonomyLinkSidebarSection.svelte';
	import NeedsReviewBanner from '$lib/components/NeedsReviewBanner.svelte';
	import { MEDIA_CATEGORIES } from '$lib/api/catalog-meta';
	import { getMenuItemAction, type EditSectionMenuItem } from '$lib/components/edit-section-menu';
	import { LAYOUT_BREAKPOINT } from '$lib/constants';
	import {
		combinedSectionsFor,
		type CombinedSectionKey
	} from '$lib/components/editors/combined-edit-sections';
	import { modelHasTitleOwnedIdentity } from '$lib/catalog-rules';
	import { setTitleAreaEditActionContext } from '$lib/components/editors/edit-action-context';
	import BasicsEditor from '$lib/components/editors/BasicsEditor.svelte';
	import ExternalDataEditor from '$lib/components/editors/ExternalDataEditor.svelte';
	import FeaturesEditor from '$lib/components/editors/FeaturesEditor.svelte';
	import MediaEditor from '$lib/components/editors/MediaEditor.svelte';
	import OverviewEditor from '$lib/components/editors/OverviewEditor.svelte';
	import PeopleEditor from '$lib/components/editors/PeopleEditor.svelte';
	import RelatedModelsEditor from '$lib/components/editors/RelatedModelsEditor.svelte';
	import TechnologyEditor from '$lib/components/editors/TechnologyEditor.svelte';
	import TitleBasicsEditor from '$lib/components/editors/TitleBasicsEditor.svelte';
	import TitleExternalDataEditor from '$lib/components/editors/TitleExternalDataEditor.svelte';
	import TitleOverviewEditor from '$lib/components/editors/TitleOverviewEditor.svelte';

	let { data, children } = $props();
	let title = $derived(data.title);
	let md = $derived(title.model_detail);
	let specs = $derived(title.agreed_specs);
	let slug = $derived(page.params.slug);

	$effect(() => {
		auth.load();
	});

	let isEdit = $derived(
		page.url.pathname.endsWith('/edit') || page.url.pathname.includes('/edit/')
	);
	let isDetail = $derived(
		!isEdit &&
			!page.url.pathname.endsWith('/sources') &&
			!page.url.pathname.endsWith('/edit-history') &&
			!page.url.pathname.includes('/media')
	);

	// Mobile detection — matches TwoColumnLayout breakpoint (LAYOUT_BREAKPOINT)
	let isMobile = $state(false);
	$effect(() => {
		const mql = matchMedia(`(max-width: ${LAYOUT_BREAKPOINT}rem)`);
		isMobile = mql.matches;
		function onChange(e: MediaQueryListEvent) {
			isMobile = e.matches;
		}
		mql.addEventListener('change', onChange);
		return () => mql.removeEventListener('change', onChange);
	});

	let metaDescription = $derived.by(() => {
		if (title.description?.text) return title.description.text;
		const parts = [title.name];
		if (md?.year) parts.push(`a ${md.year} pinball machine`);
		else parts.push('pinball title');
		if (md?.manufacturer) parts.push(`by ${md.manufacturer.name}`);
		return parts.join(' — ');
	});
	let heroImage = $derived(md ? md.hero_image_url : title.hero_image_url);

	let metaItems = $derived.by(() => {
		if (!md) return [];
		const items: Array<{ text: string; href?: string }> = [];
		if (md.manufacturer) {
			items.push({
				text: md.manufacturer.name,
				href: resolve(`/manufacturers/${md.manufacturer.slug}`)
			});
		}
		if (md.year) {
			const yearText = md.month
				? `${new Date(md.year, md.month - 1).toLocaleString('en', { month: 'long' })} ${md.year}`
				: `${md.year}`;
			items.push({ text: yearText });
		}
		return items;
	});

	// --- Combined-menu edit state ---

	let sections = $derived(combinedSectionsFor(!!md));
	let editing = $state<CombinedSectionKey | null>(null);

	let switcherItems: EditSectionMenuItem[] = $derived(
		sections.map((s) => {
			if (!isMobile) {
				return { key: s.key, label: s.menuLabel, onclick: () => (editing = s.key) };
			}
			if (s.tier === 'title') {
				return {
					key: s.key,
					label: s.menuLabel,
					href: resolve(`/titles/${slug}/edit/${s.segment}`)
				};
			}
			// combinedSectionsFor only emits model-tier entries when md exists.
			if (!md) throw new Error('unreachable: model-tier section without model_detail');
			// The model edit route reads the model's title_models count to decide
			// whether BasicsEditor renders in slim mode — no entry-point signaling
			// needed here.
			return {
				key: s.key,
				label: s.menuLabel,
				href: resolve(`/models/${md.slug}/edit/${s.segment}`)
			};
		})
	);

	let editSectionsForBar = $derived(auth.isAuthenticated ? switcherItems : undefined);

	function editAction(key: CombinedSectionKey): (() => void) | undefined {
		if (!auth.isAuthenticated) return undefined;
		return getMenuItemAction(switcherItems, key, (href) => goto(href));
	}

	setTitleAreaEditActionContext(editAction);
</script>

<MetaTags
	title={title.name}
	description={metaDescription}
	url={page.url.href}
	image={heroImage}
	imageAlt={heroImage ? `${title.name} pinball machine` : undefined}
/>

{#if title.needs_review}
	<NeedsReviewBanner notes={title.needs_review_notes} links={title.review_links} />
{/if}

<RecordDetailShell
	name={title.name}
	heroImageUrl={md ? md.hero_image_url : title.hero_image_url}
	heroImageAlt="{title.name} backglass"
	{metaItems}
	sidebarDesktopOnly={isDetail}
>
	{#snippet actionBar()}
		{#if !isEdit}
			<PageActionBar
				editSections={editSectionsForBar}
				historyHref={resolve(`/titles/${slug}/edit-history`)}
				sourcesHref={resolve(`/titles/${slug}/sources`)}
			/>
		{/if}
	{/snippet}

	{#snippet main()}
		{@render children()}
	{/snippet}

	{#snippet sidebar()}
		{#if md}
			<SidebarSection heading="Specifications">
				<ModelSpecsSidebar model={md} />
			</SidebarSection>

			<RatingsSidebarSection ipdbRating={md.ipdb_rating} pinsideRating={md.pinside_rating} />

			{#if md.variants.length > 0}
				<SidebarSection heading="Variants">
					<SidebarList>
						{#each md.variants as variant (variant.slug)}
							<SidebarListItem>
								<a href={resolve(`/models/${variant.slug}`)}>{variant.name}</a>
								{#if variant.year}
									<span class="muted">{variant.year}</span>
								{/if}
							</SidebarListItem>
						{/each}
					</SidebarList>
				</SidebarSection>
			{/if}

			<ExternalLinksSidebarSection
				ipdbId={md.ipdb_id}
				opdbId={md.opdb_id}
				pinsideId={md.pinside_id}
				note="See this title on other sites:"
			/>
		{:else}
			{#if specs.technology_generation || specs.display_type || specs.player_count || specs.system || specs.cabinet || specs.game_format || specs.display_subtype || specs.production_quantity || (specs.themes && specs.themes.length > 0) || title.abbreviations.length > 0}
				<SidebarSection heading="Specifications">
					<dl>
						{#if specs.technology_generation}
							<dt>Generation</dt>
							<dd>
								<a href={resolve(`/technology-generations/${specs.technology_generation.slug}`)}
									>{specs.technology_generation.name}</a
								>
							</dd>
						{/if}
						{#if specs.display_type}
							<dt>Display Type</dt>
							<dd>
								<a href={resolve(`/display-types/${specs.display_type.slug}`)}
									>{specs.display_type.name}</a
								>
							</dd>
						{/if}
						{#if specs.player_count}
							<dt>Players</dt>
							<dd>{specs.player_count}</dd>
						{/if}
						{#if specs.flipper_count}
							<dt>Flippers</dt>
							<dd>{specs.flipper_count}</dd>
						{/if}
						{#if specs.production_quantity}
							<dt>Units Made</dt>
							<dd>{specs.production_quantity}</dd>
						{/if}
						{#if specs.system}
							<dt>System</dt>
							<dd>
								<a href={resolve(`/systems/${specs.system.slug}`)}>{specs.system.name}</a>
							</dd>
						{/if}
						{#if specs.themes && specs.themes.length > 0}
							<dt>Themes</dt>
							<dd>
								{#each specs.themes as theme, i (theme.slug)}
									{#if i > 0},{/if}
									<a href={resolve(`/themes/${theme.slug}`)}>{theme.name}</a>
								{/each}
							</dd>
						{/if}
						{#if specs.gameplay_features && specs.gameplay_features.length > 0}
							<dt>Features</dt>
							<dd>
								{#each specs.gameplay_features as feature, i (feature.slug)}
									{#if i > 0},{/if}
									<a href={resolve(`/gameplay-features/${feature.slug}`)}>{feature.name}</a
									>{#if feature.count}&nbsp;({feature.count}){/if}
								{/each}
							</dd>
						{/if}
						{#if specs.reward_types && specs.reward_types.length > 0}
							<dt>Reward Types</dt>
							<dd>
								{#each specs.reward_types as rt, i (rt.slug)}
									{#if i > 0},{/if}
									<a href={resolve(`/reward-types/${rt.slug}`)}>{rt.name}</a>
								{/each}
							</dd>
						{/if}
						{#if title.abbreviations.length > 0}
							<dt>Abbrs</dt>
							<dd>{title.abbreviations.join(', ')}</dd>
						{/if}
						{#if specs.cabinet}
							<dt>Cabinet</dt>
							<dd>
								<a href={resolve(`/cabinets/${specs.cabinet.slug}`)}>{specs.cabinet.name}</a>
							</dd>
						{/if}
						{#if specs.game_format}
							<dt>Format</dt>
							<dd>
								<a href={resolve(`/game-formats/${specs.game_format.slug}`)}
									>{specs.game_format.name}</a
								>
							</dd>
						{/if}
						{#if specs.display_subtype}
							<dt>Display</dt>
							<dd>
								<a href={resolve(`/display-subtypes/${specs.display_subtype.slug}`)}
									>{specs.display_subtype.name}</a
								>
							</dd>
						{/if}
					</dl>
				</SidebarSection>
			{/if}

			<TaxonomyLinkSidebarSection
				heading="Franchise"
				basePath="/franchises"
				item={title.franchise}
			/>
			<TaxonomyLinkSidebarSection heading="Series" basePath="/series" item={title.series} />

			{#if title.machines.length > 0}
				<ModelHierarchy models={title.machines} />
			{/if}
		{/if}
	{/snippet}
</RecordDetailShell>

<SectionEditorHost bind:editingKey={editing} {sections} {switcherItems}>
	{#snippet editor(key, { ref, onsaved, onerror, ondirtychange })}
		{#if key === 'title:overview'}
			<TitleOverviewEditor
				bind:this={ref.current}
				initialData={title.description?.text ?? ''}
				slug={title.slug}
				{onsaved}
				{onerror}
				{ondirtychange}
			/>
		{:else if key === 'title:basics'}
			<TitleBasicsEditor
				bind:this={ref.current}
				initialData={title}
				slug={title.slug}
				{onsaved}
				{onerror}
				{ondirtychange}
			/>
		{:else if key === 'title:external-data'}
			<TitleExternalDataEditor
				bind:this={ref.current}
				initialData={title}
				slug={title.slug}
				{onsaved}
				{onerror}
				{ondirtychange}
			/>
		{:else if md && key === 'model:overview'}
			<OverviewEditor
				bind:this={ref.current}
				initialData={md.description?.text ?? ''}
				slug={md.slug}
				{onsaved}
				{onerror}
				{ondirtychange}
			/>
		{:else if md && key === 'model:basics'}
			<BasicsEditor
				bind:this={ref.current}
				initialData={md}
				slug={md.slug}
				slim={modelHasTitleOwnedIdentity(md)}
				{onsaved}
				{onerror}
				{ondirtychange}
			/>
		{:else if md && key === 'model:technology'}
			<TechnologyEditor
				bind:this={ref.current}
				initialData={md}
				slug={md.slug}
				{onsaved}
				{onerror}
				{ondirtychange}
			/>
		{:else if md && key === 'model:features'}
			<FeaturesEditor
				bind:this={ref.current}
				initialData={md}
				slug={md.slug}
				{onsaved}
				{onerror}
				{ondirtychange}
			/>
		{:else if md && key === 'model:people'}
			<PeopleEditor
				bind:this={ref.current}
				initialData={md.credits}
				slug={md.slug}
				{onsaved}
				{onerror}
				{ondirtychange}
			/>
		{:else if md && key === 'model:related-models'}
			<RelatedModelsEditor
				bind:this={ref.current}
				initialData={md}
				slug={md.slug}
				{onsaved}
				{onerror}
				{ondirtychange}
			/>
		{:else if md && key === 'model:external-data'}
			<ExternalDataEditor
				bind:this={ref.current}
				initialData={md}
				slug={md.slug}
				{onsaved}
				{onerror}
				{ondirtychange}
			/>
		{/if}
	{/snippet}

	{#snippet immediateEditor()}
		{#if md}
			<MediaEditor
				entityType="model"
				slug={md.slug}
				media={md.uploaded_media}
				categories={[...MEDIA_CATEGORIES.model]}
			/>
		{/if}
	{/snippet}
</SectionEditorHost>

<style>
	dl {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0 var(--size-3);
		align-items: baseline;
	}

	dt,
	dd {
		font-size: var(--font-size-0);
		margin: 0;
		padding: 2px 0;
	}

	dt {
		color: var(--color-text-muted);
		font-weight: 500;
	}

	dd {
		color: var(--color-text-primary);
	}

	.muted {
		color: var(--color-text-muted);
		font-size: var(--font-size-0);
	}
</style>
