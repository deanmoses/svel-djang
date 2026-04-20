<script lang="ts">
	import HierarchicalTaxonomyMobileMetaBar from './HierarchicalTaxonomyMobileMetaBar.svelte';

	let {
		basePath = '/gameplay-features',
		parents = [{ name: 'Physical Feature', slug: 'physical-feature' }],
		aliases = ['Pop'],
		parentLabel = 'Type of',
		aliasLabel = 'Also known as'
	}: {
		basePath?: string;
		parents?: { name: string; slug: string }[];
		aliases?: string[];
		parentLabel?: string;
		aliasLabel?: string;
	} = $props();
</script>

<HierarchicalTaxonomyMobileMetaBar {basePath} {parents} {aliases} {parentLabel} {aliasLabel} />
