<script lang="ts">
	import SimpleTaxonomyEditSectionPage from '$lib/components/SimpleTaxonomyEditSectionPage.svelte';
	import { saveCabinetClaims } from '../../save-cabinet-claims';

	let { data } = $props();
	let profile = $derived(data.profile);
</script>

<SimpleTaxonomyEditSectionPage {profile} basePath="/cabinets" saveClaims={saveCabinetClaims} />
