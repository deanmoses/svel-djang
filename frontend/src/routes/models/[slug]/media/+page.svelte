<script lang="ts">
	import { auth } from '$lib/auth.svelte';
	import { MEDIA_CATEGORIES } from '$lib/api/catalog-meta';
	import MediaEditor from '$lib/components/editors/MediaEditor.svelte';
	import MediaGrid from '$lib/components/media/MediaGrid.svelte';

	let { data } = $props();
	let model = $derived(data.model);
</script>

{#if auth.isAuthenticated}
	<MediaEditor entityType="model" slug={model.slug} media={model.uploaded_media} />
{:else}
	<MediaGrid
		media={model.uploaded_media}
		categories={[...MEDIA_CATEGORIES.model]}
		canEdit={false}
	/>
{/if}
