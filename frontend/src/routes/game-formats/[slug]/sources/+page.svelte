<script lang="ts">
	import EntityProvenance from '$lib/components/EntityProvenance.svelte';

	let { data } = $props();
</script>

<EntityProvenance
	sources={data.profile.sources}
	entityType="game-format"
	entitySlug={data.profile.slug}
/>
