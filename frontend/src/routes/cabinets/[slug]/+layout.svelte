<script lang="ts">
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import { SITE_NAME } from '$lib/constants';
	import MetaTags from '$lib/components/MetaTags.svelte';
	import { auth } from '$lib/auth.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import AttributionLine from '$lib/components/AttributionLine.svelte';
	import Markdown from '$lib/components/Markdown.svelte';
	import TabNav from '$lib/components/TabNav.svelte';
	import Tab from '$lib/components/Tab.svelte';

	let { data, children } = $props();
	let profile = $derived(data.profile);
	let slug = $derived(page.params.slug);

	$effect(() => {
		auth.load();
	});

	let isDetail = $derived(
		!page.url.pathname.endsWith('/edit') && !page.url.pathname.endsWith('/sources')
	);
	let isEdit = $derived(page.url.pathname.endsWith('/edit'));
	let isSources = $derived(page.url.pathname.endsWith('/sources'));
</script>

<MetaTags
	title={profile.name}
	description={profile.description?.text || `${profile.name} — ${SITE_NAME}`}
	url={page.url.href}
/>

<article>
	<PageHeader title={profile.name} breadcrumbs={[{ label: 'Cabinets', href: '/cabinets' }]} />

	{#if profile.description?.html}
		<div class="description">
			<Markdown html={profile.description.html} citations={profile.description.citations} />
			<AttributionLine attribution={profile.description.attribution} />
		</div>
	{/if}

	<TabNav>
		<Tab active={isDetail} href={resolve(`/cabinets/${slug}`)}>Detail</Tab>
		{#if auth.isAuthenticated}
			<Tab active={isEdit} href={resolve(`/cabinets/${slug}/edit`)}>Edit</Tab>
		{/if}
		<Tab active={isSources} href={resolve(`/cabinets/${slug}/sources`)}>Sources</Tab>
	</TabNav>

	{@render children()}
</article>

<style>
	article {
		max-width: 64rem;
	}

	.description {
		margin-bottom: var(--size-6);
	}
</style>
