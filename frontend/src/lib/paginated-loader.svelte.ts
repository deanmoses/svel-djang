import { onMount } from 'svelte';

/**
 * Reactive paginated data loader for use inside Svelte components.
 *
 * Fetches the first page in `onMount` and exposes a `loadMore()` method
 * to fetch subsequent pages, appending results to the accumulated `items`.
 */
export function createPaginatedLoader<T>(
	fetchPage: (page: number) => Promise<{ items: T[]; count: number }>
) {
	let items = $state<T[]>([]);
	let count = $state(0);
	let loading = $state(true);
	let loadingMore = $state(false);
	let error = $state<string | null>(null);
	let nextPage = $state(1);
	let hasMore = $state(true);

	async function fetchNextPage() {
		try {
			const result = await fetchPage(nextPage);
			items = [...items, ...result.items];
			count = result.count;
			nextPage += 1;
			hasMore = items.length < result.count;
		} catch (e) {
			error = e instanceof Error ? e.message : 'Failed to load data';
		}
	}

	onMount(async () => {
		await fetchNextPage();
		loading = false;
	});

	function loadMore() {
		if (loadingMore || !hasMore) return;
		loadingMore = true;
		fetchNextPage().finally(() => {
			loadingMore = false;
		});
	}

	return {
		get items() {
			return items;
		},
		get count() {
			return count;
		},
		get loading() {
			return loading;
		},
		get loadingMore() {
			return loadingMore;
		},
		get error() {
			return error;
		},
		get hasMore() {
			return hasMore;
		},
		loadMore
	};
}
