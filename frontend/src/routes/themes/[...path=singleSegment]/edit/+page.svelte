<script lang="ts">
  import { page } from '$app/state';
  import EditRedirectFallback from '$lib/components/EditRedirectFallback.svelte';
  import { defaultHierarchicalTaxonomySectionSegment } from '$lib/components/editors/hierarchical-taxonomy-edit-sections';
</script>

<EditRedirectFallback
  basePath="/themes"
  path={page.params.path}
  defaultSegment={defaultHierarchicalTaxonomySectionSegment()}
/>
