<script lang="ts" generics="T">
	import type { Snippet } from 'svelte';
	import ScrollableGrid from './ScrollableGrid.svelte';

	let {
		items,
		hasMore,
		loadMore,
		children
	}: {
		items: T[];
		hasMore: boolean;
		loadMore: () => void;
		children: Snippet<[T]>;
	} = $props();
</script>

<ScrollableGrid {hasMore} onSentinel={loadMore}>
	{#each items as item (item)}
		{@render children(item)}
	{/each}
</ScrollableGrid>
