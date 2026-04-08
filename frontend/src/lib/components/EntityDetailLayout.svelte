<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { Crumb } from './Breadcrumb.svelte';
	import type { InlineCitation } from './citation-tooltip';
	import AttributionLine from './AttributionLine.svelte';
	import Markdown from './Markdown.svelte';
	import PageHeader from './PageHeader.svelte';
	import { pageTitle } from '$lib/constants';

	let {
		name,
		description = null,
		breadcrumbs = null,
		children
	}: {
		name: string;
		description?: {
			text?: string;
			html?: string;
			citations?: InlineCitation[];
			attribution?: object | null;
		} | null;
		breadcrumbs?: Crumb[] | null;
		children: Snippet;
	} = $props();
</script>

<svelte:head>
	<title>{pageTitle(name)}</title>
</svelte:head>

<article>
	<PageHeader title={name} {breadcrumbs}>
		{#if description?.html}
			<Markdown html={description.html} citations={description.citations} />
			<AttributionLine attribution={description.attribution} />
		{/if}
	</PageHeader>

	{@render children()}
</article>

<style>
	article {
		max-width: 64rem;
	}
</style>
