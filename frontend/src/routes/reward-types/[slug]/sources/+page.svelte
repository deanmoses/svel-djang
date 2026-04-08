<script lang="ts">
	import EntityProvenance from '$lib/components/EntityProvenance.svelte';

	let { data } = $props();
</script>

<EntityProvenance
	sources={data.profile.sources}
	entityType="rewardtype"
	entitySlug={data.profile.slug}
/>
