<script lang="ts">
	import { tick } from 'svelte';
	import type { Snippet } from 'svelte';

	let {
		heading,
		open,
		error = '',
		onclose,
		onsave,
		children
	}: {
		heading: string;
		open: boolean;
		error?: string;
		onclose: () => void;
		onsave: () => void;
		children: Snippet;
	} = $props();

	const FOCUSABLE_SELECTOR = [
		'a[href]',
		'button:not([disabled])',
		'input:not([disabled])',
		'select:not([disabled])',
		'textarea:not([disabled])',
		'[tabindex]:not([tabindex="-1"])'
	].join(', ');

	let dialogEl: HTMLDivElement | undefined = $state();
	let closeButtonEl: HTMLButtonElement | undefined = $state();
	const uid = $props.id();
	const titleId = `${uid}-title`;
	const bodyId = `${uid}-body`;

	function close() {
		onclose();
	}

	function getFocusableElements() {
		if (!dialogEl) return [];
		return Array.from(dialogEl.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
			(element) => !element.hasAttribute('hidden') && element.getAttribute('aria-hidden') !== 'true'
		);
	}

	// Capture the element that had focus when the modal opened, move focus
	// into the dialog, lock body scroll, and listen for Escape.
	// Focus is restored in cleanup so it works for every close path
	// (Cancel, Escape, backdrop click, and Save).
	$effect(() => {
		if (!open) return;

		const opener = document.activeElement as HTMLElement | undefined;

		const prev = document.body.style.overflow;
		document.body.style.overflow = 'hidden';

		let cancelled = false;
		void tick().then(() => {
			if (cancelled) return;
			if (closeButtonEl) closeButtonEl.focus();
			else dialogEl?.focus();
		});

		function handleKeydown(e: KeyboardEvent) {
			if (e.key === 'Escape') {
				e.preventDefault();
				close();
				return;
			}

			if (e.key !== 'Tab') return;

			const focusableElements = getFocusableElements();
			if (focusableElements.length === 0) {
				e.preventDefault();
				dialogEl?.focus();
				return;
			}

			const firstElement = focusableElements[0];
			const lastElement = focusableElements[focusableElements.length - 1];
			const activeElement = document.activeElement;

			if (e.shiftKey && activeElement === firstElement) {
				e.preventDefault();
				lastElement.focus();
			} else if (!e.shiftKey && activeElement === lastElement) {
				e.preventDefault();
				firstElement.focus();
			}
		}
		document.addEventListener('keydown', handleKeydown);

		return () => {
			cancelled = true;
			document.body.style.overflow = prev;
			document.removeEventListener('keydown', handleKeydown);
			if (opener?.isConnected) {
				opener.focus();
			}
		};
	});
</script>

{#if open}
	<div class="modal-backdrop">
		<button type="button" class="backdrop-dismiss" tabindex="-1" aria-hidden="true" onclick={close}
		></button>

		<div
			class="modal-dialog"
			role="dialog"
			aria-modal="true"
			aria-labelledby={titleId}
			aria-describedby={bodyId}
			tabindex="-1"
			bind:this={dialogEl}
		>
			<header class="modal-header">
				<h2 id={titleId}>Edit {heading}</h2>
				<button
					type="button"
					class="close-btn"
					aria-label="Close"
					onclick={close}
					bind:this={closeButtonEl}>&times;</button
				>
			</header>

			<div class="modal-body" id={bodyId}>
				{#if error}
					<p class="save-error">{error}</p>
				{/if}
				{@render children()}
			</div>

			<footer class="modal-footer">
				<button type="button" class="btn-cancel" onclick={close}>Cancel</button>
				<button type="button" class="btn-save" onclick={onsave}>Save</button>
			</footer>
		</div>
	</div>
{/if}

<style>
	.modal-backdrop {
		position: fixed;
		inset: 0;
		z-index: 1000;
		background: rgba(0, 0, 0, 0.5);
		display: flex;
		align-items: center;
		justify-content: center;
		padding: var(--size-4);
	}

	.modal-dialog {
		position: relative;
		z-index: 1;
		width: 100%;
		max-width: 48rem;
		max-height: calc(100vh - var(--size-6) * 2);
		background: var(--color-background);
		border: 1px solid var(--color-border);
		border-radius: var(--radius-3);
		display: flex;
		flex-direction: column;
		box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
	}

	.backdrop-dismiss {
		position: absolute;
		inset: 0;
		border: 0;
		padding: 0;
		background: transparent;
		cursor: pointer;
	}

	.modal-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: var(--size-3) var(--size-4);
		border-bottom: 1px solid var(--color-border-soft);
		flex-shrink: 0;
	}

	.modal-header h2 {
		font-size: var(--font-size-3);
		font-weight: 600;
		margin: 0;
		color: var(--color-text-primary);
	}

	.close-btn {
		background: none;
		border: none;
		color: var(--color-text-muted);
		font-size: 1.5rem;
		cursor: pointer;
		padding: var(--size-1);
		line-height: 1;
	}

	.close-btn:hover {
		color: var(--color-text-primary);
	}

	.modal-body {
		flex: 1;
		overflow-y: auto;
		padding: var(--size-4);
	}

	.modal-footer {
		display: flex;
		align-items: center;
		justify-content: flex-end;
		gap: var(--size-2);
		padding: var(--size-3) var(--size-4);
		border-top: 1px solid var(--color-border-soft);
		flex-shrink: 0;
	}

	.btn-cancel {
		background: none;
		border: 1px solid var(--color-border);
		border-radius: var(--radius-2);
		padding: var(--size-1) var(--size-3);
		font-size: var(--font-size-1);
		color: var(--color-text-muted);
		cursor: pointer;
	}

	.btn-cancel:hover {
		color: var(--color-text-primary);
		border-color: var(--color-text-muted);
	}

	.btn-save {
		background: var(--color-accent);
		color: #fff;
		border: none;
		border-radius: var(--radius-2);
		padding: var(--size-1) var(--size-3);
		font-size: var(--font-size-1);
		font-weight: 600;
		cursor: pointer;
	}

	.btn-save:hover {
		opacity: 0.9;
	}

	.save-error {
		color: var(--color-error, #d32f2f);
		font-size: var(--font-size-1);
		margin: 0 0 var(--size-3);
	}

	/* Mobile: full-screen modal */
	@media (max-width: 40rem) {
		.modal-backdrop {
			padding: 0;
		}

		.modal-dialog {
			max-width: none;
			max-height: none;
			height: 100%;
			border-radius: 0;
			border: none;
		}
	}
</style>
