<script lang="ts">
	import SimpleTaxonomyEditSectionPage from '$lib/components/SimpleTaxonomyEditSectionPage.svelte';
	import { saveTechnologyGenerationClaims } from '../../save-technology-generation-claims';

	let { data } = $props();
	let profile = $derived(data.profile);
</script>

<SimpleTaxonomyEditSectionPage
	{profile}
	basePath="/technology-generations"
	saveClaims={saveTechnologyGenerationClaims}
/>
