<script lang="ts">
	import SimpleTaxonomyEditSectionLayout from '$lib/components/SimpleTaxonomyEditSectionLayout.svelte';

	let { children } = $props();
</script>

<SimpleTaxonomyEditSectionLayout basePath="/technology-generations">
	{@render children()}
</SimpleTaxonomyEditSectionLayout>
