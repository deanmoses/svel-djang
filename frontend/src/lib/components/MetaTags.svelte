<script lang="ts">
	import { SITE_NAME } from '$lib/constants';
	import {
		buildFullTitle,
		truncateDescription,
		buildCanonicalUrl,
		twitterCardType
	} from './meta-tags';

	let {
		title,
		description,
		url,
		image,
		imageAlt
	}: {
		title: string;
		description: string;
		url: string;
		image?: string | null;
		imageAlt?: string;
	} = $props();

	let canonicalUrl = $derived(buildCanonicalUrl(url));
	let fullTitle = $derived(buildFullTitle(title));
	let truncatedDescription = $derived(truncateDescription(description));
</script>

<svelte:head>
	<title>{fullTitle}</title>
	<meta name="description" content={truncatedDescription} />
	<link rel="canonical" href={canonicalUrl} />

	<meta property="og:type" content="website" />
	<meta property="og:site_name" content={SITE_NAME} />
	<meta property="og:title" content={title} />
	<meta property="og:description" content={truncatedDescription} />
	<meta property="og:url" content={canonicalUrl} />
	{#if image}
		<meta property="og:image" content={image} />
		{#if imageAlt}
			<meta property="og:image:alt" content={imageAlt} />
		{/if}
	{/if}

	<meta name="twitter:card" content={twitterCardType(image)} />
	<meta name="twitter:title" content={title} />
	<meta name="twitter:description" content={truncatedDescription} />
	{#if image}
		<meta name="twitter:image" content={image} />
		{#if imageAlt}
			<meta name="twitter:image:alt" content={imageAlt} />
		{/if}
	{/if}
</svelte:head>
