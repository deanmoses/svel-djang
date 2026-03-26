<script lang="ts">
	import type { Snippet } from 'svelte';

	let {
		label,
		id = '',
		optional = false,
		children
	}: {
		label: string;
		id?: string;
		optional?: boolean;
		children: Snippet<[string]>;
	} = $props();

	let inputId = $derived(id || `ef-${label.toLowerCase().replace(/\s+/g, '-')}`);
</script>

<div class="field-group">
	<label for={inputId}
		>{label}
		{#if optional}<span class="optional">(optional)</span>{/if}</label
	>
	{@render children(inputId)}
</div>

<style>
	.field-group {
		display: flex;
		flex-direction: column;
		gap: var(--size-1);
	}

	label {
		font-size: var(--font-size-1);
		font-weight: 500;
		color: var(--color-text-muted);
	}

	.optional {
		font-weight: 400;
		font-size: var(--font-size-0);
	}
</style>
