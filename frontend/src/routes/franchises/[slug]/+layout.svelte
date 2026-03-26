<script lang="ts">
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import { pageTitle } from '$lib/constants';
	import { auth } from '$lib/auth.svelte';
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';
	import AttributionLine from '$lib/components/AttributionLine.svelte';
	import Markdown from '$lib/components/Markdown.svelte';
	import TabNav from '$lib/components/TabNav.svelte';
	import Tab from '$lib/components/Tab.svelte';

	let { data, children } = $props();
	let franchise = $derived(data.franchise);
	let slug = $derived(page.params.slug);

	$effect(() => {
		auth.load();
	});

	let isDetail = $derived(
		!page.url.pathname.endsWith('/edit') &&
			!page.url.pathname.endsWith('/activity') &&
			!page.url.pathname.endsWith('/edit-history')
	);
	let isEdit = $derived(page.url.pathname.endsWith('/edit'));
	let isActivity = $derived(page.url.pathname.endsWith('/activity'));
	let isEditHistory = $derived(page.url.pathname.endsWith('/edit-history'));
</script>

<svelte:head>
	<title>{pageTitle(franchise.name)}</title>
</svelte:head>

<article>
	<header>
		<Breadcrumb crumbs={[{ label: 'Franchises', href: '/franchises' }]} current={franchise.name} />
		<h1>{franchise.name}</h1>
	</header>

	{#if franchise.description?.html}
		<div class="description">
			<Markdown html={franchise.description.html} />
			<AttributionLine attribution={franchise.description.attribution} />
		</div>
	{/if}

	<TabNav>
		<Tab active={isDetail} href={resolve(`/franchises/${slug}`)}>Titles</Tab>
		{#if auth.isAuthenticated}
			<Tab active={isEdit} href={resolve(`/franchises/${slug}/edit`)}>Edit</Tab>
		{/if}
		<Tab active={isActivity} href={resolve(`/franchises/${slug}/activity`)}>Activity</Tab>
		<Tab active={isEditHistory} href={resolve(`/franchises/${slug}/edit-history`)}>Edit History</Tab
		>
	</TabNav>

	{@render children()}
</article>

<style>
	article {
		max-width: 64rem;
	}

	header {
		margin-bottom: var(--size-6);
	}

	h1 {
		font-size: var(--font-size-7);
		font-weight: 700;
		color: var(--color-text-primary);
		margin-bottom: var(--size-4);
	}

	.description {
		margin-bottom: var(--size-6);
	}
</style>
