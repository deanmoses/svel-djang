<script lang="ts">
	import EntityProvenance from '$lib/components/EntityProvenance.svelte';

	let { data } = $props();
</script>

<EntityProvenance
	sources={data.corporateEntity.sources}
	entityType="corporate-entity"
	entitySlug={data.corporateEntity.slug}
/>
