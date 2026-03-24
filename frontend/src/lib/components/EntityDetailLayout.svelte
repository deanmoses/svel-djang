<script lang="ts">
	import type { Snippet } from 'svelte';
	import Breadcrumb from './Breadcrumb.svelte';
	import Markdown from './Markdown.svelte';
	import { pageTitle } from '$lib/constants';

	let {
		name,
		description = null,
		breadcrumbs = null,
		children
	}: {
		name: string;
		description?: { text?: string; html?: string; attribution?: object | null } | null;
		breadcrumbs?: { label: string; href: string }[] | null;
		children: Snippet;
	} = $props();
</script>

<svelte:head>
	<title>{pageTitle(name)}</title>
</svelte:head>

<article>
	<header>
		{#if breadcrumbs}
			<Breadcrumb crumbs={breadcrumbs} current={name} />
		{/if}
		<h1>{name}</h1>
		{#if description?.html}
			<Markdown html={description.html} />
		{/if}
	</header>

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
</style>
