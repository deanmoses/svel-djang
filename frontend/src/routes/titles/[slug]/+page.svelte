<script lang="ts">
	import { resolve } from '$app/paths';
	import MachineCard from '$lib/components/cards/MachineCard.svelte';
	import ModelDetailBody from '$lib/components/ModelDetailBody.svelte';
	import ModelHierarchy from '$lib/components/ModelHierarchy.svelte';
	import CreditsList from '$lib/components/CreditsList.svelte';
	import ExternalLinksSidebarSection from '$lib/components/ExternalLinksSidebarSection.svelte';
	import Markdown from '$lib/components/Markdown.svelte';
	import HeroHeader from '$lib/components/HeroHeader.svelte';
	import RatingsSidebarSection from '$lib/components/RatingsSidebarSection.svelte';
	import SidebarList from '$lib/components/SidebarList.svelte';
	import SidebarListItem from '$lib/components/SidebarListItem.svelte';
	import SidebarSection from '$lib/components/SidebarSection.svelte';
	import TabNav from '$lib/components/TabNav.svelte';
	import Tab from '$lib/components/Tab.svelte';
	import TwoColumnLayout from '$lib/components/TwoColumnLayout.svelte';
	import { pageTitle } from '$lib/constants';
	import NeedsReviewBanner from '$lib/components/NeedsReviewBanner.svelte';
	import { auth } from '$lib/auth.svelte';

	let { data } = $props();
	let title = $derived(data.title);
	let md = $derived(title.model_detail);
	let specs = $derived(title.agreed_specs);

	let activeTab = $state<'people' | 'machines'>('people');

	$effect(() => {
		if (md) auth.load();
	});

	let metaItems = $derived.by(() => {
		if (!md) return [];
		const items: Array<{ text: string; href?: string }> = [];
		if (md.manufacturer_name) {
			items.push({
				text: md.manufacturer_name,
				href: resolve(`/manufacturers/${md.manufacturer_slug}`)
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
</script>

<svelte:head>
	<title>{pageTitle(title.name)}</title>
</svelte:head>

{#if title.needs_review}
	<NeedsReviewBanner notes={title.needs_review_notes} links={title.review_links} />
{/if}

<article>
	<HeroHeader
		name={title.name}
		heroImageUrl={md ? md.hero_image_url : title.hero_image_url}
		heroImageAlt="{title.name} backglass"
		{metaItems}
	/>

	<TwoColumnLayout>
		{#snippet main()}
			{#if title.description_html}
				<section class="prose">
					<h2>About</h2>
					<Markdown html={title.description_html} />
				</section>
			{/if}

			{#if md}
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

				<TabNav>
					<Tab active>People</Tab>
					{#if auth.isAuthenticated}
						<Tab href={resolve(`/models/${md.slug}/edit`)}>Edit</Tab>
					{/if}
					<Tab href={resolve(`/models/${md.slug}/activity`)}>Activity</Tab>
				</TabNav>

				<ModelDetailBody model={md} />
			{:else}
				<TabNav>
					<Tab active={activeTab === 'machines'} onclick={() => (activeTab = 'machines')}>
						Models ({title.machines.length +
							title.machines.reduce((n, m) => n + (m.variants?.length ?? 0), 0)})
					</Tab>
					<Tab active={activeTab === 'people'} onclick={() => (activeTab = 'people')}>People</Tab>
				</TabNav>

				{#if activeTab === 'machines'}
					{#if title.machines.length === 0}
						<p class="empty">No models in this title.</p>
					{:else}
						{#each title.machines as machine (machine.slug)}
							<div class="model-group">
								<MachineCard
									slug={machine.slug}
									name={machine.name}
									thumbnailUrl={machine.thumbnail_url}
									manufacturerName={machine.manufacturer_name}
									year={machine.year}
								/>
								{#if machine.variants.length > 0}
									<ul class="variant-list">
										{#each machine.variants as variant (variant.slug)}
											<li>
												<a href={resolve(`/models/${variant.slug}`)}>{variant.name}</a>
											</li>
										{/each}
									</ul>
								{/if}
							</div>
						{/each}
					{/if}
				{:else if activeTab === 'people'}
					<CreditsList credits={title.credits} />
				{/if}
			{/if}
		{/snippet}

		{#snippet sidebar()}
			{#if md}
				<!-- Single-model: full specs from model detail -->
				<SidebarSection heading="Specifications">
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
								<a href={resolve(`/display-types/${md.display_type_slug}`)}
									>{md.display_type_name}</a
								>
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
						{#if md.franchise}
							<dt>Franchise</dt>
							<dd>
								<a href={resolve(`/franchises/${md.franchise.slug}`)}>{md.franchise.name}</a>
							</dd>
						{/if}
						{#if md.abbreviations.length > 0}
							<dt>Abbrs</dt>
							<dd>{md.abbreviations.join(', ')}</dd>
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
						{#if md.variant_features.length > 0}
							<dt>Variant</dt>
							<dd>{md.variant_features.join(', ')}</dd>
						{/if}
						{#if md.series.length > 0}
							<dt>Series</dt>
							<dd>
								{#each md.series as s, i (s.slug)}
									{#if i > 0},{/if}
									<a href={resolve(`/series/${s.slug}`)}>{s.name}</a>
								{/each}
							</dd>
						{/if}
					</dl>
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
				<!-- Multi-model: agreed specs across all models -->
				{#if specs.technology_generation_slug || specs.display_type_slug || specs.player_count || specs.system_slug || specs.cabinet_name || specs.game_format_name || specs.display_subtype_name || specs.production_quantity || (specs.themes && specs.themes.length > 0) || title.abbreviations.length > 0}
					<SidebarSection heading="Specifications">
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
							{#if title.franchise}
								<dt>Franchise</dt>
								<dd>
									<a href={resolve(`/franchises/${title.franchise.slug}`)}>{title.franchise.name}</a
									>
								</dd>
							{/if}
							{#if title.abbreviations.length > 0}
								<dt>Abbrs</dt>
								<dd>{title.abbreviations.join(', ')}</dd>
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
					</SidebarSection>
				{/if}

				{#if title.series.length > 0}
					<SidebarSection heading="Series">
						<SidebarList>
							{#each title.series as s (s.slug)}
								<SidebarListItem>
									<a href={resolve(`/series/${s.slug}`)}>{s.name}</a>
								</SidebarListItem>
							{/each}
						</SidebarList>
					</SidebarSection>
				{/if}

				{#if title.machines.length > 0}
					<ModelHierarchy models={title.machines} />
				{/if}
			{/if}
		{/snippet}
	</TwoColumnLayout>
</article>

<style>
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

	.empty {
		color: var(--color-text-muted);
		font-size: var(--font-size-2);
		padding: var(--size-8) 0;
		text-align: center;
	}

	.model-group {
		margin-bottom: var(--size-4);
	}

	.variant-list {
		list-style: none;
		padding: 0 0 0 var(--size-6);
		margin: var(--size-2) 0 0 0;
	}

	.variant-list li {
		padding: var(--size-1) 0;
		font-size: var(--font-size-1);
		color: var(--color-text-muted);
	}

	.variant-list li::before {
		content: '└';
		margin-right: var(--size-2);
		color: var(--color-text-muted);
	}

	/* Sidebar */
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
</style>
