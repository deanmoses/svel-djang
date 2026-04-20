<script lang="ts">
	import EditRedirectFallback from '$lib/components/EditRedirectFallback.svelte';
	import { defaultManufacturerSectionSegment } from '$lib/components/editors/manufacturer-edit-sections';
</script>

<EditRedirectFallback
	basePath="/manufacturers"
	defaultSegment={defaultManufacturerSectionSegment()}
/>
