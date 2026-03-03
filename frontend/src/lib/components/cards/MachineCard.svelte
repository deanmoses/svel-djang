<script lang="ts">
	import { resolve } from '$app/paths';
	import Card from './Card.svelte';

	let {
		slug,
		name,
		thumbnailUrl = null,
		manufacturerName = null,
		year = null,
		machineType = null,
		ipdbRating = null,
		pinsideRating = null,
		roles = null
	}: {
		slug: string;
		name: string;
		thumbnailUrl?: string | null;
		manufacturerName?: string | null;
		year?: number | null;
		machineType?: string | null;
		ipdbRating?: number | null;
		pinsideRating?: number | null;
		roles?: string[] | null;
	} = $props();

	let hasMeta = $derived(!!manufacturerName || !!year || !!machineType);
	let hasRatings = $derived(!!ipdbRating || !!pinsideRating);
</script>

<Card href={resolve(`/models/${slug}`)} title={name} {thumbnailUrl}>
	{#if hasMeta}
		<div class="card-meta">
			{#if manufacturerName}
				<span>{manufacturerName}</span>
			{/if}
			{#if year}
				<span>{year}</span>
			{/if}
			{#if machineType}
				<span>{machineType}</span>
			{/if}
		</div>
	{/if}
	{#if roles && roles.length > 0}
		<div class="card-roles">{roles.join(', ')}</div>
	{/if}
	{#if hasRatings}
		<div class="card-ratings">
			{#if ipdbRating}
				<span>IPDB {ipdbRating}</span>
			{/if}
			{#if pinsideRating}
				<span>Pinside {pinsideRating}</span>
			{/if}
		</div>
	{/if}
</Card>

<style>
	.card-meta {
		display: flex;
		flex-wrap: wrap;
		gap: var(--size-1);
		font-size: var(--font-size-0);
		color: var(--color-text-muted);
	}

	.card-meta span:not(:last-child)::after {
		content: '·';
		margin-left: var(--size-1);
	}

	.card-roles {
		font-size: var(--font-size-0);
		color: var(--color-text-muted);
		font-style: italic;
	}

	.card-ratings {
		display: flex;
		gap: var(--size-2);
		margin-top: var(--size-1);
		font-size: var(--font-size-0);
		color: var(--color-accent);
		font-weight: 500;
	}
</style>
