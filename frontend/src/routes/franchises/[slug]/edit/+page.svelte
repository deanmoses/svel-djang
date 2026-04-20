<script lang="ts">
	import EditRedirectFallback from '$lib/components/EditRedirectFallback.svelte';
	import { defaultFranchiseSectionSegment } from '$lib/components/editors/franchise-edit-sections';
</script>

<EditRedirectFallback basePath="/franchises" defaultSegment={defaultFranchiseSectionSegment()} />
