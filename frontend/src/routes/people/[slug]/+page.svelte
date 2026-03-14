<script lang="ts">
	import Markdown from '$lib/components/Markdown.svelte';
	import SearchableGrid from '$lib/components/grid/SearchableGrid.svelte';
	import TitleCard from '$lib/components/cards/TitleCard.svelte';

	let { data } = $props();
	let person = $derived(data.person);

	function formatDate(
		year: number | null | undefined,
		month: number | null | undefined,
		day: number | null | undefined
	): string | null {
		if (!year) return null;
		if (!month) return String(year);
		const monthName = new Date(year, month - 1).toLocaleString('en', { month: 'long' });
		if (!day) return `${monthName} ${year}`;
		return `${monthName} ${day}, ${year}`;
	}

	let birthDate = $derived(formatDate(person.birth_year, person.birth_month, person.birth_day));
	let deathDate = $derived(formatDate(person.death_year, person.death_month, person.death_day));
	let hasBiographicalInfo = $derived(
		birthDate || deathDate || person.birth_place || person.nationality
	);
</script>

{#if person.photo_url}
	<div class="photo">
		<img src={person.photo_url} alt={person.name} />
	</div>
{/if}

{#if hasBiographicalInfo}
	<dl class="bio-meta">
		{#if person.nationality}
			<div class="bio-meta-row">
				<dt>Nationality</dt>
				<dd>{person.nationality}</dd>
			</div>
		{/if}
		{#if birthDate}
			<div class="bio-meta-row">
				<dt>Born</dt>
				<dd>
					{birthDate}{#if person.birth_place}, {person.birth_place}{/if}
				</dd>
			</div>
		{:else if person.birth_place}
			<div class="bio-meta-row">
				<dt>Birth place</dt>
				<dd>{person.birth_place}</dd>
			</div>
		{/if}
		{#if deathDate}
			<div class="bio-meta-row">
				<dt>Died</dt>
				<dd>{deathDate}</dd>
			</div>
		{/if}
	</dl>
{/if}

{#if person.bio_html}
	<section class="bio">
		<Markdown html={person.bio_html} />
	</section>
{/if}

{#if person.titles.length > 0}
	<SearchableGrid
		items={person.titles}
		filterFields={(item) => [item.name]}
		placeholder="Search titles..."
		entityName="title"
	>
		{#snippet children(title)}
			<TitleCard
				slug={title.slug}
				name={title.name}
				year={title.year}
				thumbnailUrl={title.thumbnail_url}
				manufacturerName={title.manufacturer_name}
				roles={title.roles}
			/>
		{/snippet}
	</SearchableGrid>
{:else}
	<p class="empty">No credits listed.</p>
{/if}

<style>
	.photo {
		margin-bottom: var(--size-5);
	}

	.photo img {
		width: 160px;
		height: 160px;
		object-fit: cover;
		border-radius: var(--radius-3);
		display: block;
	}

	.bio-meta {
		display: flex;
		flex-direction: column;
		gap: var(--size-1);
		margin: 0 0 var(--size-5);
	}

	.bio-meta-row {
		display: flex;
		gap: var(--size-3);
		font-size: var(--font-size-1);
	}

	.bio-meta dt {
		color: var(--color-text-muted);
		min-width: 7rem;
		flex-shrink: 0;
	}

	.bio-meta dd {
		color: var(--color-text-primary);
		margin: 0;
	}

	.bio {
		margin-bottom: var(--size-6);
	}

	.empty {
		color: var(--color-text-muted);
		font-size: var(--font-size-2);
		padding: var(--size-8) 0;
		text-align: center;
	}
</style>
