<script>
	import '../app.css';
	import Nav from '$lib/components/Nav.svelte';
	import Footer from '$lib/components/Footer.svelte';

	let { children } = $props();
</script>

<div class="site-shell">
	<Nav />

	<main class="page-content">
		{@render children()}
	</main>

	<Footer />
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
</style>
