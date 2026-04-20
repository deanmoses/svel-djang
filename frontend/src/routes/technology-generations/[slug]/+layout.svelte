<script lang="ts">
	import SimpleTaxonomyDetailLayout from '$lib/components/SimpleTaxonomyDetailLayout.svelte';
	import { saveTechnologyGenerationClaims } from './save-technology-generation-claims';

	let { data, children } = $props();
	let profile = $derived(data.profile);
</script>

<SimpleTaxonomyDetailLayout
	{profile}
	parentLabel="Technology Generations"
	basePath="/technology-generations"
	saveClaims={saveTechnologyGenerationClaims}
>
	{@render children()}
</SimpleTaxonomyDetailLayout>
