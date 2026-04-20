<script lang="ts">
	import HierarchicalTaxonomyChildrenAccordion from './HierarchicalTaxonomyChildrenAccordion.svelte';

	let {
		basePath = '/gameplay-features',
		children = [
			{ name: 'Slingshot', slug: 'slingshot' },
			{ name: 'Bumper', slug: 'bumper' }
		],
		heading = 'Subtypes'
	}: {
		basePath?: string;
		children?: { name: string; slug: string }[];
		heading?: string;
	} = $props();
</script>

<HierarchicalTaxonomyChildrenAccordion {basePath} {children} {heading} />
