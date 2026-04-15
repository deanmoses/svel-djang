<script lang="ts">
	import { tick } from 'svelte';
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import { auth } from '$lib/auth.svelte';
	import MetaTags from '$lib/components/MetaTags.svelte';
	import AccordionSection from '$lib/components/AccordionSection.svelte';
	import ExternalLinksSidebarSection from '$lib/components/ExternalLinksSidebarSection.svelte';
	import Markdown from '$lib/components/Markdown.svelte';
	import HeroHeader from '$lib/components/HeroHeader.svelte';
	import ModelHierarchy from '$lib/components/ModelHierarchy.svelte';
	import ModelSpecsSidebar from '$lib/components/ModelSpecsSidebar.svelte';
	import PageActionBar from '$lib/components/PageActionBar.svelte';
	import RatingsSidebarSection from '$lib/components/RatingsSidebarSection.svelte';
	import SectionEditorModal from '$lib/components/SectionEditorModal.svelte';
	import SidebarList from '$lib/components/SidebarList.svelte';
	import SidebarListItem from '$lib/components/SidebarListItem.svelte';
	import SidebarSection from '$lib/components/SidebarSection.svelte';
	import TwoColumnLayout from '$lib/components/TwoColumnLayout.svelte';
	import CreditsList from '$lib/components/CreditsList.svelte';
	import MediaGrid from '$lib/components/media/MediaGrid.svelte';
	import { MEDIA_CATEGORIES } from '$lib/api/catalog-meta';
	import ReferencesSection from '$lib/components/ReferencesSection.svelte';
	import ModelRelationshipsList from '$lib/components/ModelRelationshipsList.svelte';
	import OverviewEditor from '$lib/components/editors/OverviewEditor.svelte';
	import {
		deduplicateCitations,
		findFirstInlineMarker,
		findRefEntry,
		scrollToAndHighlight
	} from '$lib/components/citation-refs';

	let { data, children } = $props();
	let model = $derived(data.model);
	let slug = $derived(page.params.slug);

	$effect(() => {
		auth.load();
	});

	let isOnlyModelInTitle = $derived(model.title_models.length <= 1);
	let isMedia = $derived(
		page.url.pathname.endsWith('/media') || page.url.pathname.includes('/media/')
	);
	let isDetail = $derived(
		!page.url.pathname.endsWith('/edit') &&
			!page.url.pathname.endsWith('/sources') &&
			!page.url.pathname.endsWith('/edit-history') &&
			!isMedia
	);
	let isEdit = $derived(page.url.pathname.endsWith('/edit'));

	let metaDescription = $derived.by(() => {
		if (model.description?.text) return model.description.text;
		if (model.title_description?.text) return model.title_description.text;
		const parts = [model.name];
		if (model.year) parts.push(`a ${model.year} pinball machine`);
		else parts.push('pinball machine');
		if (model.manufacturer) parts.push(`by ${model.manufacturer.name}`);
		return parts.join(' — ');
	});

	let parentLink = $derived(
		model.title ? { text: model.title.name, href: resolve(`/titles/${model.title.slug}`) } : null
	);

	let metaItems = $derived.by(() => {
		const items: Array<{ text: string; href?: string }> = [];
		if (model.manufacturer) {
			items.push({
				text: model.manufacturer.name,
				href: resolve(`/manufacturers/${model.manufacturer.slug}`)
			});
		}
		if (model.year) {
			const yearText = model.month
				? `${new Date(model.year, model.month - 1).toLocaleString('en', { month: 'long' })} ${model.year}`
				: `${model.year}`;
			items.push({ text: yearText });
		}
		return items;
	});

	// --- Section editing state ---

	// TODO: add 'specifications' | 'people' | 'relationships' | 'media' as editors are built
	type EditingSection = 'overview';
	let editing = $state<EditingSection | null>(null);
	let editError = $state('');

	let overviewEditorRef: OverviewEditor | undefined = $state();

	function closeEditor() {
		editing = null;
		editError = '';
	}

	async function saveCurrentSection() {
		editError = '';
		if (editing === 'overview') {
			await overviewEditorRef?.save();
		}
	}

	// Only model-owned citations feed the References accordion.
	// title_description citations stay with their own Markdown block
	// to avoid index collisions (each block numbers from [1]).
	let allCitations = $derived(model.description?.citations ?? []);
	let uniqueCitationCount = $derived(deduplicateCitations(allCitations).length);

	// DOM refs for cross-section citation scroll-to.
	// descriptionContentEl scopes to the model description block only,
	// so back-links don't accidentally match title_description markers.
	let descriptionContentEl: HTMLDivElement | undefined = $state();
	let refsContentEl: HTMLDivElement | undefined = $state();
	let refsAccordionOpen = $state(false);

	/** Called from References back-link → scroll to inline marker in model description */
	function scrollToInlineMarker(index: number) {
		if (!descriptionContentEl) return;
		const marker = findFirstInlineMarker(descriptionContentEl, index);
		if (marker) scrollToAndHighlight(marker);
	}

	/** Called from CitationTooltip in Overview → scroll to entry in References */
	async function scrollToRefEntry(index: number) {
		refsAccordionOpen = true;
		await tick();
		if (!refsContentEl) return;
		const entry = findRefEntry(refsContentEl, index);
		if (entry) scrollToAndHighlight(entry);
	}

	// Check if there are any relationships to show
	let hasRelationships = $derived(
		model.title ||
			model.variants.length > 0 ||
			model.variant_of ||
			(model.variant_siblings && model.variant_siblings.length > 0) ||
			model.converted_from ||
			(model.conversions && model.conversions.length > 0) ||
			model.remake_of ||
			(model.remakes && model.remakes.length > 0) ||
			model.title_models.length > 1
	);
