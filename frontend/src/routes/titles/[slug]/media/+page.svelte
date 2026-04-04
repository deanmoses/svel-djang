<script lang="ts">
	import { invalidateAll } from '$app/navigation';
	import { auth } from '$lib/auth.svelte';
	import { MEDIA_CATEGORIES } from '$lib/api/catalog-meta';
	import { detachMedia, setPrimary } from '$lib/api/media-api';
	import MediaGrid from '$lib/components/media/MediaGrid.svelte';
	import LinkButton from '$lib/components/LinkButton.svelte';

	let { data } = $props();
	let md = $derived(data.title.model_detail);
	let actionError = $state('');

	async function handleDelete(assetUuid: string) {
		if (!md) return;
		actionError = '';
		try {
			await detachMedia('machinemodel', md.slug, assetUuid);
			await invalidateAll();
		} catch (err) {
			actionError = err instanceof Error ? err.message : 'Failed to remove image.';
		}
	}

	async function handleSetPrimary(assetUuid: string) {
		if (!md) return;
		actionError = '';
		try {
			await setPrimary('machinemodel', md.slug, assetUuid);
			await invalidateAll();
		} catch (err) {
			actionError = err instanceof Error ? err.message : 'Failed to set primary image.';
		}
	}
</script>

{#if md}
	{#if actionError}
		<p class="error">{actionError}</p>
	{/if}

	{#if auth.isAuthenticated}
		<div class="upload-action">
			<LinkButton href={`/titles/${data.title.slug}/media/upload`}>Upload Media</LinkButton>
		</div>
	{/if}

	<MediaGrid
		media={md.uploaded_media}
		categories={[...MEDIA_CATEGORIES.machinemodel]}
		canEdit={auth.isAuthenticated}
		ondelete={handleDelete}
		onsetprimary={handleSetPrimary}
	/>
{/if}

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
