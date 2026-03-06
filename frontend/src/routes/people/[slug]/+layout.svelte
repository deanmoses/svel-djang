<script lang="ts">
	import { page } from '$app/state';
	import { resolve } from '$app/paths';
	import { pageTitle } from '$lib/constants';
	import { auth } from '$lib/auth.svelte';

	let { data, children } = $props();
	let person = $derived(data.person);
	let slug = $derived(page.params.slug);

	$effect(() => {
		auth.load();
	});

	let isDetail = $derived(
		!page.url.pathname.endsWith('/edit') && !page.url.pathname.endsWith('/activity')
	);
	let isEdit = $derived(page.url.pathname.endsWith('/edit'));
	let isActivity = $derived(page.url.pathname.endsWith('/activity'));
</script>

<svelte:head>
	<title>{pageTitle(person.name)}</title>
</svelte:head>

<article>
	<header>
		<h1>{person.name}</h1>
	</header>

	<nav class="tabs" aria-label="Page sections">
		<a class="tab" class:active={isDetail} href={resolve(`/people/${slug}`)}>Titles</a>
		{#if auth.isAuthenticated}
			<a class="tab" class:active={isEdit} href={resolve(`/people/${slug}/edit`)}>Edit</a>
		{/if}
		<a class="tab" class:active={isActivity} href={resolve(`/people/${slug}/activity`)}>
			Activity
		</a>
	</nav>

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

	.tabs {
		display: flex;
		gap: 0;
		border-bottom: 2px solid var(--color-border-soft);
		margin-bottom: var(--size-6);
	}

	.tab {
		padding: var(--size-2) var(--size-4);
		font-size: var(--font-size-1);
		font-weight: 500;
		color: var(--color-text-muted);
		text-decoration: none;
		border-bottom: 2px solid transparent;
		margin-bottom: -2px;
		transition:
			color 0.15s,
			border-color 0.15s;
	}

	.tab:hover {
		color: var(--color-text-primary);
	}

	.tab.active {
		color: var(--color-accent);
		border-bottom-color: var(--color-accent);
	}
</style>
