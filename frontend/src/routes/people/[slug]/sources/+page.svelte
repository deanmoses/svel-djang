<script lang="ts">
	import EntityProvenance from '$lib/components/EntityProvenance.svelte';

	let { data } = $props();
</script>

<EntityProvenance sources={data.person.sources} entityType="person" entitySlug={data.person.slug} />
