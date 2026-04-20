<script lang="ts">
	import SimpleTaxonomyDetailLayout from '$lib/components/SimpleTaxonomyDetailLayout.svelte';
	import { saveCabinetClaims } from './save-cabinet-claims';

	let { data, children } = $props();
	let profile = $derived(data.profile);
</script>

<SimpleTaxonomyDetailLayout
	{profile}
	parentLabel="Cabinets"
	basePath="/cabinets"
	saveClaims={saveCabinetClaims}
>
	{@render children()}
</SimpleTaxonomyDetailLayout>
