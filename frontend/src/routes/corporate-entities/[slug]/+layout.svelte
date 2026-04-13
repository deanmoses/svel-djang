<script lang="ts">
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import { SITE_NAME } from '$lib/constants';
	import { formatYearRange } from '$lib/utils';
	import MetaTags from '$lib/components/MetaTags.svelte';
	import { auth } from '$lib/auth.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import AttributionLine from '$lib/components/AttributionLine.svelte';
	import LocationLink from '$lib/components/LocationLink.svelte';
	import Markdown from '$lib/components/Markdown.svelte';
	import SidebarSection from '$lib/components/SidebarSection.svelte';
	import TabNav from '$lib/components/TabNav.svelte';
	import Tab from '$lib/components/Tab.svelte';
	import TwoColumnLayout from '$lib/components/TwoColumnLayout.svelte';

	let { data, children } = $props();
	let ce = $derived(data.corporateEntity);
	let slug = $derived(page.params.slug);

	$effect(() => {
		auth.load();
	});

	let yearsActive = $derived(formatYearRange(ce.year_start, ce.year_end));

	let isDetail = $derived(
		!page.url.pathname.endsWith('/edit') &&
			!page.url.pathname.endsWith('/sources') &&
			!page.url.pathname.endsWith('/edit-history')
	);
	let isEdit = $derived(page.url.pathname.endsWith('/edit'));
	let isSources = $derived(page.url.pathname.endsWith('/sources'));
	let isEditHistory = $derived(page.url.pathname.endsWith('/edit-history'));
</script>

<MetaTags
	title={ce.name}
	description={ce.description?.text || `${ce.name} — ${SITE_NAME}`}
	url={page.url.href}
/>

<article>
	<PageHeader
		title={ce.name}
		breadcrumbs={[
			{ label: 'Manufacturers', href: '/manufacturers' },
			{ label: ce.manufacturer.name, href: `/manufacturers/${ce.manufacturer.slug}` }
		]}
		--page-header-mb="var(--size-5)"
		--page-header-title-mb="var(--size-2)"
	/>

	<TwoColumnLayout>
		{#snippet main()}
			{#if ce.description?.html}
				<div class="description">
					<Markdown html={ce.description.html} citations={ce.description.citations} />
					<AttributionLine attribution={ce.description.attribution} />
				</div>
			{/if}

			<TabNav>
				<Tab active={isDetail} href={resolve(`/corporate-entities/${slug}`)}>Titles</Tab>
				{#if auth.isAuthenticated}
					<Tab active={isEdit} href={resolve(`/corporate-entities/${slug}/edit`)}>Edit</Tab>
				{/if}
				<Tab active={isSources} href={resolve(`/corporate-entities/${slug}/sources`)}>Sources</Tab>
				<Tab active={isEditHistory} href={resolve(`/corporate-entities/${slug}/edit-history`)}
					>Edit History</Tab
				>
			</TabNav>

			{@render children()}
		{/snippet}

		{#snippet sidebar()}
			<SidebarSection heading="Manufacturer">
				<p class="sidebar-value">
					<a href={resolve(`/manufacturers/${ce.manufacturer.slug}`)}>{ce.manufacturer.name}</a>
				</p>
			</SidebarSection>

			{#if yearsActive}
				<SidebarSection heading="Years Active">
					<p class="sidebar-value">{yearsActive}</p>
				</SidebarSection>
			{/if}

			{#if ce.locations && ce.locations.length > 0}
				<SidebarSection heading="Locations">
					{#each ce.locations as loc, i (i)}
						<LocationLink {loc} />
					{/each}
				</SidebarSection>
			{/if}

			{#if ce.aliases && ce.aliases.length > 0}
				<SidebarSection heading="Also known as">
					<p class="aliases">{ce.aliases.join(', ')}</p>
				</SidebarSection>
			{/if}
		{/snippet}
	</TwoColumnLayout>
</article>

<style>
	.description {
		margin-bottom: var(--size-5);
	}

	.sidebar-value {
		font-size: var(--font-size-1);
		color: var(--color-text-primary);
		margin: 0;
	}

	.sidebar-value a {
		color: var(--color-accent);
		text-decoration: none;
	}

	.sidebar-value a:hover {
		text-decoration: underline;
	}

	.aliases {
		font-size: var(--font-size-0);
		color: var(--color-text-muted);
		margin: 0;
	}
</style>
