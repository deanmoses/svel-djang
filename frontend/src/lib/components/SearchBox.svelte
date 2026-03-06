<script lang="ts">
	import { faMagnifyingGlass } from '@fortawesome/free-solid-svg-icons';
	import FaIcon from './FaIcon.svelte';

	let {
		value = $bindable(''),
		placeholder = 'Search...',
		disabled = false,
		autofocus = false
	}: {
		value?: string;
		placeholder?: string;
		disabled?: boolean;
		autofocus?: boolean;
	} = $props();
</script>

<form class="search-box" onsubmit={(e) => e.preventDefault()}>
	<FaIcon icon={faMagnifyingGlass} />
	<!-- svelte-ignore a11y_autofocus -->
	<input type="search" {placeholder} aria-label={placeholder} bind:value {disabled} {autofocus} />
</form>

<style>
	.search-box {
		position: relative;
		max-width: 36rem;
		margin: 0 auto var(--size-4);
	}

	.search-box :global(svg) {
		position: absolute;
		left: var(--size-4);
		top: 50%;
		transform: translateY(-50%);
		width: 1rem;
		height: 1rem;
		color: var(--color-text-muted);
		pointer-events: none;
	}

	input[type='search'] {
		width: 100%;
		padding: var(--size-3) var(--size-4) var(--size-3) var(--size-9);
		font-size: var(--font-size-2);
		font-family: var(--font-body);
		background-color: var(--color-input-bg);
		color: var(--color-text-primary);
		border: 1px solid var(--color-input-border);
		border-radius: var(--radius-3);
		transition:
			border-color 0.15s var(--ease-2),
			box-shadow 0.15s var(--ease-2);
	}

	input[type='search']:focus {
		outline: none;
		border-color: var(--color-input-focus);
		box-shadow: 0 0 0 3px var(--color-input-focus-ring);
	}

	input[type='search']::placeholder {
		color: var(--color-text-muted);
	}
</style>
