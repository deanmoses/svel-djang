<script lang="ts">
	import EntityProvenance from '$lib/components/EntityProvenance.svelte';

	let { data } = $props();
</script>

<EntityProvenance sources={data.title.sources} entityType="title" entitySlug={data.title.slug} />
