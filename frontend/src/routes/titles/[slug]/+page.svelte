<script lang="ts">
	import { resolve } from '$app/paths';
	import CardGrid from '$lib/components/grid/CardGrid.svelte';
	import MachineCard from '$lib/components/cards/MachineCard.svelte';
	import CreditsList from '$lib/components/CreditsList.svelte';
	import { pageTitle } from '$lib/constants';
	import { resolveHref } from '$lib/utils';

	let { data } = $props();
	let title = $derived(data.title);
</script>

<svelte:head>
	<title>{pageTitle(title.name)}</title>
</svelte:head>

<article>
	{#if title.needs_review}
		<aside class="review-banner">
			<strong>Needs review</strong>
			<p>{title.needs_review_notes}</p>
			{#if title.review_links.length > 0}
				<p class="review-links">
					{#each title.review_links as link, i (link.url)}
						{#if i > 0}
							·
						{/if}
						{#if link.url.startsWith('/')}
							<a href={resolveHref(link.url)}>{link.label}</a>
						{:else}
							<a href={link.url} target="_blank" rel="noopener">{link.label}</a>
						{/if}
					{/each}
				</p>
			{/if}
		</aside>
	{/if}

	<header>
		<h1>{title.name}</h1>
		{#if title.series.length > 0}
			<p class="series-list">
				Series:
				{#each title.series as s, i (s.slug)}
					{#if i > 0},{/if}
					<a href={resolve(`/series/${s.slug}`)}>{s.name}</a>
				{/each}
			</p>
		{/if}
	</header>

	{#if title.machines.length === 0}
		<p class="empty">No machines in this title.</p>
	{:else}
		<section>
			<h2>Machines ({title.machines.length})</h2>
			<CardGrid>
				{#each title.machines as machine (machine.slug)}
					<MachineCard
						slug={machine.slug}
						name={machine.name}
						thumbnailUrl={machine.thumbnail_url}
						manufacturerName={machine.manufacturer_name}
						year={machine.year}
					/>
				{/each}
			</CardGrid>
		</section>
	{/if}

	<CreditsList credits={title.credits} />
</article>

<style>
	article {
		max-width: 64rem;
	}

	.review-banner {
		background-color: color-mix(in srgb, var(--color-warning) 12%, transparent);
		border: 1px solid var(--color-warning);
		border-radius: var(--radius-2);
		padding: var(--size-3) var(--size-4);
		margin-bottom: var(--size-5);
		font-size: var(--font-size-1);
		color: var(--color-text-primary);
	}

	.review-banner strong {
		color: var(--color-warning);
	}

	.review-banner p {
		margin-top: var(--size-1);
	}

	.review-links a {
		color: var(--color-warning);
		text-decoration: underline;
	}

	header {
		margin-bottom: var(--size-6);
	}

	h1 {
		font-size: var(--font-size-7);
		font-weight: 700;
		color: var(--color-text-primary);
		margin-bottom: var(--size-2);
	}

	.series-list {
		font-size: var(--font-size-1);
		color: var(--color-text-muted);
		margin-top: var(--size-1);
	}

	h2 {
		font-size: var(--font-size-3);
		font-weight: 600;
		color: var(--color-text-primary);
		margin-bottom: var(--size-3);
	}

	.empty {
		color: var(--color-text-muted);
		font-size: var(--font-size-2);
		padding: var(--size-8) 0;
		text-align: center;
	}
</style>
