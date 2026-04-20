<script lang="ts">
	import EditRedirectFallback from '$lib/components/EditRedirectFallback.svelte';
	import { defaultSeriesSectionSegment } from '$lib/components/editors/series-edit-sections';
</script>

<EditRedirectFallback basePath="/series" defaultSegment={defaultSeriesSectionSegment()} />
