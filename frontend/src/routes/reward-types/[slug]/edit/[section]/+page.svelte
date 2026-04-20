<script lang="ts">
	import SimpleTaxonomyEditSectionPage from '$lib/components/SimpleTaxonomyEditSectionPage.svelte';
	import { saveRewardTypeClaims } from '../../save-reward-type-claims';

	let { data } = $props();
	let profile = $derived(data.profile);
</script>

<SimpleTaxonomyEditSectionPage
	{profile}
	basePath="/reward-types"
	saveClaims={saveRewardTypeClaims}
/>
