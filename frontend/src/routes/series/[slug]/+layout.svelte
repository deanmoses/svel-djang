<script lang="ts">
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import { SITE_NAME } from '$lib/constants';
	import { auth } from '$lib/auth.svelte';
	import MetaTags from '$lib/components/MetaTags.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import AttributionLine from '$lib/components/AttributionLine.svelte';
	import Markdown from '$lib/components/Markdown.svelte';
	import TabNav from '$lib/components/TabNav.svelte';
	import Tab from '$lib/components/Tab.svelte';

	let { data, children } = $props();
	let series = $derived(data.series);
	let slug = $derived(page.params.slug);

	$effect(() => {
		auth.load();
	});

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
	title={series.name}
	description={series.description?.text || `${series.name} — ${SITE_NAME}`}
	url={page.url.href}
/>

<article>
	<PageHeader title={series.name} breadcrumbs={[{ label: 'Series', href: '/series' }]} />

	{#if series.description?.html}
		<div class="description">
			<Markdown html={series.description.html} citations={series.description.citations} />
			<AttributionLine attribution={series.description.attribution} />
		</div>
	{/if}

	<TabNav>
		<Tab active={isDetail} href={resolve(`/series/${slug}`)}>Titles</Tab>
		{#if auth.isAuthenticated}
			<Tab active={isEdit} href={resolve(`/series/${slug}/edit`)}>Edit</Tab>
		{/if}
		<Tab active={isSources} href={resolve(`/series/${slug}/sources`)}>Sources</Tab>
		<Tab active={isEditHistory} href={resolve(`/series/${slug}/edit-history`)}>Edit History</Tab>
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
