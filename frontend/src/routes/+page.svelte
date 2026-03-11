<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import client from '$lib/api/client';
	import MachineCard from '$lib/components/cards/MachineCard.svelte';
	import { SITE_NAME } from '$lib/constants';
	import { resolveHref } from '$lib/utils';
	import { onMount } from 'svelte';
	import type { components } from '$lib/api/schema';

	type RecentModel = components['schemas']['ModelRecentSchema'];

	let searchQuery = $state('');
	let recentModels = $state<RecentModel[]>([]);

	function handleSubmit(e: Event) {
		e.preventDefault();
		const q = searchQuery.trim();
		if (q) {
			goto(`${resolveHref('/search')}?q=${encodeURIComponent(q)}`);
		}
	}

	onMount(async () => {
		const { data } = await client.GET('/api/models/recent/');
		if (data) recentModels = data;
	});
</script>

<svelte:head>
	<title>{SITE_NAME}</title>
</svelte:head>

<div class="home">
	<section class="hero">
		<h1 class="site-title">{SITE_NAME}</h1>
		<p class="tagline">Cataloging every pinball machine ever made</p>
		<form class="hero-search" onsubmit={handleSubmit}>
			<input
				type="search"
				placeholder="Search titles, manufacturers, people..."
				aria-label="Search the catalog"
				bind:value={searchQuery}
			/>
		</form>
	</section>

	<nav class="explore-links">
		<a href={resolve('/titles')} class="explore-card">
			<span class="explore-label">Titles</span>
			<span class="explore-desc">Browse thousands of pinball machines from the 1930s to today</span>
		</a>
		<a href={resolve('/manufacturers')} class="explore-card">
			<span class="explore-label">Manufacturers</span>
			<span class="explore-desc">From Gottlieb and Bally to Stern and Jersey Jack</span>
		</a>
		<a href={resolve('/people')} class="explore-card">
			<span class="explore-label">People</span>
			<span class="explore-desc">The designers, artists, and engineers behind the games</span>
		</a>
	</nav>

	{#if recentModels.length > 0}
		<section class="recent">
			<h2 class="recent-heading">Newest Machines</h2>
			<div class="recent-grid">
				{#each recentModels as model (model.slug)}
					<MachineCard
						slug={model.slug}
						name={model.name}
						thumbnailUrl={model.thumbnail_url}
						manufacturerName={model.manufacturer_name}
						year={model.year}
					/>
				{/each}
			</div>
		</section>
	{/if}
</div>

<style>
	.home {
		padding: var(--size-5) 0;
	}

	.hero {
		text-align: center;
		padding: var(--size-10) 0 var(--size-8);
	}

	.site-title {
		font-size: var(--font-size-8);
		font-weight: 700;
		color: var(--color-text-primary);
		margin-bottom: var(--size-2);
	}

	.tagline {
		font-size: var(--font-size-3);
		color: var(--color-text-muted);
	}

	.hero-search {
		max-width: 36rem;
		margin: var(--size-6) auto 0;
	}

	.hero-search input[type='search'] {
		width: 100%;
		padding: var(--size-3) var(--size-4);
		font-size: var(--font-size-2);
		font-family: var(--font-body);
		background-color: var(--color-input-bg);
		color: var(--color-text-primary);
		border: 1px solid var(--color-input-border);
		border-radius: var(--radius-3);
		transition:
			border-color 0.15s var(--ease-2),
			box-shadow 0.15s var(--ease-2);
	}

	.hero-search input[type='search']:focus {
		outline: none;
		border-color: var(--color-input-focus);
		box-shadow: 0 0 0 3px var(--color-input-focus-ring);
	}

	.hero-search input[type='search']::placeholder {
		color: var(--color-text-muted);
	}

	.explore-links {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(16rem, 1fr));
		gap: var(--size-4);
		max-width: 54rem;
		margin: 0 auto;
	}

	.explore-card {
		display: flex;
		flex-direction: column;
		padding: var(--size-5);
		border: 1px solid var(--color-border-soft);
		border-radius: var(--radius-2);
		text-decoration: none;
		transition:
			border-color 0.15s var(--ease-2),
			box-shadow 0.15s var(--ease-2);
	}

	.explore-card:hover {
		border-color: var(--color-accent);
		box-shadow: 0 2px 8px rgb(0 0 0 / 0.08);
	}

	.explore-label {
		font-size: var(--font-size-4);
		font-weight: 600;
		color: var(--color-accent);
		margin-bottom: var(--size-1);
	}

	.explore-desc {
		font-size: var(--font-size-1);
		color: var(--color-text-muted);
		line-height: 1.5;
	}

	.recent {
		max-width: 54rem;
		margin: var(--size-8) auto 0;
	}

	.recent-heading {
		font-size: var(--font-size-4);
		font-weight: 600;
		color: var(--color-text-primary);
		margin-bottom: var(--size-4);
	}

	.recent-grid {
		display: grid;
		grid-template-columns: repeat(3, 1fr);
		gap: var(--size-4);
	}

	@media (max-width: 640px) {
		.recent-grid {
			grid-template-columns: 1fr;
		}
	}
</style>
