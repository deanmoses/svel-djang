<script lang="ts">
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import { pageTitle } from '$lib/constants';
	import { auth } from '$lib/auth.svelte';
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';
	import Markdown from '$lib/components/Markdown.svelte';
	import TabNav from '$lib/components/TabNav.svelte';
	import Tab from '$lib/components/Tab.svelte';

	let { data, children } = $props();
	let mfr = $derived(data.manufacturer);
	let slug = $derived(page.params.slug);

	$effect(() => {
		auth.load();
	});

	let isDetail = $derived(
		!page.url.pathname.endsWith('/edit') &&
			!page.url.pathname.endsWith('/activity') &&
			!page.url.pathname.endsWith('/systems')
	);
	let isEdit = $derived(page.url.pathname.endsWith('/edit'));
	let isActivity = $derived(page.url.pathname.endsWith('/activity'));
	let isSystems = $derived(page.url.pathname.endsWith('/systems'));
</script>

<svelte:head>
	<title>{pageTitle(mfr.name)}</title>
</svelte:head>

<article>
	<header>
		<Breadcrumb crumbs={[{ label: 'Manufacturers', href: '/manufacturers' }]} current={mfr.name} />
		<h1>{mfr.name}</h1>
		{#if mfr.description_html}
			<Markdown html={mfr.description_html} />
		{/if}
	</header>

	<TabNav>
		<Tab active={isDetail} href={resolve(`/manufacturers/${slug}`)}>Titles</Tab>
		{#if mfr.systems.length > 0}
			<Tab active={isSystems} href={resolve(`/manufacturers/${slug}/systems`)}>Systems</Tab>
		{/if}
		{#if auth.isAuthenticated}
			<Tab active={isEdit} href={resolve(`/manufacturers/${slug}/edit`)}>Edit</Tab>
		{/if}
		<Tab active={isActivity} href={resolve(`/manufacturers/${slug}/activity`)}>Activity</Tab>
	</TabNav>

	{@render children()}
</article>

<style>
	article {
		max-width: 64rem;
	}

	header {
		margin-bottom: var(--size-5);
	}

	h1 {
		font-size: var(--font-size-7);
		font-weight: 700;
		color: var(--color-text-primary);
		margin-bottom: var(--size-2);
	}
</style>
