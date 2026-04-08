<script lang="ts">
	import EntityProvenance from '$lib/components/EntityProvenance.svelte';

	let { data } = $props();
</script>

<EntityProvenance sources={data.model.sources} entityType="model" entitySlug={data.model.slug} />
