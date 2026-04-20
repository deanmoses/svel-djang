<script lang="ts">
	import EditRedirectFallback from '$lib/components/EditRedirectFallback.svelte';
	import { defaultSimpleTaxonomySectionSegment } from '$lib/components/editors/simple-taxonomy-edit-sections';
</script>

<EditRedirectFallback basePath="/cabinets" defaultSegment={defaultSimpleTaxonomySectionSegment()} />
