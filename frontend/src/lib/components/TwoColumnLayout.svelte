<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		heroImageUrl = null,
		heroImageAlt = '',
		header,
		main,
		sidebar
	}: {
		heroImageUrl?: string | null;
		heroImageAlt?: string;
		header: Snippet;
		main: Snippet;
		sidebar: Snippet;
	} = $props();
</script>

<article>
	{#if heroImageUrl}
		<div class="hero-banner">
			<img class="hero-bg" src={heroImageUrl} alt={heroImageAlt} />
			<div class="hero-scrim"></div>
			<header class="hero-header">
				{@render header()}
			</header>
		</div>
	{:else}
		<header>
			{@render header()}
		</header>
	{/if}

	<div class="two-col">
		<div class="main-col">
			{@render main()}
		</div>
		<aside class="sidebar">
			{@render sidebar()}
		</aside>
	</div>
</article>

<style>
	/* Hero banner with overlaid text */
	.hero-banner {
		position: relative;
		overflow: hidden;
		border-radius: var(--radius-3);
		min-height: 14rem;
		max-height: 22rem;
		margin-bottom: var(--size-5);
		display: flex;
		align-items: flex-end;
		background-color: var(--color-surface);
	}

	.hero-bg {
		position: absolute;
		inset: 0;
		width: 100%;
		height: 100%;
		object-fit: cover;
		object-position: center 20%;
		z-index: 0;
	}

	.hero-scrim {
		position: absolute;
		inset: 0;
		z-index: 1;
		background: linear-gradient(
			to top,
			rgba(0, 0, 0, 0.85) 0%,
			rgba(0, 0, 0, 0.5) 40%,
			rgba(0, 0, 0, 0.1) 70%,
			transparent 100%
		);
		pointer-events: none;
	}

	.hero-header {
		position: relative;
		z-index: 2;
		padding: var(--size-5) var(--size-5) var(--size-4);
		width: 100%;
		margin-bottom: 0;
	}

	.hero-header :global(h1) {
		color: #ffffff;
		text-shadow: 0 1px 4px rgba(0, 0, 0, 0.6);
	}

	.hero-header :global(.meta) {
		color: rgba(255, 255, 255, 0.85);
	}

	.hero-header :global(.meta a) {
		color: rgba(255, 255, 255, 0.9);
		text-decoration: underline;
		text-decoration-color: rgba(255, 255, 255, 0.4);
	}

	.hero-header :global(.meta a:hover) {
		color: #ffffff;
		text-decoration-color: #ffffff;
	}

	.hero-header :global(.meta span:not(:last-child)::after) {
		color: rgba(255, 255, 255, 0.5);
	}

	.hero-header :global(.chip) {
		background-color: rgba(255, 255, 255, 0.15);
		border-color: rgba(255, 255, 255, 0.25);
		color: rgba(255, 255, 255, 0.9);
		backdrop-filter: blur(4px);
	}

	@media (max-width: 40rem) {
		.hero-banner {
			min-height: 10rem;
			max-height: 16rem;
			border-radius: 0;
			margin-left: calc(-1 * var(--size-5));
			margin-right: calc(-1 * var(--size-5));
		}

		.hero-header {
			padding: var(--size-3) var(--size-4) var(--size-3);
		}

		.hero-header :global(h1) {
			font-size: var(--font-size-5);
		}

		.hero-header :global(.meta) {
			font-size: var(--font-size-0);
		}
	}

	/* Plain header (no image) */
	header {
		margin-bottom: var(--size-5);
	}

	/* Two-column layout */
	.two-col {
		display: grid;
		grid-template-columns: 1fr;
		gap: var(--size-6);
	}

	@media (min-width: 52rem) {
		.two-col {
			grid-template-columns: 1fr 18rem;
		}
	}

	/* Sidebar */
	.sidebar {
		display: flex;
		flex-direction: column;
		gap: var(--size-3);
	}
</style>
