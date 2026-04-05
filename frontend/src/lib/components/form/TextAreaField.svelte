<script lang="ts">
	import FieldGroup from './FieldGroup.svelte';

	let {
		label,
		value = $bindable(''),
		id = '',
		rows = 4
	}: {
		label: string;
		value?: string;
		id?: string;
		rows?: number;
	} = $props();
</script>

<FieldGroup {label} {id}>
	{#snippet children(inputId)}
		<textarea id={inputId} {rows} bind:value></textarea>
	{/snippet}
</FieldGroup>
