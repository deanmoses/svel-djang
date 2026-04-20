<script lang="ts">
	import { afterNavigate } from '$app/navigation';
	import { onMount } from 'svelte';
	import { SvelteMap } from 'svelte/reactivity';
	import { toast, type ToastMessage } from './toast.svelte';
	import { resolveHref } from '$lib/utils';

	// Timeout handles keyed by toast id. SvelteMap satisfies the
	// svelte/prefer-svelte-reactivity lint; we don't actually need
	// reactivity here since only $effect reads it.
	const timers = new SvelteMap<string, ReturnType<typeof setTimeout>>();

	function clearTimer(id: string) {
		const t = timers.get(id);
		if (t != null) {
			clearTimeout(t);
			timers.delete(id);
		}
	}

	function startTimer(msg: ToastMessage) {
		clearTimer(msg.id);
		if (!Number.isFinite(msg.dwellMs)) return;
		const handle = setTimeout(() => {
			toast.dismiss(msg.id);
			timers.delete(msg.id);
		}, msg.dwellMs);
		timers.set(msg.id, handle);
	}

	// Start / clear timers as messages appear and disappear.
	$effect(() => {
		const current = toast.messages;
		const seen = new Set<string>(current.map((m) => m.id));
		for (const msg of current) {
			if (!timers.has(msg.id)) startTimer(msg);
		}
		// Clean up timers for messages that have been dismissed.
		for (const id of timers.keys()) {
			if (!seen.has(id)) clearTimer(id);
		}
	});

	onMount(() => {
		return () => {
			for (const t of timers.values()) clearTimeout(t);
			timers.clear();
		};
	});

	afterNavigate(() => {
		toast.onNavigation();
	});

	async function handleAction(msg: ToastMessage) {
		if (!msg.action) return;
		// The action handler typically calls handle.update(...) to replace
		// the text (e.g. "Restored X"). If it doesn't, the dwellMs timer
		// dismisses the toast naturally.
		await msg.action.onAction();
	}
</script>

<!-- Assertive region for errors, polite for everything else. -->
<div class="toast-host" aria-live="polite" aria-atomic="false">
	{#each toast.messages as msg (msg.id)}
		<div class="toast toast--{msg.variant}" role={msg.variant === 'error' ? 'alert' : 'status'}>
			{#if msg.href}
				<a class="text" href={resolveHref(msg.href)}>{msg.text}</a>
			{:else}
				<span class="text">{msg.text}</span>
			{/if}
			{#if msg.action}
				<button
					type="button"
					class="action"
					onclick={() => handleAction(msg)}
					aria-label={msg.action.label}
				>
					{msg.action.label}
				</button>
			{/if}
			<button
				type="button"
				class="close"
				onclick={() => toast.dismiss(msg.id)}
				aria-label="Dismiss"
			>
				×
			</button>
		</div>
	{/each}
</div>

<style>
	.toast-host {
		position: fixed;
		bottom: var(--size-5);
		left: 50%;
		transform: translateX(-50%);
		display: flex;
		flex-direction: column;
		gap: var(--size-2);
		z-index: 1000;
		pointer-events: none;
	}

	.toast {
		pointer-events: auto;
		display: flex;
		align-items: center;
		gap: var(--size-3);
		background: var(--color-surface-elevated, #222);
		color: var(--color-text-primary-inverse, #fff);
		padding: var(--size-2) var(--size-4);
		border-radius: var(--size-2);
		box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
		max-width: 28rem;
	}

	.toast--error {
		background: var(--color-error, #b00020);
	}

	.text {
		flex: 1;
		font-size: var(--font-size-0);
		color: inherit;
	}

	a.text {
		text-decoration: underline;
	}

	.action {
		background: none;
		border: none;
		color: inherit;
		font-size: var(--font-size-0);
		font-weight: 600;
		text-transform: uppercase;
		letter-spacing: 0.05em;
		cursor: pointer;
		padding: var(--size-1) var(--size-2);
	}

	.action:hover {
		text-decoration: underline;
	}

	.action:focus-visible,
	.close:focus-visible {
		outline: 2px solid var(--color-accent, #ffb300);
		outline-offset: 2px;
	}

	.close {
		background: none;
		border: none;
		color: inherit;
		font-size: var(--font-size-2);
		cursor: pointer;
		padding: 0 var(--size-2);
		line-height: 1;
	}
</style>
