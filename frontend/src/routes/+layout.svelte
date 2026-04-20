<script>
	import '../app.css';
	import { page } from '$app/state';
	import Nav from '$lib/components/Nav.svelte';
	import Footer from '$lib/components/Footer.svelte';
	import ToastHost from '$lib/toast/ToastHost.svelte';

	let { children } = $props();

	// Focus-mode routes render their own minimal chrome; suppress site
	// Nav/Footer and the page-content wrapper. Patterns:
	//   /:entity/new                           create a top-level record
	//   /:entity/:slug/:child/new              create a nested record
	//   /:entity/:slug/edit                    edit (no section)
	//   /:entity/:slug/edit/:section           edit a section
	//   /:entity/:slug/delete                  destructive confirmation
	// Note: `edit` and `delete` require a slug segment before them so a
	// catalog record with slug='edit' or 'delete' (e.g. /titles/delete)
	// still gets full chrome. `new` is safe without that guard because
	// SvelteKit's route priority gives /:entity/new to the create page,
	// not the detail page.
	let isFocusMode = $derived(
		/\/new$|\/[^/]+\/[^/]+\/edit(\/|$)|\/[^/]+\/[^/]+\/delete$/.test(page.url.pathname)
	);
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

	<ToastHost />
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
