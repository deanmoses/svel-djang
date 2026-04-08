<script lang="ts">
	import AttributionLine from '$lib/components/AttributionLine.svelte';
	import Markdown from '$lib/components/Markdown.svelte';
	import PageHeader from '$lib/components/PageHeader.svelte';
	import { pageTitle } from '$lib/constants';

	let { data } = $props();
	let profile = $derived(data.profile);
</script>

<svelte:head>
	<title>{pageTitle(profile.name)}</title>
</svelte:head>

<article>
	<PageHeader title={profile.name}>
		{#if profile.description?.html}
			<Markdown html={profile.description.html} citations={profile.description.citations} />
			<AttributionLine attribution={profile.description.attribution} />
		{/if}
	</PageHeader>
</article>

<style>
	article {
		max-width: 64rem;
	}
</style>
