<script lang="ts">
	import { resolve } from '$app/paths';
	import Card from './Card.svelte';

	let {
		slug,
		name,
		thumbnailUrl = null,
		creditCount = 0
	}: {
		slug: string;
		name: string;
		thumbnailUrl?: string | null;
		creditCount?: number;
	} = $props();
</script>

<Card href={resolve(`/people/${slug}`)} title={name} {thumbnailUrl}>
	<p class="card-count">{creditCount} credit{creditCount === 1 ? '' : 's'}</p>
</Card>

<style>
	.card-count {
		font-size: var(--font-size-0);
		color: var(--color-text-muted);
	}
</style>
