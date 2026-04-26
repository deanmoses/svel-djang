<script lang="ts">
  import ManufacturerCardGrid from '$lib/components/ManufacturerCardGrid.svelte';
  import type { components } from '$lib/api/schema';

  type LocationDetail = components['schemas']['LocationDetailSchema'];

  let { data } = $props();
  let profile = $derived<LocationDetail>(data.profile);
</script>

<ManufacturerCardGrid manufacturers={profile.manufacturers} showCount={false} />
