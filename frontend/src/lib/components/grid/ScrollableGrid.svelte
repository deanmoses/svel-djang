<script lang="ts">
	import type { Snippet } from 'svelte';
	import CardGrid from './CardGrid.svelte';

	let {
		hasMore,
		onSentinel,
		children
	}: {
		hasMore: boolean;
		onSentinel: () => void;
		children: Snippet;
	} = $props();

	let sentinel: HTMLDivElement | undefined = $state();

	$effect(() => {
		if (!sentinel) return;
		const observer = new IntersectionObserver(
			(entries) => {
				if (entries[0].isIntersecting) {
					onSentinel();
				}
			},
			{ rootMargin: '200px' }
		);
		observer.observe(sentinel);
		return () => observer.disconnect();
	});
</script>

<CardGrid>
	{@render children()}
</CardGrid>

{#if hasMore}
	<div class="sentinel" bind:this={sentinel}></div>
{/if}

<style>
	.sentinel {
		height: 1px;
	}
</style>
