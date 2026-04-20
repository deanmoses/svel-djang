<script lang="ts">
	import SimpleTaxonomyEditSectionPage from '$lib/components/SimpleTaxonomyEditSectionPage.svelte';
	import { saveTechnologySubgenerationClaims } from '../../save-technology-subgeneration-claims';

	let { data } = $props();
	let profile = $derived(data.profile);
</script>

<SimpleTaxonomyEditSectionPage
	{profile}
	basePath="/technology-subgenerations"
	saveClaims={saveTechnologySubgenerationClaims}
/>
