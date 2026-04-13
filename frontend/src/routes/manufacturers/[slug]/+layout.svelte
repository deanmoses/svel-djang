<script lang="ts">
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import { formatYearRange, resolveHref } from '$lib/utils';
	import MetaTags from '$lib/components/MetaTags.svelte';
	import { auth } from '$lib/auth.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import ExpandableSidebarList from '$lib/components/ExpandableSidebarList.svelte';
	import LocationLink from '$lib/components/LocationLink.svelte';
	import AttributionLine from '$lib/components/AttributionLine.svelte';
	import Markdown from '$lib/components/Markdown.svelte';
	import SidebarList from '$lib/components/SidebarList.svelte';
	import SidebarListItem from '$lib/components/SidebarListItem.svelte';
	import SidebarSection from '$lib/components/SidebarSection.svelte';
	import TabNav from '$lib/components/TabNav.svelte';
	import Tab from '$lib/components/Tab.svelte';
	import TwoColumnLayout from '$lib/components/TwoColumnLayout.svelte';

	let { data, children } = $props();
	let mfr = $derived(data.manufacturer);
	let slug = $derived(page.params.slug);

	let yearsActive = $derived(formatYearRange(mfr.year_start, mfr.year_end));
	let metaDescription = $derived(mfr.description?.text || `${mfr.name} — pinball manufacturer`);

	$effect(() => {
		auth.load();
	});

	let hasEntityLocations = $derived(mfr.entities.some((e) => e.locations.length > 0));

	let isMedia = $derived(
		page.url.pathname.endsWith('/media') || page.url.pathname.includes('/media/')
	);
	let isDetail = $derived(
		!page.url.pathname.endsWith('/edit') &&
			!page.url.pathname.endsWith('/sources') &&
			!page.url.pathname.endsWith('/systems') &&
			!page.url.pathname.endsWith('/edit-history') &&
			!isMedia
	);
	let isEdit = $derived(page.url.pathname.endsWith('/edit'));
	let isSources = $derived(page.url.pathname.endsWith('/sources'));
	let isEditHistory = $derived(page.url.pathname.endsWith('/edit-history'));

	function websiteHostname(url: string): string {
		try {
			return new URL(url).hostname;
		} catch {
			return url;
		}
	}
</script>

<MetaTags
	title={mfr.name}
	description={metaDescription}
	url={page.url.href}
	image={mfr.logo_url}
	imageAlt={mfr.logo_url ? `${mfr.name} logo` : undefined}
/>

<article>
	<PageHeader
		title={mfr.name}
		breadcrumbs={[{ label: 'Manufacturers', href: '/manufacturers' }]}
		--page-header-mb="var(--size-5)"
		--page-header-title-mb="var(--size-2)"
	/>

	<TwoColumnLayout>
		{#snippet main()}
			{#if mfr.description?.html}
				<div class="description">
					<Markdown html={mfr.description.html} citations={mfr.description.citations} />
					<AttributionLine attribution={mfr.description.attribution} />
				</div>
			{/if}

			<TabNav>
				<Tab active={isDetail} href={resolve(`/manufacturers/${slug}`)}>Titles</Tab>
				<Tab active={isMedia} href={resolve(`/manufacturers/${slug}/media`)}>Media</Tab>
				{#if auth.isAuthenticated}
					<Tab active={isEdit} href={resolve(`/manufacturers/${slug}/edit`)}>Edit</Tab>
				{/if}
				<Tab active={isSources} href={resolve(`/manufacturers/${slug}/sources`)}>Sources</Tab>
				<Tab active={isEditHistory} href={resolve(`/manufacturers/${slug}/edit-history`)}
					>Edit History</Tab
				>
			</TabNav>

			{@render children()}
		{/snippet}

		{#snippet sidebar()}
			{#if mfr.logo_url}
				<div class="logo">
					<img src={mfr.logo_url} alt="{mfr.name} logo" />
				</div>
			{/if}

			{#if yearsActive}
				<SidebarSection heading="Years Active">
					<p class="sidebar-value">{yearsActive}</p>
				</SidebarSection>
			{/if}

			{#if mfr.entities.length > 0}
				<SidebarSection heading="Companies">
					<SidebarList>
						{#each mfr.entities as entity (entity.slug)}
							<SidebarListItem>
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
							</SidebarListItem>
						{/each}
					</SidebarList>
				</SidebarSection>
			{/if}

			{#if !hasEntityLocations && (mfr.headquarters || mfr.country)}
				<SidebarSection heading="Location">
					<p class="sidebar-value">
						{[mfr.headquarters, mfr.country].filter(Boolean).join(', ')}
					</p>
				</SidebarSection>
			{/if}

			{#if mfr.systems.length > 0}
				<SidebarSection heading="Systems">
					<SidebarList>
						{#each mfr.systems as system (system.slug)}
							<SidebarListItem>
								<a href={resolve(`/systems/${system.slug}`)}>{system.name}</a>
							</SidebarListItem>
						{/each}
					</SidebarList>
				</SidebarSection>
			{/if}

			{#if mfr.persons.length > 0}
				<SidebarSection heading="Notable People">
					<ExpandableSidebarList items={mfr.persons} limit={10} key={(p) => p.slug}>
						{#snippet children(person)}
							<SidebarListItem>
								<a href={resolveHref(`/people/${person.slug}`)}>{person.name}</a>
								{#if person.roles.length > 0}
									<span class="muted">{person.roles.join(', ')}</span>
								{/if}
							</SidebarListItem>
						{/snippet}
					</ExpandableSidebarList>
				</SidebarSection>
			{/if}

			{#if mfr.website}
				<SidebarSection heading="Links">
					<SidebarList>
						<SidebarListItem>
							<a href={mfr.website} target="_blank" rel="noopener">{websiteHostname(mfr.website)}</a
							>
						</SidebarListItem>
					</SidebarList>
				</SidebarSection>
			{/if}
		{/snippet}
	</TwoColumnLayout>
</article>

<style>
	.description {
		margin-bottom: var(--size-5);
	}

	.logo {
		padding-bottom: var(--size-3);
		border-bottom: 1px solid var(--color-border-soft);
	}

	.logo img {
		max-width: 100%;
		max-height: 120px;
		object-fit: contain;
		display: block;
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

	.sidebar-value {
		font-size: var(--font-size-1);
		color: var(--color-text-primary);
		margin: 0;
	}
</style>
