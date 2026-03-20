<script lang="ts">
	import SearchableGrid from '$lib/components/grid/SearchableGrid.svelte';
	import TitleCard from '$lib/components/cards/TitleCard.svelte';

	let { data } = $props();
	let mfr = $derived(data.manufacturer);

	let yearsActive = $derived(() => {
		if (mfr.year_start && mfr.year_end) return `${mfr.year_start}–${mfr.year_end}`;
		if (mfr.year_start) return `${mfr.year_start}–present`;
		if (mfr.year_end) return `dissolved ${mfr.year_end}`;
		return null;
	});

	let hasInfo = $derived(
		mfr.country || mfr.headquarters || mfr.year_start || mfr.year_end || mfr.website
	);
</script>

{#if mfr.logo_url}
	<div class="logo">
		<img src={mfr.logo_url} alt="{mfr.name} logo" />
	</div>
{/if}

{#if hasInfo}
	<dl class="bio-meta">
		{#if mfr.country}
			<div class="bio-meta-row">
				<dt>Country</dt>
				<dd>{mfr.country}</dd>
			</div>
		{/if}
		{#if mfr.headquarters}
			<div class="bio-meta-row">
				<dt>Headquarters</dt>
				<dd>{mfr.headquarters}</dd>
			</div>
		{/if}
		{#if yearsActive()}
			<div class="bio-meta-row">
				<dt>Years active</dt>
				<dd>{yearsActive()}</dd>
			</div>
		{/if}
		{#if mfr.website}
			<div class="bio-meta-row">
				<dt>Website</dt>
				<dd>
					<a href={mfr.website}>{mfr.website}</a>
				</dd>
			</div>
		{/if}
	</dl>
{/if}

{#if mfr.titles.length === 0}
	<p class="empty">No titles listed for this manufacturer.</p>
{:else}
	<section>
		<h2>Titles ({mfr.titles.length})</h2>
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
	</section>
{/if}

<style>
	.logo {
		margin-bottom: var(--size-5);
	}

	.logo img {
		max-width: 200px;
		max-height: 120px;
		object-fit: contain;
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

	.bio-meta dd a {
		color: var(--color-accent);
		text-decoration: none;
	}

	.bio-meta dd a:hover {
		text-decoration: underline;
	}

	h2 {
		font-size: var(--font-size-3);
		font-weight: 600;
		color: var(--color-text-primary);
		margin-bottom: var(--size-3);
	}

	section {
		margin-bottom: var(--size-6);
	}

	.empty {
		color: var(--color-text-muted);
		font-size: var(--font-size-2);
		padding: var(--size-8) 0;
		text-align: center;
	}
</style>
