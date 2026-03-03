<script lang="ts">
	import { resolve } from '$app/paths';
	import Card from './Card.svelte';

	let {
		slug,
		name,
		thumbnailUrl = null,
		tradeName = null,
		modelCount = 0
	}: {
		slug: string;
		name: string;
		thumbnailUrl?: string | null;
		tradeName?: string | null;
		modelCount?: number;
	} = $props();
</script>

<Card href={resolve(`/manufacturers/${slug}`)} title={name} {thumbnailUrl}>
	{#if tradeName && tradeName !== name}
		<p class="card-trade-name">{tradeName}</p>
	{/if}
	<p class="card-count">{modelCount} model{modelCount === 1 ? '' : 's'}</p>
</Card>

<style>
	.card-trade-name {
		font-size: var(--font-size-0);
		color: var(--color-text-muted);
		margin-bottom: var(--size-1);
	}

	.card-count {
		font-size: var(--font-size-0);
		color: var(--color-text-muted);
	}
</style>
