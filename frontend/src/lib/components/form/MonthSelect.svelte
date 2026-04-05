<script lang="ts">
	import FieldGroup from './FieldGroup.svelte';

	let {
		label,
		value = $bindable(''),
		id = ''
	}: {
		label: string;
		value?: string | number;
		id?: string;
	} = $props();

	const months = [
		'January',
		'February',
		'March',
		'April',
		'May',
		'June',
		'July',
		'August',
		'September',
		'October',
		'November',
		'December'
	];
</script>

<FieldGroup {label} {id}>
	{#snippet children(inputId)}
		<select id={inputId} bind:value>
			<option value="">—</option>
			{#each months as name, i (i)}
				<option value={i + 1}>{name}</option>
			{/each}
		</select>
	{/snippet}
</FieldGroup>

<style>
	select {
		width: 100%;
	}
</style>
