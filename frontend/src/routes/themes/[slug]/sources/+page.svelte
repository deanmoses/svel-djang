<script lang="ts">
	import EntityProvenance from '$lib/components/EntityProvenance.svelte';

	let { data } = $props();
</script>

<EntityProvenance sources={data.theme.sources} entityType="theme" entitySlug={data.theme.slug} />
