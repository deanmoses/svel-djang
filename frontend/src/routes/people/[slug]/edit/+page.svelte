<script lang="ts">
	import EditRedirectFallback from '$lib/components/EditRedirectFallback.svelte';
	import { defaultPersonSectionSegment } from '$lib/components/editors/person-edit-sections';
</script>

<EditRedirectFallback basePath="/people" defaultSegment={defaultPersonSectionSegment()} />
