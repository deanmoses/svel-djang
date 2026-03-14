<script lang="ts">
	import client from '$lib/api/client';
	import { createAsyncLoader } from '$lib/async-loader.svelte';
	import CardGrid from '$lib/components/grid/CardGrid.svelte';
	import Markdown from '$lib/components/Markdown.svelte';
	import TitleCard from '$lib/components/cards/TitleCard.svelte';
	import { pageTitle } from '$lib/constants';

	let { data } = $props();
	let profile = $derived(data.profile);

	const titles = createAsyncLoader(async () => {
		const { data: result } = await client.GET('/api/titles/', {
			params: { query: { display: profile.slug, page_size: 500 } }
		});
		return result?.items ?? [];
	}, []);
</script>

<svelte:head>
	<title>{pageTitle(profile.name)}</title>
</svelte:head>

<article>
	<header>
		<h1>{profile.name}</h1>
		{#if profile.description_html}
			<Markdown html={profile.description_html} />
		{/if}
	</header>

	{#if titles.loading}
		<p class="empty">Loading titles…</p>
	{:else if titles.error}
		<p class="empty">Failed to load titles.</p>
	{:else if titles.data.length === 0}
		<p class="empty">No titles with this display type.</p>
	{:else}
		<section>
			<h2>Titles ({titles.data.length})</h2>
			<CardGrid>
				{#each titles.data as title (title.slug)}
					<TitleCard
						slug={title.slug}
						name={title.name}
						thumbnailUrl={title.thumbnail_url}
						manufacturerName={title.manufacturer_name}
						year={title.year}
					/>
				{/each}
			</CardGrid>
		</section>
	{/if}
</article>

<style>
	article {
		max-width: 64rem;
	}

	header {
		margin-bottom: var(--size-6);
	}

	h1 {
		font-size: var(--font-size-7);
		font-weight: 700;
		color: var(--color-text-primary);
		margin-bottom: var(--size-4);
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
