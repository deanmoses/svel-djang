<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		href,
		title,
		thumbnailUrl = null,
		children = undefined
	}: {
		href: string;
		title: string;
		thumbnailUrl?: string | null;
		children?: Snippet;
	} = $props();
</script>

<!-- eslint-disable-next-line svelte/no-navigation-without-resolve -- href is pre-resolved by caller -->
<a {href} class="card">
	{#if thumbnailUrl}
		<img src={thumbnailUrl} alt="" class="card-img" loading="lazy" />
	{:else}
		<div class="card-img-placeholder"></div>
	{/if}
	<div class="card-body">
		<h3 class="card-title">{title}</h3>
		{#if children}
			{@render children()}
		{/if}
	</div>
</a>

<style>
	.card {
		display: flex;
		flex-direction: column;
		background-color: var(--color-surface);
		border: 1px solid var(--color-border-soft);
		border-radius: var(--radius-2);
		overflow: hidden;
		text-decoration: none;
		color: inherit;
		transition:
			border-color 0.15s var(--ease-2),
			box-shadow 0.15s var(--ease-2);
	}

	.card:hover {
		border-color: var(--color-accent);
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
	}

	.card-img {
		width: 100%;
		height: 8rem;
		object-fit: cover;
	}

	.card-img-placeholder {
		width: 100%;
		height: 8rem;
		background-color: var(--color-border-soft);
	}

	.card-body {
		padding: var(--size-3);
	}

	.card-title {
		font-size: var(--font-size-2);
		font-weight: 600;
		color: var(--color-text-primary);
		margin-bottom: var(--size-1);
	}
</style>
