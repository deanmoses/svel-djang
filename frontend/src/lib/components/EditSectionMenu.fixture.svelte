<script lang="ts">
	import EditSectionMenu from './EditSectionMenu.svelte';
</script>

<EditSectionMenu
	items={[
		{ key: 'overview', label: 'Overview', href: '/models/medieval-madness/edit/overview' },
		{
			key: 'specifications',
			label: 'Specifications',
			href: '/models/medieval-madness/edit/specifications'
		},
		{
			key: 'relationships',
			label: 'Relationships',
			href: '/models/medieval-madness/edit/relationships'
		}
	]}
/>
