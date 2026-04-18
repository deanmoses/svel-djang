<script lang="ts">
	import { tick } from 'svelte';
	import { resolve } from '$app/paths';
	import AccordionSection from '$lib/components/AccordionSection.svelte';
	import CardGrid from '$lib/components/grid/CardGrid.svelte';
	import CreditsList from '$lib/components/CreditsList.svelte';
	import MachineCard from '$lib/components/cards/MachineCard.svelte';
	import Markdown from '$lib/components/Markdown.svelte';
	import MediaGrid from '$lib/components/media/MediaGrid.svelte';
	import ModelSpecsSidebar from '$lib/components/ModelSpecsSidebar.svelte';
	import ReferencesSection from '$lib/components/ReferencesSection.svelte';
	import RelatedTitlesSection from '$lib/components/RelatedTitlesSection.svelte';
	import {
		deduplicateCitations,
		findFirstInlineMarker,
		findRefEntry,
		scrollToAndHighlight
	} from '$lib/components/citation-refs';
	import { titleAreaEditActionContext } from '$lib/components/editors/edit-action-context';

	let { data } = $props();
	let title = $derived(data.title);
	let md = $derived(title.model_detail);
	let specs = $derived(title.agreed_specs);

	// Desktop: opens the layout's SectionEditorHost modal. Mobile: navigates to
	// the appropriate edit route. Returns undefined when unauthenticated.
	const editAction = titleAreaEditActionContext.get();

	let descriptionContentEl: HTMLDivElement | undefined = $state();
	let refsContentEl: HTMLDivElement | undefined = $state();
	let refsAccordionOpen = $state(false);

	function scrollToInlineMarker(index: number) {
		if (!descriptionContentEl) return;
		const marker = findFirstInlineMarker(descriptionContentEl, index);
		if (marker) scrollToAndHighlight(marker);
	}

	async function scrollToRefEntry(index: number) {
		refsAccordionOpen = true;
		await tick();
		if (!refsContentEl) return;
		const entry = findRefEntry(refsContentEl, index);
		if (entry) scrollToAndHighlight(entry);
	}

	// Flatten parents and variants into a single grid — no hierarchy.
	let flatModels = $derived.by(() => {
		const out: Array<{
			slug: string;
			name: string;
			year: number | null | undefined;
			thumbnailUrl: string | null | undefined;
			manufacturerName: string | null;
		}> = [];
		for (const m of title.machines) {
			out.push({
				slug: m.slug,
				name: m.name,
				year: m.year,
				thumbnailUrl: m.thumbnail_url,
				manufacturerName: m.manufacturer?.name ?? null
			});
			for (const v of m.variants ?? []) {
				out.push({
					slug: v.slug,
					name: v.name,
					year: v.year,
					thumbnailUrl: v.thumbnail_url,
					manufacturerName: m.manufacturer?.name ?? null
				});
			}
		}
		return out;
	});

	let hasTechnology = $derived(
		!!(
			specs.technology_generation ||
			specs.technology_subgeneration ||
			specs.display_type ||
			specs.display_subtype ||
			specs.system
		)
	);

	let hasFeatures = $derived(
		!!(
			specs.game_format ||
			specs.cabinet ||
			specs.player_count ||
			specs.flipper_count ||
			specs.production_quantity ||
			(specs.themes && specs.themes.length > 0) ||
			(specs.gameplay_features && specs.gameplay_features.length > 0) ||
			(specs.reward_types && specs.reward_types.length > 0) ||
			(specs.tags && specs.tags.length > 0) ||
			title.franchise ||
			title.series
		)
	);

	let hasExternalLinks = $derived(!!(title.opdb_id || title.fandom_page_id));

	let descriptionCitations = $derived(title.description?.citations ?? []);
	let uniqueDescriptionCitationCount = $derived(deduplicateCitations(descriptionCitations).length);
	let mdDescriptionCitations = $derived(md?.description?.citations ?? []);
	let uniqueMdDescriptionCitationCount = $derived(
		deduplicateCitations(mdDescriptionCitations).length
	);
</script>

