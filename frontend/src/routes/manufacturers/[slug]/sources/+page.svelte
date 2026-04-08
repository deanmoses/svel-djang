<script lang="ts">
	import EntityProvenance from '$lib/components/EntityProvenance.svelte';

	let { data } = $props();
</script>

<EntityProvenance
	sources={data.manufacturer.sources}
	entityType="manufacturer"
	entitySlug={data.manufacturer.slug}
/>
