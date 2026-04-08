<script lang="ts">
	import EntityProvenance from '$lib/components/EntityProvenance.svelte';

	let { data } = $props();
</script>

<EntityProvenance
	sources={data.franchise.sources}
	entityType="franchise"
	entitySlug={data.franchise.slug}
/>
