<script lang="ts">
	import EntityProvenance from '$lib/components/EntityProvenance.svelte';

	let { data } = $props();
</script>

<EntityProvenance
	sources={data.profile.sources}
	entityType="reward-type"
	entitySlug={data.profile.slug}
/>
