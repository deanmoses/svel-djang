<script lang="ts">
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import { auth } from '$lib/auth.svelte';
	import MetaTags from '$lib/components/MetaTags.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
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
			!page.url.pathname.endsWith('/sources') &&
			!page.url.pathname.endsWith('/edit-history') &&
			!isMedia
	);
	let isEdit = $derived(page.url.pathname.endsWith('/edit'));
	let isSources = $derived(page.url.pathname.endsWith('/sources'));
	let isEditHistory = $derived(page.url.pathname.endsWith('/edit-history'));
</script>

<MetaTags
	title={person.name}
	description={person.description?.text || `${person.name} — pinball industry professional`}
	url={page.url.href}
	image={person.photo_url}
	imageAlt={person.photo_url ? `Photo of ${person.name}` : undefined}
/>

<article>
	<PageHeader
		title={person.name}
		breadcrumbs={[{ label: 'People', href: '/people' }]}
		--page-header-mb="var(--size-5)"
		--page-header-title-mb="var(--size-2)"
	/>

	<TabNav>
		<Tab active={isDetail} href={resolve(`/people/${slug}`)}>Titles</Tab>
		<Tab active={isMedia} href={resolve(`/people/${slug}/media`)}>Media</Tab>
		{#if auth.isAuthenticated}
			<Tab active={isEdit} href={resolve(`/people/${slug}/edit`)}>Edit</Tab>
		{/if}
		<Tab active={isSources} href={resolve(`/people/${slug}/sources`)}>Sources</Tab>
		<Tab active={isEditHistory} href={resolve(`/people/${slug}/edit-history`)}>Edit History</Tab>
	</TabNav>

	{@render children()}
</article>

<style>
	article {
		max-width: 64rem;
	}
</style>
