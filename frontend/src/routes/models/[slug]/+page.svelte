<script lang="ts">
	import ModelDetailBody from '$lib/components/ModelDetailBody.svelte';

	let { data } = $props();
	let model = $derived(data.model);
</script>

<ModelDetailBody {model} />
