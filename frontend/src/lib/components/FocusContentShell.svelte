<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		backHref,
		maxWidth = '48rem',
		heading,
		children
	}: {
		backHref: string;
		maxWidth?: string;
		heading: Snippet;
		children: Snippet;
	} = $props();
</script>

<div class="focus-shell" style:max-width={maxWidth}>
	<header class="focus-header">
		<a href={backHref} class="back-link">&larr; Back</a>
		<div class="heading-slot">
			{@render heading()}
		</div>
	</header>

	{@render children()}
</div>

<style>
	.focus-shell {
		margin: 0 auto;
		padding: var(--size-4);
	}

	.focus-header {
		position: relative;
		display: flex;
		align-items: center;
		justify-content: center;
		margin-bottom: var(--size-4);
		min-height: 2.5rem;
	}

	.back-link {
		position: absolute;
		left: 0;
		font-size: var(--font-size-1);
		color: var(--color-text-muted);
		text-decoration: none;
	}

	.back-link:hover {
		color: var(--color-text-primary);
	}
</style>
