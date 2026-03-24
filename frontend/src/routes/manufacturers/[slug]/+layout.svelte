<script lang="ts">
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import { pageTitle } from '$lib/constants';
	import { resolveHref } from '$lib/utils';
	import { auth } from '$lib/auth.svelte';
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';
	import ExpandableSidebarList from '$lib/components/ExpandableSidebarList.svelte';
	import LocationLink from '$lib/components/LocationLink.svelte';
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

	let yearsActive = $derived.by(() => {
		if (mfr.year_start && mfr.year_end) return `${mfr.year_start}–${mfr.year_end}`;
		if (mfr.year_start) return `${mfr.year_start}–present`;
		if (mfr.year_end) return `–${mfr.year_end}`;
		return null;
	});

	$effect(() => {
		auth.load();
	});

	let hasEntityAddresses = $derived(mfr.entities.some((e) => e.locations.length > 0));

	let isDetail = $derived(
		!page.url.pathname.endsWith('/edit') &&
			!page.url.pathname.endsWith('/activity') &&
			!page.url.pathname.endsWith('/systems')
	);
	let isEdit = $derived(page.url.pathname.endsWith('/edit'));
	let isActivity = $derived(page.url.pathname.endsWith('/activity'));

	function websiteHostname(url: string): string {
		try {
			return new URL(url).hostname;
		} catch {
			return url;
		}
	}
</script>

<svelte:head>
	<title>{pageTitle(mfr.name)}</title>
</svelte:head>

<article>
	<header>
		<Breadcrumb crumbs={[{ label: 'Manufacturers', href: '/manufacturers' }]} current={mfr.name} />
		<h1>{mfr.name}</h1>
	</header>

	<TwoColumnLayout>
		{#snippet main()}
			{#if mfr.description_html}
				<div class="description">
					<Markdown html={mfr.description_html} />
				</div>
			{/if}

			<TabNav>
				<Tab active={isDetail} href={resolve(`/manufacturers/${slug}`)}>Titles</Tab>
				{#if auth.isAuthenticated}
					<Tab active={isEdit} href={resolve(`/manufacturers/${slug}/edit`)}>Edit</Tab>
				{/if}
				<Tab active={isActivity} href={resolve(`/manufacturers/${slug}/activity`)}>Activity</Tab>
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
									<span class="entity-name">{entity.name}</span>
									{#if entity.year_start || entity.year_end}
										<span class="muted">
											{#if entity.year_start && entity.year_end}
												{entity.year_start}–{entity.year_end}
											{:else if entity.year_start}
												{entity.year_start}–present
											{:else if entity.year_end}
												–{entity.year_end}
											{/if}
										</span>
									{/if}
									{#each entity.locations as addr, i (i)}
										<LocationLink {addr} />
									{/each}
								</div>
							</SidebarListItem>
						{/each}
					</SidebarList>
				</SidebarSection>
			{/if}

			{#if !hasEntityAddresses && (mfr.headquarters || mfr.country)}
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
	header {
		margin-bottom: var(--size-5);
	}

	h1 {
		font-size: var(--font-size-7);
		font-weight: 700;
		color: var(--color-text-primary);
		margin-bottom: var(--size-2);
	}

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
