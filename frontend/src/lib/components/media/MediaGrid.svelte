<script lang="ts">
	import type { components } from '$lib/api/schema';
	import MediaCard from './MediaCard.svelte';
	import MediaLightbox from './MediaLightbox.svelte';

	type UploadedMedia = components['schemas']['UploadedMediaSchema'];

	const BATCH_SIZE = 100;

	let {
		media,
		categories = [],
		canEdit = false,
		ondelete,
		onsetprimary
	}: {
		media: UploadedMedia[];
		categories?: string[];
		canEdit?: boolean;
		ondelete?: (assetUuid: string) => void;
		onsetprimary?: (assetUuid: string) => void;
	} = $props();

	let activeCategory = $state<string | null>(null);

	let filteredMedia = $derived(
		activeCategory ? media.filter((m) => m.category === activeCategory) : media
	);

	let visibleCount = $state(BATCH_SIZE);
	let visibleMedia = $derived(filteredMedia.slice(0, visibleCount));
	let hasMore = $derived(visibleCount < filteredMedia.length);

	// Reset visible count when filter changes
	$effect(() => {
		void activeCategory;
		visibleCount = BATCH_SIZE;
	});

	// Infinite scroll sentinel
	let sentinel: HTMLDivElement | undefined = $state();

	$effect(() => {
		if (!sentinel) return;
		const observer = new IntersectionObserver(
			(entries) => {
				if (entries[0].isIntersecting) {
					visibleCount += BATCH_SIZE;
				}
			},
			{ rootMargin: '200px' }
		);
		observer.observe(sentinel);
		return () => observer.disconnect();
	});

	// Category counts — single pass over the array, derived so it recalculates only when media changes
	let categoryCounts = $derived(
		media.reduce<Record<string, number>>((acc, m) => {
			if (m.category) acc[m.category] = (acc[m.category] ?? 0) + 1;
			return acc;
		}, {})
	);

	// Lightbox state
	let lightboxIndex = $state<number | null>(null);

	function openLightbox(uuid: string) {
		lightboxIndex = filteredMedia.findIndex((m) => m.asset_uuid === uuid);
	}

	function closeLightbox() {
		lightboxIndex = null;
	}
</script>

<div class="media-grid-container">
	<div class="filters">
		<button
			class="filter-btn"
			class:active={activeCategory === null}
			onclick={() => (activeCategory = null)}
		>
			All ({media.length})
		</button>
		{#each categories as cat (cat)}
			<button
				class="filter-btn"
				class:active={activeCategory === cat}
				onclick={() => (activeCategory = cat)}
			>
				{cat} ({categoryCounts[cat] ?? 0})
			</button>
		{/each}
	</div>

	{#if filteredMedia.length === 0}
		<p class="empty">
			{#if activeCategory}
				No {activeCategory} images yet.
			{:else}
				No images yet.
			{/if}
		</p>
	{:else}
		<div class="grid">
			{#each visibleMedia as asset (asset.asset_uuid)}
				<MediaCard {asset} {canEdit} {ondelete} {onsetprimary} onclick={openLightbox} />
			{/each}
		</div>

		{#if hasMore}
			<div class="sentinel" bind:this={sentinel}></div>
		{/if}
	{/if}
</div>

{#if lightboxIndex !== null}
	<MediaLightbox media={filteredMedia} initialIndex={lightboxIndex} onclose={closeLightbox} />
{/if}

<style>
	.filters {
		display: flex;
		flex-wrap: wrap;
		gap: var(--size-2);
		margin-bottom: var(--size-4);
	}

	.filter-btn {
		background: none;
		border: 1px solid var(--color-border-soft);
		border-radius: var(--radius-2);
		padding: var(--size-1) var(--size-3);
		font-size: var(--font-size-1);
		color: var(--color-text-muted);
		cursor: pointer;
		transition:
			color 0.15s ease,
			border-color 0.15s ease;
	}

	.filter-btn:hover {
		color: var(--color-text);
		border-color: var(--color-border);
	}

	.filter-btn.active {
		color: var(--color-accent);
		border-color: var(--color-accent);
	}

	.grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(14rem, 1fr));
		gap: var(--size-4);
	}

	.empty {
		text-align: center;
		color: var(--color-text-muted);
		font-size: var(--font-size-1);
		padding: var(--size-6) 0;
	}

	.sentinel {
		height: 1px;
	}
</style>
