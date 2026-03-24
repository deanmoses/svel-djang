<script lang="ts">
	import AttributionLine from '$lib/components/AttributionLine.svelte';
	import Markdown from '$lib/components/Markdown.svelte';
	import { pageTitle } from '$lib/constants';

	let { data } = $props();
	let profile = $derived(data.profile);
</script>

<svelte:head>
	<title>{pageTitle(profile.name)}</title>
</svelte:head>

<article>
	<header>
		<h1>{profile.name}</h1>
		{#if profile.description?.html}
			<Markdown html={profile.description.html} />
			<AttributionLine attribution={profile.description.attribution} />
		{/if}
	</header>
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
</style>
