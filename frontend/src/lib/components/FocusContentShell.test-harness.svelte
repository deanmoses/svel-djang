<script lang="ts">
	import FocusContentShell from './FocusContentShell.svelte';

	let {
		backHref = '/titles/medieval-madness',
		maxWidth = undefined
	}: {
		backHref?: string;
		maxWidth?: string;
	} = $props();
</script>

{#snippet headingSnippet()}
	<h1>Edit History</h1>
{/snippet}

<FocusContentShell {backHref} {maxWidth} heading={headingSnippet}>
	<div>Audit content</div>
</FocusContentShell>
