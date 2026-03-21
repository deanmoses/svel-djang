<script lang="ts">
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import { pageTitle } from '$lib/constants';
	import { auth } from '$lib/auth.svelte';
	import ExternalLinksSidebarSection from '$lib/components/ExternalLinksSidebarSection.svelte';
	import HeroHeader from '$lib/components/HeroHeader.svelte';
	import ModelHierarchy from '$lib/components/ModelHierarchy.svelte';
	import ModelSpecsSidebar from '$lib/components/ModelSpecsSidebar.svelte';
	import RatingsSidebarSection from '$lib/components/RatingsSidebarSection.svelte';
	import SidebarList from '$lib/components/SidebarList.svelte';
	import SidebarListItem from '$lib/components/SidebarListItem.svelte';
	import SidebarSection from '$lib/components/SidebarSection.svelte';
	import TabNav from '$lib/components/TabNav.svelte';
	import Tab from '$lib/components/Tab.svelte';
	import TwoColumnLayout from '$lib/components/TwoColumnLayout.svelte';

	let { data, children } = $props();
	let model = $derived(data.model);
	let slug = $derived(page.params.slug);

	$effect(() => {
		auth.load();
	});

	let isOnlyModelInTitle = $derived(model.title_models.length <= 1);
	let isDetail = $derived(
		!page.url.pathname.endsWith('/edit') && !page.url.pathname.endsWith('/activity')
	);
	let isEdit = $derived(page.url.pathname.endsWith('/edit'));
	let isActivity = $derived(page.url.pathname.endsWith('/activity'));

	let parentLink = $derived(
		model.title_slug && model.title_name
			? { text: model.title_name, href: resolve(`/titles/${model.title_slug}`) }
			: null
	);

	let metaItems = $derived.by(() => {
		const items: Array<{ text: string; href?: string }> = [];
		if (model.manufacturer_name) {
			items.push({
				text: model.manufacturer_name,
				href: resolve(`/manufacturers/${model.manufacturer_slug}`)
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
</script>

<svelte:head>
	<title>{pageTitle(model.name)}</title>
</svelte:head>

<article>
	<HeroHeader
		name={model.name}
		heroImageUrl={model.hero_image_url}
		heroImageAlt="{model.name} backglass"
		{parentLink}
		{metaItems}
	/>

	<TwoColumnLayout>
		{#snippet main()}
			{#if model.title_description && isOnlyModelInTitle}
				<section class="prose">
					<h2>About</h2>
					<p>{model.title_description}</p>
				</section>
			{/if}

			<TabNav>
				<Tab active={isDetail} href={resolve(`/models/${slug}`)}>People</Tab>
				{#if auth.isAuthenticated}
					<Tab active={isEdit} href={resolve(`/models/${slug}/edit`)}>Edit</Tab>
				{/if}
				<Tab active={isActivity} href={resolve(`/models/${slug}/activity`)}>Activity</Tab>
			</TabNav>

			{@render children()}
		{/snippet}

		{#snippet sidebar()}
			<SidebarSection heading="Specifications">
				<ModelSpecsSidebar {model} />
			</SidebarSection>

			<RatingsSidebarSection ipdbRating={model.ipdb_rating} pinsideRating={model.pinside_rating} />

			{#if model.title_slug}
				<SidebarSection heading="Parent Title">
					<SidebarList>
						<SidebarListItem>
							<a href={resolve(`/titles/${model.title_slug}`)}>{model.title_name}</a>
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

			{#if model.variant_of_slug}
				<SidebarSection heading="Parent Model">
					<SidebarList>
						<SidebarListItem>
							<a href={resolve(`/models/${model.variant_of_slug}`)}>{model.variant_of_name}</a>
							{#if model.variant_of_year}
								<span class="muted">{model.variant_of_year}</span>
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

			{#if model.converted_from_slug}
				<SidebarSection heading="Converted From" note="This game was rebuilt from the hardware of:">
					<SidebarList>
						<SidebarListItem>
							<a href={resolve(`/models/${model.converted_from_slug}`)}
								>{model.converted_from_name}</a
							>
							{#if model.converted_from_year}
								<span class="muted">{model.converted_from_year}</span>
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

			{#if model.remake_of_slug}
				<SidebarSection heading="Remake Of" note="This game is a remake of:">
					<SidebarList>
						<SidebarListItem>
							<a href={resolve(`/models/${model.remake_of_slug}`)}>{model.remake_of_name}</a>
							{#if model.remake_of_year}
								<span class="muted">{model.remake_of_year}</span>
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
				excludeSlug={model.variant_of_slug ?? model.slug}
			/>

			<ExternalLinksSidebarSection
				ipdbId={model.ipdb_id}
				opdbId={model.opdb_id}
				pinsideId={model.pinside_id}
				note="See this model on other sites:"
			/>
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

	.muted {
		color: var(--color-text-muted);
		font-size: var(--font-size-0);
	}
</style>
