<script lang="ts">
	import SimpleTaxonomyDetailLayout from '$lib/components/SimpleTaxonomyDetailLayout.svelte';
	import { saveTechnologySubgenerationClaims } from './save-technology-subgeneration-claims';

	let { data, children } = $props();
	let profile = $derived(data.profile);
</script>

<SimpleTaxonomyDetailLayout
	{profile}
	parentLabel="Technology Subgenerations"
	basePath="/technology-subgenerations"
	saveClaims={saveTechnologySubgenerationClaims}
>
	{@render children()}
</SimpleTaxonomyDetailLayout>
