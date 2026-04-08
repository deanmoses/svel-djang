<script lang="ts">
	import EntityProvenance from '$lib/components/EntityProvenance.svelte';

	let { data } = $props();
</script>

<EntityProvenance sources={data.profile.sources} entityType="tag" entitySlug={data.profile.slug} />
