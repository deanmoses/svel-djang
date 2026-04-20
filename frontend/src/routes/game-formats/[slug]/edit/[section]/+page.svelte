<script lang="ts">
	import SimpleTaxonomyEditSectionPage from '$lib/components/SimpleTaxonomyEditSectionPage.svelte';
	import { saveGameFormatClaims } from '../../save-game-format-claims';

	let { data } = $props();
	let profile = $derived(data.profile);
</script>

<SimpleTaxonomyEditSectionPage
	{profile}
	basePath="/game-formats"
	saveClaims={saveGameFormatClaims}
/>
