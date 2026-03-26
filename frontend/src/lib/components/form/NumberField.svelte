<script lang="ts">
	import FieldGroup from './FieldGroup.svelte';

	let {
		label,
		value = $bindable(''),
		id = '',
		min,
		max,
		step = 1
	}: {
		label: string;
		value?: string | number;
		id?: string;
		min?: number;
		max?: number;
		step?: number;
	} = $props();
</script>

<FieldGroup {label} {id}>
	{#snippet children(inputId)}
		<input id={inputId} type="number" {min} {max} {step} bind:value />
	{/snippet}
</FieldGroup>
