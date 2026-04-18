<script>
	import '../app.css';
	import { page } from '$app/state';
	import Nav from '$lib/components/Nav.svelte';
	import Footer from '$lib/components/Footer.svelte';

	let { children } = $props();

	// Focus-mode routes (edit pages and the create pages under /:entity/new)
	// render their own minimal chrome; suppress site Nav/Footer and the
	// page-content wrapper.
	let isFocusMode = $derived(/\/edit(\/|$)|\/new$/.test(page.url.pathname));
</script>

<div class="site-shell">
	{#if !isFocusMode}
		<Nav />
	{/if}

	<main class:page-content={!isFocusMode} class:focus-content={isFocusMode}>
		{@render children()}
	</main>

	{#if !isFocusMode}
		<Footer />
	{/if}
</div>

<style>
	.site-shell {
		display: flex;
		flex-direction: column;
		min-height: 100dvh;
	}

	.page-content {
		flex: 1;
		width: 100%;
		max-width: 72rem;
		margin: 0 auto;
		padding: var(--size-6) var(--size-5);
	}

	.focus-content {
		flex: 1;
		width: 100%;
	}
</style>
