<script lang="ts">
	import CreditsList from '$lib/components/CreditsList.svelte';
	import type { components } from '$lib/api/schema';

	type Model = components['schemas']['MachineModelDetailSchema'];

	let { model }: { model: Model } = $props();
</script>

<CreditsList credits={model.credits} />
