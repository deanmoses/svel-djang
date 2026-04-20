<script lang="ts">
	import SimpleTaxonomyDetailLayout from '$lib/components/SimpleTaxonomyDetailLayout.svelte';
	import { saveTagClaims } from './save-tag-claims';

	let { data, children } = $props();
	let profile = $derived(data.profile);
</script>

<SimpleTaxonomyDetailLayout
	{profile}
	parentLabel="Tags"
	basePath="/tags"
	saveClaims={saveTagClaims}
>
	{@render children()}
</SimpleTaxonomyDetailLayout>
