<script lang="ts" generics="T">
	import type { Snippet } from 'svelte';
	import CardGrid from './CardGrid.svelte';

	const BATCH_SIZE = 100;

	let {
		items,
		entityName = 'result',
		entityNamePlural = `${entityName}s`,
		children
	}: {
		items: T[];
		entityName?: string;
		entityNamePlural?: string;
		children: Snippet<[T]>;
	} = $props();

	let visibleCount = $state(BATCH_SIZE);
	let sentinel: HTMLDivElement | undefined = $state();

	let visibleItems = $derived(items.slice(0, visibleCount));
	let hasMore = $derived(visibleCount < items.length);
	let countLabel = $derived(
		`${items.length.toLocaleString()} ${items.length === 1 ? entityName : entityNamePlural}`
	);

	// Reset visible count when items change
	$effect(() => {
		void items;
		visibleCount = BATCH_SIZE;
	});

	$effect(() => {
		if (!sentinel) return;
		const observer = new IntersectionObserver(
			(entries) => {
				if (entries[0].isIntersecting && hasMore) {
					visibleCount += BATCH_SIZE;
				}
			},
			{ rootMargin: '200px' }
		);
		observer.observe(sentinel);
		return () => observer.disconnect();
	});
</script>

<p class="count">{countLabel}</p>

<CardGrid>
	{#each visibleItems as item (item)}
		{@render children(item)}
	{/each}
</CardGrid>

{#if hasMore}
	<div class="sentinel" bind:this={sentinel}></div>
{/if}

<style>
	.count {
		text-align: center;
		color: var(--color-text-muted);
		font-size: var(--font-size-1);
		margin-bottom: var(--size-4);
	}

	.sentinel {
		height: 1px;
	}
</style>
