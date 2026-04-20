<script lang="ts">
	import HierarchicalTaxonomySidebar from './HierarchicalTaxonomySidebar.svelte';

	let {
		basePath = '/gameplay-features',
		parents = [{ name: 'Physical Feature', slug: 'physical-feature' }],
		children = [
			{ name: 'Slingshot', slug: 'slingshot' },
			{ name: 'Bumper', slug: 'bumper' }
		],
		aliases = ['Pop'],
		parentHeading = 'Type of',
		childHeading = 'Subtypes',
		aliasHeading = 'Also known as'
	}: {
		basePath?: string;
		parents?: { name: string; slug: string }[];
		children?: { name: string; slug: string }[];
		aliases?: string[];
		parentHeading?: string;
		childHeading?: string;
		aliasHeading?: string;
	} = $props();
</script>

<HierarchicalTaxonomySidebar
	{basePath}
	{parents}
	{children}
	{aliases}
	{parentHeading}
	{childHeading}
	{aliasHeading}
/>
