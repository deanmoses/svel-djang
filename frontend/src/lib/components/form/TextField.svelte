<script lang="ts">
	import FieldGroup from './FieldGroup.svelte';

	let {
		label,
		value = $bindable(''),
		type = 'text',
		id = '',
		placeholder = '',
		optional = false
	}: {
		label: string;
		value?: string;
		type?: 'text' | 'url';
		id?: string;
		placeholder?: string;
		optional?: boolean;
	} = $props();
</script>

<FieldGroup {label} {id} {optional}>
	{#snippet children(inputId)}
		<input id={inputId} bind:value {type} {placeholder} />
	{/snippet}
</FieldGroup>
