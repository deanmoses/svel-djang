<script lang="ts">
	import { goto } from '$app/navigation';
	import { resolve } from '$app/paths';
	import { auth } from '$lib/auth.svelte';
	import { MANUFACTURER_MEDIA_CATEGORIES } from '$lib/api/media-api';
	import MediaUploadZone from '$lib/components/media/MediaUploadZone.svelte';

	let { data } = $props();
	let mfr = $derived(data.manufacturer);

	function handleUploaded() {
		goto(resolve(`/manufacturers/${mfr.slug}/media`), { invalidateAll: true });
	}
</script>

{#if auth.isAuthenticated}
	<h2 class="heading">Upload Media</h2>
	<MediaUploadZone
		entityType="manufacturer"
		slug={mfr.slug}
		categories={[...MANUFACTURER_MEDIA_CATEGORIES]}
		onuploaded={handleUploaded}
	/>
{:else}
	<p class="login-prompt">Log in to upload media.</p>
{/if}

<style>
	.heading {
		font-size: var(--font-size-3);
		margin-bottom: var(--size-4);
	}

	.login-prompt {
		color: var(--color-text-muted);
	}
</style>
