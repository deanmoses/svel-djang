<script lang="ts">
	import { resolve } from '$app/paths';
	import MachineCard from '$lib/components/cards/MachineCard.svelte';
	import CreditsList from '$lib/components/CreditsList.svelte';

	let { data } = $props();
	let model = $derived(data.model);
</script>

<section class="specs">
	<h2>Specifications</h2>
	<dl>
		{#if model.technology_generation_slug}
			<dt>Generation</dt>
			<dd>
				<a href={resolve(`/technology-generations/${model.technology_generation_slug}`)}
					>{model.technology_generation_name}</a
				>
			</dd>
		{/if}
		{#if model.display_type_slug}
			<dt>Display Type</dt>
			<dd>
				<a href={resolve(`/display-types/${model.display_type_slug}`)}>{model.display_type_name}</a>
			</dd>
		{/if}
		{#if model.player_count}
			<dt>Players</dt>
			<dd>{model.player_count}</dd>
		{/if}
		{#if model.flipper_count}
			<dt>Flippers</dt>
			<dd>{model.flipper_count}</dd>
		{/if}
		{#if model.production_quantity}
			<dt>Production</dt>
			<dd>{model.production_quantity}</dd>
		{/if}
		{#if model.system_slug}
			<dt>System</dt>
			<dd><a href={resolve(`/systems/${model.system_slug}`)}>{model.system_name}</a></dd>
		{/if}
		{#if model.themes.length > 0}
			<dt>Themes</dt>
			<dd>
				{#each model.themes as theme, i (theme.slug)}
					{#if i > 0},
					{/if}
					<a href={resolve(`/themes/${theme.slug}`)}>{theme.name}</a>
				{/each}
			</dd>
		{/if}
		{#if model.cabinet_name}
			<dt>Cabinet</dt>
			<dd>{model.cabinet_name}</dd>
		{/if}
		{#if model.game_format_name}
			<dt>Format</dt>
			<dd>{model.game_format_name}</dd>
		{/if}
		{#if model.display_subtype_name}
			<dt>Display</dt>
			<dd>{model.display_subtype_name}</dd>
		{/if}
		{#if model.gameplay_features.length > 0}
			<dt>Features</dt>
			<dd>
				{#each model.gameplay_features as feature, i (feature.slug)}
					{#if i > 0},
					{/if}
					{feature.name}
				{/each}
			</dd>
		{/if}
		{#if model.series.length > 0}
			<dt>Series</dt>
			<dd>
				{#each model.series as s, i (s.slug)}
					{#if i > 0},
					{/if}
					<a href={resolve(`/series/${s.slug}`)}>{s.name}</a>
				{/each}
			</dd>
		{/if}
	</dl>
</section>

{#if model.aliases.length > 0}
	<section class="variants">
		<h2>Variants</h2>
		<ul>
			{#each model.aliases as alias (alias.slug)}
				<li>
					<a href={resolve(`/models/${alias.slug}`)}>{alias.name}</a>
					{#if alias.variant_features.length > 0}
						<span class="alias-features">{alias.variant_features.join(', ')}</span>
					{/if}
				</li>
			{/each}
		</ul>
	</section>
{/if}

{#if model.title_models && model.title_models.length > 0}
	<section class="title-models">
		<h2>Other Models in This Title</h2>
		<div class="title-models-grid">
			{#each model.title_models as sibling (sibling.slug)}
				<MachineCard
					slug={sibling.slug}
					name={sibling.name}
					year={sibling.year}
					manufacturerName={sibling.manufacturer_name}
					thumbnailUrl={sibling.thumbnail_url}
				/>
			{/each}
		</div>
	</section>
{/if}

{#if model.ipdb_rating || model.pinside_rating}
	<section class="ratings">
		<h2>Ratings</h2>
		<div class="rating-cards">
			{#if model.ipdb_rating}
				<div class="rating-card">
					<span class="rating-value">{model.ipdb_rating.toFixed(1)}</span>
					<span class="rating-label">IPDB</span>
				</div>
			{/if}
			{#if model.pinside_rating}
				<div class="rating-card">
					<span class="rating-value">{model.pinside_rating.toFixed(1)}</span>
					<span class="rating-label">Pinside</span>
				</div>
			{/if}
		</div>
	</section>
{/if}

{#if model.educational_text}
	<section class="description">
		<h2>About</h2>
		<p>{model.educational_text}</p>
	</section>
{/if}

{#if model.extra_data.notes}
	<section class="notes">
		<h2>Notes</h2>
		<p>{model.extra_data.notes}</p>
	</section>
{/if}

{#if model.extra_data.Notes}
	<section class="notes">
		<h2>Notes Capitalized</h2>
		<p>{model.extra_data.Notes}</p>
	</section>
{/if}

<CreditsList credits={model.credits} />

<style>
	h2 {
		font-size: var(--font-size-3);
		font-weight: 600;
		color: var(--color-text-primary);
		margin-bottom: var(--size-3);
	}

	section {
		margin-bottom: var(--size-6);
	}

	dl {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: var(--size-1) var(--size-4);
		align-items: baseline;
	}

	dt {
		font-size: var(--font-size-1);
		color: var(--color-text-muted);
		font-weight: 500;
	}

	dd {
		font-size: var(--font-size-1);
		color: var(--color-text-primary);
	}

	.variants ul {
		list-style: none;
		padding: 0;
	}

	.variants li {
		display: flex;
		justify-content: space-between;
		padding: var(--size-2) 0;
		border-bottom: 1px solid var(--color-border-soft);
		font-size: var(--font-size-1);
	}

	.alias-features {
		color: var(--color-text-muted);
		font-size: var(--font-size-0);
	}

	.rating-cards {
		display: flex;
		gap: var(--size-4);
	}

	.rating-card {
		display: flex;
		flex-direction: column;
		align-items: center;
		padding: var(--size-3) var(--size-5);
		background-color: var(--color-surface);
		border: 1px solid var(--color-border-soft);
		border-radius: var(--radius-2);
	}

	.rating-value {
		font-size: var(--font-size-5);
		font-weight: 700;
		color: var(--color-accent);
	}

	.rating-label {
		font-size: var(--font-size-0);
		color: var(--color-text-muted);
		text-transform: uppercase;
		letter-spacing: 0.05em;
	}

	.title-models-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(12rem, 1fr));
		gap: var(--size-4);
	}

	.notes p,
	.description p {
		font-size: var(--font-size-2);
		color: var(--color-text-primary);
		line-height: var(--font-lineheight-3);
	}
</style>
