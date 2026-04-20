<script lang="ts">
	import SimpleTaxonomyEditSectionPage from '$lib/components/SimpleTaxonomyEditSectionPage.svelte';
	import { saveDisplaySubtypeClaims } from '../../save-display-subtype-claims';

	let { data } = $props();
	let profile = $derived(data.profile);
</script>

<SimpleTaxonomyEditSectionPage
	{profile}
	basePath="/display-subtypes"
	saveClaims={saveDisplaySubtypeClaims}
/>
