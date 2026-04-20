<script lang="ts">
	import Layout from './+layout.svelte';

	let { data, childText = 'Child content' } = $props();
</script>

<Layout {data}>
	<p>{childText}</p>
</Layout>
