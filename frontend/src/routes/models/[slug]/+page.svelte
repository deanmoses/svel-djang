<script lang="ts">
	import { tick } from 'svelte';
	import AccordionSection from '$lib/components/AccordionSection.svelte';
	import Markdown from '$lib/components/Markdown.svelte';
	import ModelHierarchy from '$lib/components/ModelHierarchy.svelte';
	import ModelSpecsSidebar from '$lib/components/ModelSpecsSidebar.svelte';
	import CreditsList from '$lib/components/CreditsList.svelte';
	import MediaGrid from '$lib/components/media/MediaGrid.svelte';
	import { MEDIA_CATEGORIES } from '$lib/api/catalog-meta';
	import ReferencesSection from '$lib/components/ReferencesSection.svelte';
	import ModelRelationshipsList from '$lib/components/ModelRelationshipsList.svelte';
	import { modelEditActionContext } from '$lib/components/editors/edit-action-context';
	import {
		deduplicateCitations,
		findFirstInlineMarker,
		findRefEntry,
		scrollToAndHighlight
	} from '$lib/components/citation-refs';

	let { data } = $props();
	let model = $derived(data.model);

	// On desktop, editAction opens the modal editor; on mobile, it navigates to the edit route.
	const editAction = modelEditActionContext.get();

	let isOnlyModelInTitle = $derived(model.title_models.length <= 1);

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
	let hasTechnology = $derived(
		!!model.technology_generation ||
			!!model.technology_subgeneration ||
			!!model.display_type ||
			!!model.display_subtype ||
			!!model.system
	);
	let hasFeatures = $derived(
		!!model.game_format ||
			!!model.cabinet ||
			(model.reward_types?.length ?? 0) > 0 ||
			model.themes.length > 0 ||
			!!model.production_quantity ||
			!!model.player_count ||
			!!model.flipper_count ||
			model.gameplay_features.length > 0 ||
			!!model.franchise ||
			!!model.series ||
			model.variant_features.length > 0
	);
	let peopleHeading = $derived(`People (${model.credits.length})`);
	let mediaHeading = $derived(`Media (${model.uploaded_media.length})`);
	let hasExternalLinks = $derived(!!(model.ipdb_id || model.opdb_id || model.pinside_id));
</script>

<!-- Overview accordion — description prose -->
<AccordionSection heading="Overview" open={true} onEdit={editAction('overview')}>
	{#if (model.title_description?.html && isOnlyModelInTitle) || model.description?.html}
		{#if model.title_description?.html && isOnlyModelInTitle}
			<Markdown html={model.title_description.html} citations={model.title_description.citations} />
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

<!-- Technology — mobile only -->
{#if hasTechnology}
	<div class="mobile-only">
		<AccordionSection heading="Technology" onEdit={editAction('technology')}>
			<ModelSpecsSidebar {model} section="technology" />
		</AccordionSection>
	</div>
{/if}

<!-- Features — mobile only -->
{#if hasFeatures}
	<div class="mobile-only">
		<AccordionSection heading="Features" onEdit={editAction('features')}>
			<ModelSpecsSidebar {model} section="features" />
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
{/if}

<!-- People -->
{#if model.credits.length > 0}
	<AccordionSection heading={peopleHeading} onEdit={editAction('people')}>
		<CreditsList credits={model.credits} showHeading={false} />
	</AccordionSection>
{/if}

<!-- Related Models — mobile only -->
{#if hasRelationships}
	<div class="mobile-only">
		<AccordionSection heading="Related Models" onEdit={editAction('related-models')}>
			<ModelRelationshipsList {model} />
			<ModelHierarchy
				models={model.title_models}
				heading="Other Models In Title"
				excludeSlug={model.variant_of?.slug ?? model.slug}
				inline
			/>
		</AccordionSection>
	</div>
{/if}

<!-- Media -->
{#if model.uploaded_media.length > 0}
	<AccordionSection heading={mediaHeading} onEdit={editAction('media')}>
		<MediaGrid
			media={model.uploaded_media}
			categories={[...MEDIA_CATEGORIES.model]}
			canEdit={false}
		/>
	</AccordionSection>
{/if}

<!-- External Links — mobile only -->
{#if hasExternalLinks}
	<div class="mobile-only">
		<AccordionSection heading="External Links" onEdit={editAction('external-data')}>
			<p class="external-note">See this model on other sites:</p>
			<div class="external-ids">
				{#if model.ipdb_id}
					<a href="https://www.ipdb.org/machine.cgi?id={model.ipdb_id}">
						Internet Pinball Database
					</a>
				{/if}
				{#if model.opdb_id}
					<a href="https://opdb.org/machines/{model.opdb_id}">Open Pinball Database</a>
				{/if}
				{#if model.pinside_id}
					<a href="https://pinside.com/pinball/machine/{model.pinside_id}">Pinside</a>
				{/if}
			</div>
		</AccordionSection>
	</div>
{/if}

<!-- References — only when citations exist -->
{#if allCitations.length > 0}
	<AccordionSection heading="References ({uniqueCitationCount})" bind:open={refsAccordionOpen}>
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

<style>
	.muted {
		color: var(--color-text-muted);
		font-size: var(--font-size-0);
	}

	/* Mobile-only: visible below 52rem — keep in sync with LAYOUT_BREAKPOINT */
	.mobile-only {
		display: block;
	}

	@media (min-width: 52rem) {
		.mobile-only {
			display: none;
		}
	}

	.external-note {
		font-size: var(--font-size-0);
		color: var(--color-text-muted);
		margin: 0 0 var(--size-2);
	}

	.external-ids {
		display: flex;
		flex-wrap: wrap;
		gap: var(--size-3);
		font-size: var(--font-size-0);
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
