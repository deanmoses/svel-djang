<script lang="ts" generics="T">
	import type { Snippet } from 'svelte';
	import SearchBox from '../SearchBox.svelte';
	import CardGrid from './CardGrid.svelte';
	import InfiniteGrid from './InfiniteGrid.svelte';
	import SkeletonCard from '../cards/SkeletonCard.svelte';
	import { normalizeText } from '$lib/util';

	const SEARCH_THRESHOLD = 12;
	const SKELETON_INDICES = Array.from({ length: 12 }, (_, i) => i);

	let {
		items,
		filterFields,
		loading = false,
		error = null,
		placeholder = 'Search...',
		entityName = 'result',
		entityNamePlural = `${entityName}s`,
		children
	}: {
		items: T[];
		filterFields: (item: T) => (string | number | null | undefined)[];
		loading?: boolean;
		error?: string | null;
		placeholder?: string;
		entityName?: string;
		entityNamePlural?: string;
		children: Snippet<[T]>;
	} = $props();

	let searchQuery = $state('');

	let filteredItems = $derived.by(() => {
		const q = normalizeText(searchQuery.trim());
		if (!q) return items;
		return items.filter((item) =>
			filterFields(item).some((field) => field != null && normalizeText(String(field)).includes(q))
		);
	});

	let showSearch = $derived(items.length >= SEARCH_THRESHOLD || searchQuery.trim() !== '');
</script>

<div class="searchable-grid">
	{#if loading}
		{#if showSearch}
			<SearchBox {placeholder} disabled />
		{/if}
		<CardGrid>
			{#each SKELETON_INDICES as i (i)}
				<SkeletonCard />
			{/each}
		</CardGrid>
	{:else if error}
		<p class="error">{error}</p>
	{:else}
		{#if showSearch}
			<SearchBox bind:value={searchQuery} {placeholder} />
		{/if}

		<InfiniteGrid items={filteredItems} {entityName} {entityNamePlural} {children} />
	{/if}
</div>

<style>
	.searchable-grid {
		padding: var(--size-5) 0;
	}

	.error {
		text-align: center;
		color: var(--color-error);
		padding: var(--size-6) 0;
	}
</style>
