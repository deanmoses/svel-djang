<script lang="ts">
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import { pageTitle } from '$lib/constants';
	import { auth } from '$lib/auth.svelte';
	import Breadcrumb from '$lib/components/Breadcrumb.svelte';
	import TabNav from '$lib/components/TabNav.svelte';
	import Tab from '$lib/components/Tab.svelte';

	let { data, children } = $props();
	let person = $derived(data.person);
	let slug = $derived(page.params.slug);

	$effect(() => {
		auth.load();
	});

	let isMedia = $derived(
		page.url.pathname.endsWith('/media') || page.url.pathname.includes('/media/')
	);
	let isDetail = $derived(
		!page.url.pathname.endsWith('/edit') &&
			!page.url.pathname.endsWith('/activity') &&
			!page.url.pathname.endsWith('/edit-history') &&
			!isMedia
	);
	let isEdit = $derived(page.url.pathname.endsWith('/edit'));
	let isActivity = $derived(page.url.pathname.endsWith('/activity'));
	let isEditHistory = $derived(page.url.pathname.endsWith('/edit-history'));
</script>

<svelte:head>
	<title>{pageTitle(person.name)}</title>
</svelte:head>

<article>
	<header>
		<Breadcrumb crumbs={[{ label: 'People', href: '/people' }]} current={person.name} />
		<h1>{person.name}</h1>
	</header>

	<TabNav>
		<Tab active={isDetail} href={resolve(`/people/${slug}`)}>Titles</Tab>
		<Tab active={isMedia} href={resolve(`/people/${slug}/media`)}>Media</Tab>
		{#if auth.isAuthenticated}
			<Tab active={isEdit} href={resolve(`/people/${slug}/edit`)}>Edit</Tab>
		{/if}
		<Tab active={isActivity} href={resolve(`/people/${slug}/activity`)}>Activity</Tab>
		<Tab active={isEditHistory} href={resolve(`/people/${slug}/edit-history`)}>Edit History</Tab>
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
