<script lang="ts">
	import { pageTitle } from '$lib/constants';

	let { data } = $props();
</script>

<svelte:head>
	<title>{pageTitle('Hello')}</title>
</svelte:head>

<article class="hello-page">
	<h1>Hello World</h1>
	<p class="message">{data.message}</p>
	<p class="proof">This content was rendered on the server.</p>
</article>

<style>
	.hello-page {
		max-width: 40rem;
		padding: var(--size-6) 0;
	}

	h1 {
		font-size: var(--font-size-7);
		margin-bottom: var(--size-4);
	}

	.message {
		font-size: var(--font-size-4);
		color: var(--color-text-primary);
		margin-bottom: var(--size-3);
	}

	.proof {
		color: var(--color-text-muted);
	}
</style>
