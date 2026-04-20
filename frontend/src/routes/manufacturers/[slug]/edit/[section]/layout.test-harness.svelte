<script lang="ts">
	import Layout from './+layout.svelte';

	let { childText = 'Child content' } = $props();
</script>

<Layout>
	<p>{childText}</p>
</Layout>
