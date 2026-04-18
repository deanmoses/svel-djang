<script lang="ts">
	import ActionMenu from '$lib/components/ActionMenu.svelte';
	import MenuItem from '$lib/components/MenuItem.svelte';
	import type { EditSectionMenuItem } from './edit-section-menu';

	let {
		label = undefined,
		currentKey = undefined,
		disabled = false,
		variant = 'default',
		items
	}: {
		label?: string;
		currentKey?: string;
		disabled?: boolean;
		variant?: 'default' | 'heading';
		items: EditSectionMenuItem[];
	} = $props();

	let currentLabel = $derived(
		currentKey ? (items.find((item) => item.key === currentKey)?.label ?? 'Edit') : 'Edit'
	);
</script>

<ActionMenu label={label ?? currentLabel} {disabled} {variant}>
	{#each items as item (item.key)}
		<MenuItem
			href={item.href}
			onclick={item.onclick}
			disabled={item.key === currentKey}
			current={item.key === currentKey}
		>
			{item.label}
		</MenuItem>
	{/each}
</ActionMenu>
