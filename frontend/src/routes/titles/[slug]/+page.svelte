<script lang="ts">
	import { resolve } from '$app/paths';
	import CardGrid from '$lib/components/grid/CardGrid.svelte';
	import MachineCard from '$lib/components/cards/MachineCard.svelte';
	import ModelDetailBody from '$lib/components/ModelDetailBody.svelte';
	import CreditsList from '$lib/components/CreditsList.svelte';
	import TwoColumnLayout from '$lib/components/TwoColumnLayout.svelte';
	import { pageTitle } from '$lib/constants';
	import { resolveHref } from '$lib/utils';
	import { auth } from '$lib/auth.svelte';

	let { data } = $props();
	let title = $derived(data.title);
	let md = $derived(title.model_detail);
	let specs = $derived(title.agreed_specs);

	let activeTab = $state<'people' | 'machines'>('people');

	$effect(() => {
		if (md) auth.load();
	});
</script>

<svelte:head>
	<title>{pageTitle(title.name)}</title>
</svelte:head>

{#if title.needs_review}
	<aside class="review-banner">
		<strong>Needs review</strong>
		<p>{title.needs_review_notes}</p>
		{#if title.review_links.length > 0}
			<p class="review-links">
				{#each title.review_links as link, i (link.url)}
					{#if i > 0}
						·
					{/if}
					{#if link.url.startsWith('/')}
						<a href={resolveHref(link.url)}>{link.label}</a>
					{:else}
						<a href={link.url} target="_blank" rel="noopener">{link.label}</a>
					{/if}
				{/each}
			</p>
		{/if}
	</aside>
{/if}

<TwoColumnLayout
	heroImageUrl={md ? md.hero_image_url : title.hero_image_url}
	heroImageAlt="{title.name} backglass"
>
	{#snippet header()}
		<h1>{title.name}</h1>
		{#if md}
			<div class="meta">
				{#if md.manufacturer_name}
					<span>
						<a href={resolve(`/manufacturers/${md.manufacturer_slug}`)}>
							{md.manufacturer_name}
						</a>
					</span>
				{/if}
				{#if md.year}
					<span
						>{#if md.month}{new Date(md.year, md.month - 1).toLocaleString('en', {
								month: 'long'
							}) + ' '}{/if}{md.year}</span
					>
				{/if}
				{#if md.franchise}
					<span>{md.franchise.name}</span>
				{/if}
			</div>
			{#if md.variant_features.length > 0}
				<div class="features">
					{#each md.variant_features as feature (feature)}
						<span class="chip">{feature}</span>
					{/each}
				</div>
			{/if}
		{/if}
		{#if title.series.length > 0}
			<p class="series-list">
				Series:
				{#each title.series as s, i (s.slug)}
					{#if i > 0},{/if}
					<a href={resolve(`/series/${s.slug}`)}>{s.name}</a>
				{/each}
			</p>
		{/if}
	{/snippet}

	{#snippet main()}
		{#if md}
			{#if md.educational_text}
				<section class="prose">
					<h2>About</h2>
					<p>{md.educational_text}</p>
				</section>
			{/if}

			{#if md.extra_data.notes}
				<section class="prose">
					<h2>Notes</h2>
					<p>{md.extra_data.notes}</p>
				</section>
			{/if}

			{#if md.extra_data.Notes}
				<section class="prose">
					<h2>Notes</h2>
					<p>{md.extra_data.Notes}</p>
				</section>
			{/if}

			<nav class="tabs" aria-label="Page sections">
				<span class="tab active">People</span>
				{#if auth.isAuthenticated}
					<a class="tab" href={resolve(`/models/${md.slug}/edit`)}>Edit</a>
				{/if}
				<a class="tab" href={resolve(`/models/${md.slug}/activity`)}>Activity</a>
			</nav>

			<ModelDetailBody model={md} />
		{:else}
			<nav class="tabs" aria-label="Page sections">
				<button
					class="tab"
					class:active={activeTab === 'machines'}
					onclick={() => (activeTab = 'machines')}
				>
					Machines ({title.machines.length})
				</button>
				<button
					class="tab"
					class:active={activeTab === 'people'}
					onclick={() => (activeTab = 'people')}
				>
					People
				</button>
			</nav>

			{#if activeTab === 'machines'}
				{#if title.machines.length === 0}
					<p class="empty">No machines in this title.</p>
				{:else}
					<CardGrid>
						{#each title.machines as machine (machine.slug)}
							<MachineCard
								slug={machine.slug}
								name={machine.name}
								thumbnailUrl={machine.thumbnail_url}
								manufacturerName={machine.manufacturer_name}
								year={machine.year}
							/>
						{/each}
					</CardGrid>
				{/if}
			{:else if activeTab === 'people'}
				<CreditsList credits={title.credits} />
			{/if}
		{/if}
	{/snippet}

	{#snippet sidebar()}
		{#if md}
			<!-- Single-model: full specs from model detail -->
			<section class="sidebar-section">
				<h3>Specifications</h3>
				<dl>
					{#if md.technology_generation_slug}
						<dt>Generation</dt>
						<dd>
							<a href={resolve(`/technology-generations/${md.technology_generation_slug}`)}
								>{md.technology_generation_name}</a
							>
						</dd>
					{/if}
					{#if md.display_type_slug}
						<dt>Display Type</dt>
						<dd>
							<a href={resolve(`/display-types/${md.display_type_slug}`)}>{md.display_type_name}</a>
						</dd>
					{/if}
					{#if md.player_count}
						<dt>Players</dt>
						<dd>{md.player_count}</dd>
					{/if}
					{#if md.flipper_count}
						<dt>Flippers</dt>
						<dd>{md.flipper_count}</dd>
					{/if}
					{#if md.production_quantity}
						<dt>Units Made</dt>
						<dd>{md.production_quantity}</dd>
					{/if}
					{#if md.system_slug}
						<dt>System</dt>
						<dd>
							<a href={resolve(`/systems/${md.system_slug}`)}>{md.system_name}</a>
						</dd>
					{/if}
					{#if md.themes.length > 0}
						<dt>Themes</dt>
						<dd>
							{#each md.themes as theme, i (theme.slug)}
								{#if i > 0},{/if}
								<a href={resolve(`/themes/${theme.slug}`)}>{theme.name}</a>
							{/each}
						</dd>
					{/if}
					{#if md.cabinet_name}
						<dt>Cabinet</dt>
						<dd>{md.cabinet_name}</dd>
					{/if}
					{#if md.game_format_name}
						<dt>Format</dt>
						<dd>{md.game_format_name}</dd>
					{/if}
					{#if md.display_subtype_name}
						<dt>Display</dt>
						<dd>{md.display_subtype_name}</dd>
					{/if}
					{#if md.gameplay_features.length > 0}
						<dt>Features</dt>
						<dd>
							{#each md.gameplay_features as feature, i (feature.slug)}
								{#if i > 0},{/if}
								{feature.name}
							{/each}
						</dd>
					{/if}
				</dl>
			</section>

			{#if md.ipdb_rating || md.pinside_rating}
				<section class="sidebar-section">
					<h3>Ratings</h3>
					<div class="rating-row">
						{#if md.ipdb_rating}
							<div class="rating-badge">
								<span class="rating-value">{md.ipdb_rating.toFixed(1)}</span>
								<span class="rating-label">IPDB</span>
							</div>
						{/if}
						{#if md.pinside_rating}
							<div class="rating-badge">
								<span class="rating-value">{md.pinside_rating.toFixed(1)}</span>
								<span class="rating-label">Pinside</span>
							</div>
						{/if}
					</div>
				</section>
			{/if}

			{#if md.aliases.length > 0}
				<section class="sidebar-section">
					<h3>Variants</h3>
					<ul class="sidebar-list">
						{#each md.aliases as alias (alias.slug)}
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

			<div class="external-ids">
				{#if md.ipdb_id}
					<a href="https://www.ipdb.org/machine.cgi?id={md.ipdb_id}" target="_blank" rel="noopener">
						IPDB #{md.ipdb_id}
					</a>
				{/if}
				{#if md.opdb_id}
					<a href="https://opdb.org/machines/{md.opdb_id}" target="_blank" rel="noopener"> OPDB </a>
				{/if}
				{#if md.pinside_id}
					<a
						href="https://pinside.com/pinball/machine/{md.pinside_id}"
						target="_blank"
						rel="noopener"
					>
						Pinside
					</a>
				{/if}
			</div>
		{:else}
			<!-- Multi-model: agreed specs across all models -->
			{#if specs.technology_generation_slug || specs.display_type_slug || specs.player_count || specs.system_slug || specs.cabinet_name || specs.game_format_name || specs.display_subtype_name || specs.production_quantity || (specs.themes && specs.themes.length > 0)}
				<section class="sidebar-section">
					<h3>Specifications</h3>
					<dl>
						{#if specs.technology_generation_slug}
							<dt>Generation</dt>
							<dd>
								<a href={resolve(`/technology-generations/${specs.technology_generation_slug}`)}
									>{specs.technology_generation_name}</a
								>
							</dd>
						{/if}
						{#if specs.display_type_slug}
							<dt>Display Type</dt>
							<dd>
								<a href={resolve(`/display-types/${specs.display_type_slug}`)}
									>{specs.display_type_name}</a
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
						{#if specs.system_slug}
							<dt>System</dt>
							<dd>
								<a href={resolve(`/systems/${specs.system_slug}`)}>{specs.system_name}</a>
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
						{#if specs.cabinet_name}
							<dt>Cabinet</dt>
							<dd>{specs.cabinet_name}</dd>
						{/if}
						{#if specs.game_format_name}
							<dt>Format</dt>
							<dd>{specs.game_format_name}</dd>
						{/if}
						{#if specs.display_subtype_name}
							<dt>Display</dt>
							<dd>{specs.display_subtype_name}</dd>
						{/if}
					</dl>
				</section>
			{/if}

			{#if title.series.length > 0}
				<section class="sidebar-section">
					<h3>Series</h3>
					<ul class="sidebar-list">
						{#each title.series as s (s.slug)}
							<li>
								<a href={resolve(`/series/${s.slug}`)}>{s.name}</a>
							</li>
						{/each}
					</ul>
				</section>
			{/if}

			{#if title.machines.length > 1}
				<section class="sidebar-section">
					<h3>Models</h3>
					<ul class="sidebar-list">
						{#each title.machines as machine (machine.slug)}
							<li>
								<a href={resolve(`/models/${machine.slug}`)}>{machine.name}</a>
								{#if machine.year}
									<span class="muted">{machine.year}</span>
								{/if}
							</li>
						{/each}
					</ul>
				</section>
			{/if}
		{/if}
	{/snippet}
</TwoColumnLayout>

<style>
	.review-banner {
		background-color: color-mix(in srgb, var(--color-warning) 12%, transparent);
		border: 1px solid var(--color-warning);
		border-radius: var(--radius-2);
		padding: var(--size-3) var(--size-4);
		margin-bottom: var(--size-5);
		font-size: var(--font-size-1);
		color: var(--color-text-primary);
	}

	.review-banner strong {
		color: var(--color-warning);
	}

	.review-banner p {
		margin-top: var(--size-1);
	}

	.review-links a {
		color: var(--color-warning);
		text-decoration: underline;
	}

	h1 {
		font-size: var(--font-size-7);
		font-weight: 700;
		color: var(--color-text-primary);
		margin-bottom: var(--size-2);
	}

	.series-list {
		font-size: var(--font-size-1);
		color: var(--color-text-muted);
		margin-top: var(--size-1);
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
		border: none;
		background: none;
		cursor: pointer;
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

	.empty {
		color: var(--color-text-muted);
		font-size: var(--font-size-2);
		padding: var(--size-8) 0;
		text-align: center;
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
