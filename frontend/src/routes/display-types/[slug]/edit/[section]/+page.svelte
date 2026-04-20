<script lang="ts">
	import SimpleTaxonomyEditSectionPage from '$lib/components/SimpleTaxonomyEditSectionPage.svelte';
	import { saveDisplayTypeClaims } from '../../save-display-type-claims';

	let { data } = $props();
	let profile = $derived(data.profile);
</script>

<SimpleTaxonomyEditSectionPage
	{profile}
	basePath="/display-types"
	saveClaims={saveDisplayTypeClaims}
/>
