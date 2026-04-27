<script lang="ts">
  import SimpleTaxonomyDetailLayout from '$lib/components/SimpleTaxonomyDetailLayout.svelte';

  let { data, children } = $props();
  let profile = $derived(data.profile);
</script>

<SimpleTaxonomyDetailLayout
  {profile}
  parentLabel="Cabinets"
  basePath="/cabinets"
  claimsPath={'/api/cabinets/{public_id}/claims/'}
  deleteHref={`/cabinets/${profile.slug}/delete`}
>
  {@render children()}
</SimpleTaxonomyDetailLayout>
