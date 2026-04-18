<script lang="ts">
	import { resolve } from '$app/paths';
	import { MEDIA_CATEGORIES } from '$lib/api/catalog-meta';
	import AccordionSection from '$lib/components/AccordionSection.svelte';
	import RichTextAccordionReader from '$lib/components/RichTextAccordionReader.svelte';
	import TitleCard from '$lib/components/cards/TitleCard.svelte';
	import { manufacturerEditActionContext } from '$lib/components/editors/edit-action-context';
	import SearchableGrid from '$lib/components/grid/SearchableGrid.svelte';
	import LocationLink from '$lib/components/LocationLink.svelte';
	import MediaGrid from '$lib/components/media/MediaGrid.svelte';
	import { formatYearRange } from '$lib/utils';

	let { data } = $props();
	let mfr = $derived(data.manufacturer);
	let editAction = manufacturerEditActionContext.get();

	let yearsActive = $derived(formatYearRange(mfr.year_start, mfr.year_end));
	let hasEntityLocations = $derived(mfr.entities.some((entity) => entity.locations.length > 0));
	let titlesHeading = $derived(`Titles (${mfr.titles.length})`);
	let systemsHeading = $derived(`Systems (${mfr.systems.length})`);
	let peopleHeading = $derived(`People (${mfr.persons.length})`);
	let mediaHeading = $derived(`Media (${mfr.uploaded_media.length})`);

	function websiteHostname(url: string): string {
		try {
			return new URL(url).hostname;
		} catch {
			return url;
		}
	}
</script>

<RichTextAccordionReader richText={mfr.description} onEdit={editAction('description')} />

<AccordionSection heading="Companies">
	<div class="company-section">
		{#if yearsActive}
			<div class="detail-block">
				<h3>Years Active</h3>
				<p>{yearsActive}</p>
			</div>
		{/if}

		{#if mfr.entities.length > 0}
			<div class="detail-block">
				<h3>Companies</h3>
				<ul class="stack-list">
					{#each mfr.entities as entity (entity.slug)}
						<li>
							<div class="entity">
								<a href={resolve(`/corporate-entities/${entity.slug}`)} class="entity-name"
									>{entity.name}</a
								>
								{#if formatYearRange(entity.year_start, entity.year_end)}
									<span class="muted">
										{formatYearRange(entity.year_start, entity.year_end)}
									</span>
								{/if}
								{#each entity.locations as loc, i (i)}
									<LocationLink {loc} />
								{/each}
							</div>
						</li>
					{/each}
				</ul>
			</div>
		{/if}

		{#if !hasEntityLocations && (mfr.headquarters || mfr.country)}
			<div class="detail-block">
				<h3>Location</h3>
				<p>{[mfr.headquarters, mfr.country].filter(Boolean).join(', ')}</p>
			</div>
		{/if}

		{#if mfr.website}
			<div class="detail-block">
				<h3>Website</h3>
				<p>
					<a href={mfr.website} target="_blank" rel="noopener">{websiteHostname(mfr.website)}</a>
				</p>
			</div>
		{/if}

		{#if !yearsActive && mfr.entities.length === 0 && !mfr.website && !mfr.headquarters && !mfr.country}
			<p class="empty">No company details yet.</p>
		{/if}
	</div>
</AccordionSection>

<AccordionSection heading={titlesHeading}>
	{#if mfr.titles.length === 0}
		<p class="empty">No titles listed for this manufacturer.</p>
	{:else}
		<SearchableGrid
			items={mfr.titles}
			filterFields={(item) => [item.name]}
			placeholder="Search titles..."
			entityName="title"
		>
			{#snippet children(title)}
				<TitleCard
					slug={title.slug}
					name={title.name}
					thumbnailUrl={title.thumbnail_url}
					year={title.year}
				/>
			{/snippet}
		</SearchableGrid>
	{/if}
</AccordionSection>

{#if mfr.systems.length > 0}
	<AccordionSection heading={systemsHeading}>
		<ul class="stack-list">
			{#each mfr.systems as system (system.slug)}
				<li>
					<a href={resolve(`/systems/${system.slug}`)}>{system.name}</a>
				</li>
			{/each}
		</ul>
	</AccordionSection>
{/if}

{#if mfr.persons.length > 0}
	<AccordionSection heading={peopleHeading}>
		<ul class="stack-list">
			{#each mfr.persons as person (person.slug)}
				<li>
					<div class="entity">
						<a href={resolve(`/people/${person.slug}`)}>{person.name}</a>
						{#if person.roles.length > 0}
							<span class="muted">{person.roles.join(', ')}</span>
						{/if}
					</div>
				</li>
			{/each}
		</ul>
	</AccordionSection>
{/if}

{#if mfr.uploaded_media.length > 0}
	<AccordionSection heading={mediaHeading}>
		<MediaGrid
			media={mfr.uploaded_media}
			categories={[...MEDIA_CATEGORIES.manufacturer]}
			canEdit={false}
		/>
	</AccordionSection>
{/if}

<style>
	.company-section {
		display: flex;
		flex-direction: column;
		gap: var(--size-4);
	}

	.detail-block h3 {
		font-size: var(--font-size-1);
		margin: 0 0 var(--size-2);
	}

	.detail-block p {
		margin: 0;
	}

	.stack-list {
		list-style: none;
		padding: 0;
		margin: 0;
		display: flex;
		flex-direction: column;
		gap: var(--size-3);
	}

	.entity {
		display: flex;
		flex-direction: column;
		gap: var(--size-00);
	}

	.entity-name {
		font-weight: 500;
		color: var(--color-text-primary);
		text-decoration: none;
	}

	.entity-name:hover {
		color: var(--color-accent);
	}

	.muted {
		color: var(--color-text-muted);
		font-size: var(--font-size-0);
	}

	.empty {
		color: var(--color-text-muted);
		font-size: var(--font-size-1);
		margin: 0;
	}
</style>
