<script lang="ts">
	import SimpleTaxonomyDetailLayout from '$lib/components/SimpleTaxonomyDetailLayout.svelte';
	import { saveRewardTypeClaims } from './save-reward-type-claims';

	let { data, children } = $props();
	let profile = $derived(data.profile);
</script>

<SimpleTaxonomyDetailLayout
	{profile}
	parentLabel="Reward Types"
	basePath="/reward-types"
	saveClaims={saveRewardTypeClaims}
>
	{@render children()}
</SimpleTaxonomyDetailLayout>
