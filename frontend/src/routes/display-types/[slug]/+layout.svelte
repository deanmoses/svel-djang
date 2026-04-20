<script lang="ts">
	import SimpleTaxonomyDetailLayout from '$lib/components/SimpleTaxonomyDetailLayout.svelte';
	import { saveDisplayTypeClaims } from './save-display-type-claims';

	let { data, children } = $props();
	let profile = $derived(data.profile);
</script>

<SimpleTaxonomyDetailLayout
	{profile}
	parentLabel="Display Types"
	basePath="/display-types"
	saveClaims={saveDisplayTypeClaims}
>
	{@render children()}
</SimpleTaxonomyDetailLayout>
