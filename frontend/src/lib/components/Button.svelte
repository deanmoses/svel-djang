<script lang="ts">
	import type { Snippet } from 'svelte';
	let {
		children,
		tag = 'button',
		variant = 'primary',
		...rest
	}: {
		children: Snippet;
		tag?: string;
		variant?: 'primary' | 'secondary';
		[key: string]: unknown;
	} = $props();
</script>

<svelte:element this={tag} class="btn btn-{variant}" {...rest}>{@render children()}</svelte:element>

<style>
	.btn {
		display: inline-block;
		padding: var(--size-2) var(--size-4);
		border-radius: var(--radius-2);
		font-size: var(--font-size-1);
		text-decoration: none;
		cursor: pointer;
		transition: opacity 0.15s ease;
	}

	.btn:disabled {
		opacity: 0.6;
		cursor: not-allowed;
	}

	.btn-primary {
		background: var(--color-accent);
		color: #fff;
		border: none;
	}

	.btn-primary:hover:not(:disabled) {
		opacity: 0.9;
	}

	.btn-secondary {
		background: none;
		border: 1px solid var(--color-border);
		color: var(--color-text-muted);
	}

	.btn-secondary:hover:not(:disabled) {
		color: var(--color-text-primary);
		border-color: var(--color-text-muted);
	}
</style>
