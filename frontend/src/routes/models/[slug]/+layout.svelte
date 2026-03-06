<script lang="ts">
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import { pageTitle } from '$lib/constants';
	import { auth } from '$lib/auth.svelte';
	import TwoColumnLayout from '$lib/components/TwoColumnLayout.svelte';

	let { data, children } = $props();
	let model = $derived(data.model);
	let slug = $derived(page.params.slug);

	$effect(() => {
		auth.load();
	});

	let isDetail = $derived(
		!page.url.pathname.endsWith('/edit') && !page.url.pathname.endsWith('/activity')
	);
	let isEdit = $derived(page.url.pathname.endsWith('/edit'));
	let isActivity = $derived(page.url.pathname.endsWith('/activity'));
</script>

<svelte:head>
	<title>{pageTitle(model.name)}</title>
</svelte:head>

<TwoColumnLayout heroImageUrl={model.hero_image_url} heroImageAlt="{model.name} backglass">
	{#snippet header()}
		{#if model.title_slug}
			<a class="kicker" href={resolve(`/titles/${model.title_slug}`)}>
				{model.title_name}
			</a>
		{/if}
		<h1>{model.name}</h1>
		<div class="meta">
			{#if model.manufacturer_name}
				<span>
					<a href={resolve(`/manufacturers/${model.manufacturer_slug}`)}>
						{model.manufacturer_name}
					</a>
				</span>
			{/if}
			{#if model.year}
				<span
					>{#if model.month}{new Date(model.year, model.month - 1).toLocaleString('en', {
							month: 'long'
						}) + ' '}{/if}{model.year}</span
				>
			{/if}
			{#if model.franchise}
				<span>{model.franchise.name}</span>
			{/if}
		</div>
		{#if model.variant_features.length > 0}
			<div class="features">
				{#each model.variant_features as feature (feature)}
					<span class="chip">{feature}</span>
				{/each}
			</div>
		{/if}
	{/snippet}

	{#snippet main()}
		{#if model.educational_text}
			<section class="prose">
				<h2>About</h2>
				<p>{model.educational_text}</p>
			</section>
		{/if}

		{#if model.extra_data.notes}
			<section class="prose">
				<h2>Notes</h2>
				<p>{model.extra_data.notes}</p>
			</section>
		{/if}

		{#if model.extra_data.Notes}
			<section class="prose">
				<h2>Notes</h2>
				<p>{model.extra_data.Notes}</p>
			</section>
		{/if}

		<nav class="tabs" aria-label="Page sections">
			<a class="tab" class:active={isDetail} href={resolve(`/models/${slug}`)}>People</a>
			{#if auth.isAuthenticated}
				<a class="tab" class:active={isEdit} href={resolve(`/models/${slug}/edit`)}>Edit</a>
			{/if}
			<a class="tab" class:active={isActivity} href={resolve(`/models/${slug}/activity`)}>
				Activity
			</a>
		</nav>

		{@render children()}
	{/snippet}

	{#snippet sidebar()}
		<section class="sidebar-section">
			<h3>Specifications</h3>
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
						<a href={resolve(`/display-types/${model.display_type_slug}`)}
							>{model.display_type_name}</a
						>
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
					<dt>Units Made</dt>
					<dd>{model.production_quantity}</dd>
				{/if}
				{#if model.system_slug}
					<dt>System</dt>
					<dd>
						<a href={resolve(`/systems/${model.system_slug}`)}>{model.system_name}</a>
					</dd>
				{/if}
				{#if model.themes.length > 0}
					<dt>Themes</dt>
					<dd>
						{#each model.themes as theme, i (theme.slug)}
							{#if i > 0},{/if}
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
							{#if i > 0},{/if}
							{feature.name}
						{/each}
					</dd>
				{/if}
				{#if model.series.length > 0}
					<dt>Series</dt>
					<dd>
						{#each model.series as s, i (s.slug)}
							{#if i > 0},{/if}
							<a href={resolve(`/series/${s.slug}`)}>{s.name}</a>
						{/each}
					</dd>
				{/if}
			</dl>
		</section>

		{#if model.ipdb_rating || model.pinside_rating}
			<section class="sidebar-section">
				<h3>Ratings</h3>
				<div class="rating-row">
					{#if model.ipdb_rating}
						<div class="rating-badge">
							<span class="rating-value">{model.ipdb_rating.toFixed(1)}</span>
							<span class="rating-label">IPDB</span>
						</div>
					{/if}
					{#if model.pinside_rating}
						<div class="rating-badge">
							<span class="rating-value">{model.pinside_rating.toFixed(1)}</span>
							<span class="rating-label">Pinside</span>
						</div>
					{/if}
				</div>
			</section>
		{/if}

		{#if model.aliases.length > 0}
			<section class="sidebar-section">
				<h3>Variants</h3>
				<ul class="sidebar-list">
					{#each model.aliases as alias (alias.slug)}
						<li>
							<a href={resolve(`/models/${alias.slug}`)}>{alias.name}</a>
							{#if alias.variant_features.length > 0}
								<span class="muted">{alias.variant_features.join(', ')}</span>
							{/if}
						</li>
					{/each}
				</ul>
			</section>
		{/if}

		{#if model.title_models && model.title_models.length > 0}
			<section class="sidebar-section">
				<h3>Other Models</h3>
				<ul class="sidebar-list">
					{#each model.title_models as sibling (sibling.slug)}
						<li>
							<a href={resolve(`/models/${sibling.slug}`)}>{sibling.name}</a>
							{#if sibling.year}
								<span class="muted">{sibling.year}</span>
							{/if}
						</li>
					{/each}
				</ul>
			</section>
		{/if}

		<div class="external-ids">
			{#if model.ipdb_id}
				<a
					href="https://www.ipdb.org/machine.cgi?id={model.ipdb_id}"
					target="_blank"
					rel="noopener"
				>
					IPDB #{model.ipdb_id}
				</a>
			{/if}
			{#if model.opdb_id}
				<a href="https://opdb.org/machines/{model.opdb_id}" target="_blank" rel="noopener">
					OPDB
				</a>
			{/if}
			{#if model.pinside_id}
				<a
					href="https://pinside.com/pinball/machine/{model.pinside_id}"
					target="_blank"
					rel="noopener"
				>
					Pinside
				</a>
			{/if}
		</div>
	{/snippet}
</TwoColumnLayout>

<style>
	.kicker {
		font-size: var(--font-size-1);
		font-weight: 500;
		color: var(--color-text-muted);
		text-decoration: none;
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}

	.kicker:hover {
		color: var(--color-accent);
	}

	h1 {
		font-size: var(--font-size-7);
		font-weight: 700;
		color: var(--color-text-primary);
		margin-bottom: var(--size-2);
	}

	.meta {
		display: flex;
		flex-wrap: wrap;
		gap: var(--size-2);
		font-size: var(--font-size-2);
		color: var(--color-text-muted);
	}

	.meta span:not(:last-child)::after {
		content: '·';
		margin-left: var(--size-2);
	}

	.features {
		display: flex;
		flex-wrap: wrap;
		gap: var(--size-2);
		margin-top: var(--size-3);
	}

	.chip {
		display: inline-block;
		padding: var(--size-1) var(--size-3);
		font-size: var(--font-size-0);
		background-color: var(--color-surface);
		border: 1px solid var(--color-border-soft);
		border-radius: var(--radius-round);
		color: var(--color-text-muted);
	}

	/* Main column */
	.prose {
		margin-bottom: var(--size-5);
	}

	.prose h2 {
		font-size: var(--font-size-3);
		font-weight: 600;
		color: var(--color-text-primary);
		margin-bottom: var(--size-3);
	}

	.prose p {
		font-size: var(--font-size-2);
		color: var(--color-text-primary);
		line-height: var(--font-lineheight-3);
	}

	.tabs {
		display: flex;
		gap: 0;
		border-bottom: 2px solid var(--color-border-soft);
		margin-bottom: var(--size-6);
	}

	.tab {
		padding: var(--size-2) var(--size-4);
		font-size: var(--font-size-1);
		font-weight: 500;
		color: var(--color-text-muted);
		text-decoration: none;
		border-bottom: 2px solid transparent;
		margin-bottom: -2px;
		transition:
			color 0.15s,
			border-color 0.15s;
	}

	.tab:hover {
		color: var(--color-text-primary);
	}

	.tab.active {
		color: var(--color-accent);
		border-bottom-color: var(--color-accent);
	}

	/* Sidebar */
	.sidebar-section {
		padding-bottom: var(--size-3);
		border-bottom: 1px solid var(--color-border-soft);
	}

	.sidebar-section h3 {
		font-size: var(--font-size-1);
		font-weight: 600;
		color: var(--color-text-primary);
		margin-bottom: var(--size-1);
		text-transform: uppercase;
		letter-spacing: 0.04em;
	}

	.sidebar-section dl {
		display: grid;
		grid-template-columns: auto 1fr;
		gap: 0 var(--size-3);
		align-items: baseline;
	}

	.sidebar-section dt,
	.sidebar-section dd {
		font-size: var(--font-size-0);
		margin: 0;
		padding: 2px 0;
	}

	.sidebar-section dt {
		color: var(--color-text-muted);
		font-weight: 500;
	}

	.sidebar-section dd {
		color: var(--color-text-primary);
	}

	.rating-row {
		display: flex;
		gap: var(--size-3);
	}

	.rating-badge {
		display: flex;
		align-items: baseline;
		gap: var(--size-1);
	}

	.rating-value {
		font-size: var(--font-size-3);
		font-weight: 700;
		color: var(--color-accent);
	}

	.rating-label {
		font-size: var(--font-size-0);
		color: var(--color-text-muted);
	}

	.sidebar-list {
		list-style: none;
		padding: 0;
		margin: 0;
	}

	.sidebar-list li {
		display: flex;
		justify-content: space-between;
		align-items: baseline;
		padding: var(--size-1) 0;
		font-size: var(--font-size-0);
	}

	.sidebar-list li:not(:last-child) {
		border-bottom: 1px solid var(--color-border-soft);
	}

	.muted {
		color: var(--color-text-muted);
		font-size: var(--font-size-0);
	}

	.external-ids {
		display: flex;
		flex-wrap: wrap;
		gap: var(--size-3);
		font-size: var(--font-size-0);
	}
</style>
