<script lang="ts">
	import { auth } from '$lib/auth.svelte';
	import { MEDIA_CATEGORIES } from '$lib/api/catalog-meta';
	import MediaEditor from '$lib/components/editors/MediaEditor.svelte';
	import MediaGrid from '$lib/components/media/MediaGrid.svelte';

	let { data } = $props();
	let person = $derived(data.person);
</script>

{#if auth.isAuthenticated}
	<MediaEditor entityType="person" slug={person.slug} media={person.uploaded_media} />
{:else}
	<MediaGrid
		media={person.uploaded_media}
		categories={[...MEDIA_CATEGORIES.person]}
		canEdit={false}
	/>
{/if}
