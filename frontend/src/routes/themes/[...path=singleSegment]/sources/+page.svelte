<script lang="ts">
  import EntitySources from '$lib/components/EntitySources.svelte';

  let { data } = $props();
</script>

<EntitySources sources={data.sources} evidence={data.evidence} />
