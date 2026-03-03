<script lang="ts">
	import { resolve } from '$app/paths';
	import Card from './Card.svelte';

	let {
		slug,
		name,
		thumbnailUrl = null,
		short_name = null
	}: {
		slug: string;
		name: string;
		thumbnailUrl?: string | null;
		short_name?: string | null;
	} = $props();
</script>

<Card href={resolve(`/titles/${slug}`)} title={name} {thumbnailUrl}>
	{#if short_name && short_name !== name}
		<p class="card-short_name">{short_name}</p>
	{/if}
</Card>

<style>
	.card-short_name {
		font-size: var(--font-size-0);
		color: var(--color-text-muted);
	}
</style>
