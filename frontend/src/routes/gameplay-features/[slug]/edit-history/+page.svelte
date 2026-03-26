<script lang="ts">
	import EditHistory from '$lib/components/EditHistory.svelte';

	let { data } = $props();
</script>

<EditHistory changesets={data.changesets} />
