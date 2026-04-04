<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import { auth } from '$lib/auth.svelte';
	import { MEDIA_CATEGORIES } from '$lib/api/catalog-meta';
	import { detachMedia, setPrimary } from '$lib/api/media-api';
	import MediaGrid from '$lib/components/media/MediaGrid.svelte';
	import LinkButton from '$lib/components/LinkButton.svelte';

	let { data } = $props();
	let person = $derived(data.person);
	let actionError = $state('');

	async function handleDelete(assetUuid: string) {
		actionError = '';
		try {
			await detachMedia('person', person.slug, assetUuid);
			await invalidateAll();
		} catch (err) {
			actionError = err instanceof Error ? err.message : 'Failed to remove image.';
		}
	}

	async function handleSetPrimary(assetUuid: string) {
		actionError = '';
		try {
			await setPrimary('person', person.slug, assetUuid);
			await invalidateAll();
		} catch (err) {
			actionError = err instanceof Error ? err.message : 'Failed to set primary image.';
		}
	}
</script>

{#if actionError}
	<p class="error">{actionError}</p>
{/if}

{#if auth.isAuthenticated}
	<div class="upload-action">
		<LinkButton href={`/people/${person.slug}/media/upload`}>Upload Media</LinkButton>
	</div>
{/if}

<MediaGrid
	media={person.uploaded_media}
	categories={[...MEDIA_CATEGORIES.person]}
	canEdit={auth.isAuthenticated}
	ondelete={handleDelete}
	onsetprimary={handleSetPrimary}
/>

<style>
	.upload-action {
		margin-bottom: var(--size-4);
	}

	.error {
		color: var(--color-error, #c53030);
		font-size: var(--font-size-1);
		margin-bottom: var(--size-3);
	}
</style>
