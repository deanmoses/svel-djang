<script lang="ts">
	import { resolve } from '$app/paths';
	import Card from './Card.svelte';

	let {
		slug,
		name,
		thumbnailUrl = null
	}: {
		slug: string;
		name: string;
		thumbnailUrl?: string | null;
	} = $props();
</script>

<Card href={resolve(`/titles/${slug}`)} title={name} {thumbnailUrl} />