{#if md}
	<!-- Single-model title: sections sourced from the one model's detail. -->
	<AccordionSection heading="Overview" open={true} onEdit={editAction('model:overview')}>
		{#if md.description?.html}
			<div bind:this={descriptionContentEl}>
				<Markdown
					html={md.description.html}
					citations={md.description.citations}
					showReferences={false}
					onNavigateToRef={scrollToRefEntry}
				/>
			</div>
		{:else}
			<p class="muted">No description yet.</p>
		{/if}
	</AccordionSection>

	{#if md.technology_generation || md.technology_subgeneration || md.display_type || md.display_subtype || md.system}
		<AccordionSection heading="Technology" onEdit={editAction('model:technology')}>
			<ModelSpecsSidebar model={md} section="technology" />
		</AccordionSection>
	{/if}

	<AccordionSection heading="Features" onEdit={editAction('model:features')}>
		<ModelSpecsSidebar model={md} section="features" />
	</AccordionSection>

	{#if title.related_titles && title.related_titles.length > 0}
		<AccordionSection heading="Related Titles">
			<RelatedTitlesSection relatedTitles={title.related_titles} />
		</AccordionSection>
	{/if}

	{#if md.credits.length > 0}
		<AccordionSection heading="People ({md.credits.length})" onEdit={editAction('model:people')}>
			<CreditsList credits={md.credits} showHeading={false} />
		</AccordionSection>
	{/if}

	{#if md.uploaded_media.length > 0}
		<AccordionSection
			heading="Media ({md.uploaded_media.length})"
			onEdit={editAction('model:media')}
		>
			<MediaGrid media={md.uploaded_media} canEdit={false} />
		</AccordionSection>
	{/if}

	{#if md.ipdb_id || md.opdb_id || md.pinside_id || title.opdb_id || title.fandom_page_id}
		<AccordionSection heading="External Links" onEdit={editAction('model:external-data')}>
			<div class="external-ids">
				{#if md.ipdb_id}
					<a href="https://www.ipdb.org/machine.cgi?id={md.ipdb_id}">Internet Pinball Database</a>
				{/if}
				{#if md.opdb_id}
					<a href="https://opdb.org/machines/{md.opdb_id}">Open Pinball Database</a>
				{/if}
				{#if md.pinside_id}
					<a href="https://pinside.com/pinball/machine/{md.pinside_id}">Pinside</a>
				{/if}
				{#if title.opdb_id}
					<a href="https://opdb.org/groups/{title.opdb_id}">OPDB</a>
				{/if}
				{#if title.fandom_page_id}
					<a href="https://pinball.fandom.com/?curid={title.fandom_page_id}">Pinball Wiki</a>
				{/if}
			</div>
		</AccordionSection>
	{/if}

	{#if mdDescriptionCitations.length > 0}
		<AccordionSection
			heading="References ({uniqueMdDescriptionCitationCount})"
			bind:open={refsAccordionOpen}
		>
			<div bind:this={refsContentEl}>
				<ReferencesSection
					citations={mdDescriptionCitations}
					open={true}
					showToggle={false}
					onBackLink={scrollToInlineMarker}
				/>
			</div>
		</AccordionSection>
	{/if}
{:else}
	<!-- Overview -->
	<AccordionSection heading="Overview" open={true} onEdit={editAction('title:overview')}>
		{#if title.description?.html}
			<div bind:this={descriptionContentEl}>
				<Markdown
					html={title.description.html}
					citations={title.description.citations}
					showReferences={false}
					onNavigateToRef={scrollToRefEntry}
				/>
			</div>
		{:else}
			<p class="muted">No description yet.</p>
		{/if}
	</AccordionSection>

	<!-- Models — flat grid including variants -->
	{#if flatModels.length > 0}
		<AccordionSection heading="Models ({flatModels.length})">
			<CardGrid>
				{#each flatModels as m (m.slug)}
					<MachineCard
						slug={m.slug}
						name={m.name}
						thumbnailUrl={m.thumbnailUrl}
						manufacturerName={m.manufacturerName}
						year={m.year}
					/>
				{/each}
			</CardGrid>
		</AccordionSection>
	{/if}

	<!-- Technology — intersection of models' technology fields -->
	{#if hasTechnology}
		<AccordionSection heading="Technology">
			<dl>
				{#if specs.technology_generation}
					<dt>Generation</dt>
					<dd>
						<a href={resolve(`/technology-generations/${specs.technology_generation.slug}`)}
							>{specs.technology_generation.name}</a
						>
					</dd>
				{/if}
				{#if specs.technology_subgeneration}
					<dt>Subgeneration</dt>
					<dd>
						<a href={resolve(`/technology-subgenerations/${specs.technology_subgeneration.slug}`)}
							>{specs.technology_subgeneration.name}</a
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
				{#if specs.display_subtype}
					<dt>Display Subtype</dt>
					<dd>
						<a href={resolve(`/display-subtypes/${specs.display_subtype.slug}`)}
							>{specs.display_subtype.name}</a
						>
					</dd>
				{/if}
				{#if specs.system}
					<dt>System</dt>
					<dd>
						<a href={resolve(`/systems/${specs.system.slug}`)}>{specs.system.name}</a>
					</dd>
				{/if}
			</dl>
		</AccordionSection>
	{/if}

	<!-- Features — intersection of models' features + franchise / series at title tier -->
	{#if hasFeatures}
		<AccordionSection heading="Features">
			<dl>
				{#if title.franchise}
					<dt>Franchise</dt>
					<dd>
						<a href={resolve(`/franchises/${title.franchise.slug}`)}>{title.franchise.name}</a>
					</dd>
				{/if}
				{#if title.series}
					<dt>Series</dt>
					<dd>
						<a href={resolve(`/series/${title.series.slug}`)}>{title.series.name}</a>
					</dd>
				{/if}
				{#if specs.game_format}
					<dt>Format</dt>
					<dd>
						<a href={resolve(`/game-formats/${specs.game_format.slug}`)}>{specs.game_format.name}</a
						>
					</dd>
				{/if}
				{#if specs.cabinet}
					<dt>Cabinet</dt>
					<dd>
						<a href={resolve(`/cabinets/${specs.cabinet.slug}`)}>{specs.cabinet.name}</a>
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
				{#if specs.themes && specs.themes.length > 0}
					<dt>Themes</dt>
					<dd>
						{#each specs.themes as theme, i (theme.slug)}
							{#if i > 0},
							{/if}
							<a href={resolve(`/themes/${theme.slug}`)}>{theme.name}</a>
						{/each}
					</dd>
				{/if}
				{#if specs.gameplay_features && specs.gameplay_features.length > 0}
					<dt>Gameplay</dt>
					<dd>
						{#each specs.gameplay_features as gf, i (gf.slug)}
							{#if i > 0},
							{/if}
							<a href={resolve(`/gameplay-features/${gf.slug}`)}>{gf.name}</a
							>{#if gf.count}&nbsp;({gf.count}){/if}
						{/each}
					</dd>
				{/if}
				{#if specs.reward_types && specs.reward_types.length > 0}
					<dt>Reward Types</dt>
					<dd>
						{#each specs.reward_types as rt, i (rt.slug)}
							{#if i > 0},
							{/if}
							<a href={resolve(`/reward-types/${rt.slug}`)}>{rt.name}</a>
						{/each}
					</dd>
				{/if}
				{#if specs.tags && specs.tags.length > 0}
					<dt>Tags</dt>
					<dd>
						{#each specs.tags as tag, i (tag.slug)}
							{#if i > 0},
							{/if}
							<a href={resolve(`/tags/${tag.slug}`)}>{tag.name}</a>
						{/each}
					</dd>
				{/if}
			</dl>
		</AccordionSection>
	{/if}

	<!-- Related Titles — union of cross-title conversion/remake links -->
	{#if title.related_titles && title.related_titles.length > 0}
		<AccordionSection heading="Related Titles">
			<RelatedTitlesSection relatedTitles={title.related_titles} />
		</AccordionSection>
	{/if}

	<!-- People — intersection of credits across models -->
	{#if title.credits.length > 0}
		<AccordionSection heading="People ({title.credits.length})">
			<CreditsList credits={title.credits} showHeading={false} />
		</AccordionSection>
	{/if}

	<!-- Media — union across models -->
	{#if title.media.length > 0}
		<AccordionSection heading="Media ({title.media.length})">
			<MediaGrid media={title.media} canEdit={false} />
		</AccordionSection>
	{/if}

	<!-- External Links -->
	{#if hasExternalLinks}
		<AccordionSection heading="External Links" onEdit={editAction('title:external-data')}>
			<div class="external-ids">
				{#if title.opdb_id}
					<a href="https://opdb.org/groups/{title.opdb_id}">OPDB</a>
				{/if}
				{#if title.fandom_page_id}
					<a href="https://pinball.fandom.com/?curid={title.fandom_page_id}">Pinball Wiki</a>
				{/if}
			</div>
		</AccordionSection>
	{/if}

	<!-- References — only when citations exist -->
	{#if descriptionCitations.length > 0}
		<AccordionSection
			heading="References ({uniqueDescriptionCitationCount})"
			bind:open={refsAccordionOpen}
		>
			<div bind:this={refsContentEl}>
				<ReferencesSection
					citations={descriptionCitations}
					open={true}
					showToggle={false}
					onBackLink={scrollToInlineMarker}
				/>
			</div>
		</AccordionSection>
	{/if}
{/if}

<style>
	.muted {
		color: var(--color-text-muted);
	}

	dl {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: var(--size-1) var(--size-3);
		align-items: baseline;
		margin: 0;
	}

	dt,
	dd {
		font-size: var(--font-size-1);
		margin: 0;
	}

	dt {
		color: var(--color-text-muted);
		font-weight: 500;
	}

	.external-ids {
		display: flex;
		flex-direction: column;
		gap: var(--size-2);
	}
</style>