</script>

<MetaTags
	title={model.name}
	description={metaDescription}
	url={page.url.href}
	image={model.hero_image_url}
	imageAlt={model.hero_image_url ? `${model.name} pinball machine` : undefined}
/>

<article>
	<HeroHeader
		name={model.name}
		heroImageUrl={model.hero_image_url}
		heroImageAlt="{model.name} backglass"
		{parentLink}
		{metaItems}
	/>

	{#if !isEdit}
		<PageActionBar
			detailHref={isDetail ? undefined : resolve(`/models/${slug}`)}
			editHref={auth.isAuthenticated ? resolve(`/models/${slug}/edit`) : undefined}
			historyHref={resolve(`/models/${slug}/edit-history`)}
			sourcesHref={resolve(`/models/${slug}/sources`)}
		/>
	{/if}

	<TwoColumnLayout>
		{#snippet main()}
			{#if isDetail}
				<!-- Overview accordion — description prose -->
				<AccordionSection
					heading="Overview"
					open={true}
					onEdit={auth.isAuthenticated ? () => (editing = 'overview') : undefined}
				>
					{#if (model.title_description?.html && isOnlyModelInTitle) || model.description?.html}
						{#if model.title_description?.html && isOnlyModelInTitle}
							<Markdown
								html={model.title_description.html}
								citations={model.title_description.citations}
							/>
						{/if}
						{#if model.description?.html}
							<div bind:this={descriptionContentEl}>
								<Markdown
									html={model.description.html}
									citations={model.description.citations}
									showReferences={false}
									onNavigateToRef={scrollToRefEntry}
								/>
							</div>
						{/if}
					{:else}
						<p class="muted">No description yet.</p>
					{/if}
				</AccordionSection>

				<!-- Specifications — mobile only -->
				<div class="mobile-only">
					<AccordionSection heading="Specifications">
						<ModelSpecsSidebar {model} />
						{#if model.ipdb_rating || model.pinside_rating}
							<div class="mobile-ratings">
								{#if model.ipdb_rating}
									<span>IPDB: {model.ipdb_rating.toFixed(1)}</span>
								{/if}
								{#if model.pinside_rating}
									<span>Pinside: {model.pinside_rating.toFixed(1)}</span>
								{/if}
							</div>
						{/if}
					</AccordionSection>
				</div>

				<!-- People -->
				<AccordionSection heading="People">
					<CreditsList credits={model.credits} showHeading={false} />
				</AccordionSection>

				<!-- Relationships — mobile only -->
				{#if hasRelationships}
					<div class="mobile-only">
						<AccordionSection heading="Relationships">
							<ModelRelationshipsList {model} />
						</AccordionSection>
					</div>
				{/if}

				<!-- Media -->
				<AccordionSection heading="Media">
					<MediaGrid
						media={model.uploaded_media}
						categories={[...MEDIA_CATEGORIES.model]}
						canEdit={false}
					/>
				</AccordionSection>

				<!-- References — only when citations exist -->
				{#if allCitations.length > 0}
					<AccordionSection
						heading="References ({uniqueCitationCount})"
						bind:open={refsAccordionOpen}
					>
						<div bind:this={refsContentEl}>
							<ReferencesSection
								citations={allCitations}
								open={true}
								showToggle={false}
								onBackLink={scrollToInlineMarker}
							/>
						</div>
					</AccordionSection>
				{/if}
			{:else}
				<!-- Sub-route content (edit, sources, edit-history, media) -->
				{@render children()}
			{/if}
		{/snippet}

		{#snippet sidebar()}
			<div class:desktop-only={isDetail}>
				<SidebarSection heading="Specifications">
					<ModelSpecsSidebar {model} />
				</SidebarSection>

				<RatingsSidebarSection
					ipdbRating={model.ipdb_rating}
					pinsideRating={model.pinside_rating}
				/>

				{#if model.title}
					<SidebarSection heading="Parent Title">
						<SidebarList>
							<SidebarListItem>
								<a href={resolve(`/titles/${model.title.slug}`)}>{model.title.name}</a>
							</SidebarListItem>
						</SidebarList>
					</SidebarSection>
				{/if}

				{#if model.variants.length > 0}
					<SidebarSection
						heading="Variants of this Model"
						note="These play identically, differing only cosmetically:"
					>
						<SidebarList>
							{#each model.variants as variant (variant.slug)}
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

				{#if model.variant_of}
					<SidebarSection heading="Parent Model">
						<SidebarList>
							<SidebarListItem>
								<a href={resolve(`/models/${model.variant_of.slug}`)}>{model.variant_of.name}</a>
								{#if model.variant_of.year}
									<span class="muted">{model.variant_of.year}</span>
								{/if}
							</SidebarListItem>
						</SidebarList>
					</SidebarSection>
				{/if}

				{#if model.variant_siblings && model.variant_siblings.length > 0}
					<SidebarSection heading="Other Variants">
						<SidebarList>
							{#each model.variant_siblings as sibling (sibling.slug)}
								<SidebarListItem>
									<a href={resolve(`/models/${sibling.slug}`)}>{sibling.name}</a>
									{#if sibling.year}
										<span class="muted">{sibling.year}</span>
									{/if}
								</SidebarListItem>
							{/each}
						</SidebarList>
					</SidebarSection>
				{/if}

				{#if model.converted_from}
					<SidebarSection
						heading="Converted From"
						note="This game was rebuilt from the hardware of:"
					>
						<SidebarList>
							<SidebarListItem>
								<a href={resolve(`/models/${model.converted_from.slug}`)}
									>{model.converted_from.name}</a
								>
								{#if model.converted_from.year}
									<span class="muted">{model.converted_from.year}</span>
								{/if}
							</SidebarListItem>
						</SidebarList>
					</SidebarSection>
				{/if}

				{#if model.conversions && model.conversions.length > 0}
					<SidebarSection
						heading="Conversions"
						note="Different games rebuilt from this machine's hardware:"
					>
						<SidebarList>
							{#each model.conversions as conversion (conversion.slug)}
								<SidebarListItem>
									<a href={resolve(`/models/${conversion.slug}`)}>{conversion.name}</a>
									{#if conversion.year}
										<span class="muted">{conversion.year}</span>
									{/if}
								</SidebarListItem>
							{/each}
						</SidebarList>
					</SidebarSection>
				{/if}

				{#if model.remake_of}
					<SidebarSection heading="Remake Of" note="This game is a remake of:">
						<SidebarList>
							<SidebarListItem>
								<a href={resolve(`/models/${model.remake_of.slug}`)}>{model.remake_of.name}</a>
								{#if model.remake_of.year}
									<span class="muted">{model.remake_of.year}</span>
								{/if}
							</SidebarListItem>
						</SidebarList>
					</SidebarSection>
				{/if}

				{#if model.remakes && model.remakes.length > 0}
					<SidebarSection heading="Remakes" note="Later remakes of this machine:">
						<SidebarList>
							{#each model.remakes as remake (remake.slug)}
								<SidebarListItem>
									<a href={resolve(`/models/${remake.slug}`)}>{remake.name}</a>
									{#if remake.year}
										<span class="muted">{remake.year}</span>
									{/if}
								</SidebarListItem>
							{/each}
						</SidebarList>
					</SidebarSection>
				{/if}

				<ModelHierarchy
					models={model.title_models}
					heading="Other Models In Title"
					excludeSlug={model.variant_of?.slug ?? model.slug}
				/>

				<ExternalLinksSidebarSection
					ipdbId={model.ipdb_id}
					opdbId={model.opdb_id}
					pinsideId={model.pinside_id}
					note="See this model on other sites:"
				/>
			</div>
		{/snippet}
	</TwoColumnLayout>
</article>

<!-- Section editor modals -->
<SectionEditorModal
	heading="Overview"
	open={editing === 'overview'}
	error={editError}
	onclose={closeEditor}
	onsave={saveCurrentSection}
>
	<OverviewEditor
		bind:this={overviewEditorRef}
		initialDescription={model.description?.text ?? ''}
		slug={model.slug}
		onsaved={closeEditor}
		onerror={(msg) => (editError = msg)}
	/>
</SectionEditorModal>

<!-- TODO: Add SectionEditorModals for Specifications, People, Relationships, Media
     as their editor components are built -->

<style>
	.muted {
		color: var(--color-text-muted);
		font-size: var(--font-size-0);
	}

	/* Mobile-only: visible below 52rem (matches TwoColumnLayout breakpoint) */
	.mobile-only {
		display: block;
	}

	/* Desktop-only: hide sidebar content on mobile */
	.desktop-only {
		display: none;
	}

	@media (min-width: 52rem) {
		.mobile-only {
			display: none;
		}

		.desktop-only {
			display: contents;
		}
	}

	/* Mobile ratings supplement */
	.mobile-ratings {
		display: flex;
		gap: var(--size-4);
		margin-top: var(--size-3);
		padding-top: var(--size-3);
		border-top: 1px solid var(--color-border-soft);
		font-size: var(--font-size-0);
		color: var(--color-text-muted);
	}
</style>
