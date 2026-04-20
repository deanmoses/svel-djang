<script lang="ts">
	import EditRedirectFallback from '$lib/components/EditRedirectFallback.svelte';
	import { defaultSystemSectionSegment } from '$lib/components/editors/system-edit-sections';
</script>

<EditRedirectFallback basePath="/systems" defaultSegment={defaultSystemSectionSegment()} />
