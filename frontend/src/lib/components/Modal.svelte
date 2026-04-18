<script lang="ts">
	import { tick } from 'svelte';
	import type { Snippet } from 'svelte';
	import { acquireScrollLock } from './scroll-lock';

	let {
		title,
		titleContent,
		open,
		onclose,
		headerActions,
		footer,
		children
	}: {
		title: string;
		titleContent?: Snippet;
		open: boolean;
		onclose: () => void;
		headerActions?: Snippet;
		footer?: Snippet;
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

	// Keyboard ownership and focus restoration still assume one active dialog,
	// but scroll locking is delegated to a shared reference-counted manager so
	// concurrent or switching modals can't leak the lock.
	// Capture the element that had focus when the modal opened, move focus
	// into the dialog, lock body scroll, and listen for Escape.
	// Focus is restored in cleanup so it works for every close path,
	// including parent-controlled closes.
	$effect(() => {
		if (!open) return;

		const opener = document.activeElement as HTMLElement | undefined;

		const releaseScrollLock = acquireScrollLock();

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
			releaseScrollLock();
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
				<div class="header-main">
					<h2 id={titleId}>
						{#if titleContent}
							{@render titleContent()}
						{:else}
							{title}
						{/if}
					</h2>
					{#if headerActions}
						<div class="header-actions">
							{@render headerActions()}
						</div>
					{/if}
				</div>
				<button
					type="button"
					class="close-btn"
					aria-label="Close"
					onclick={close}
					bind:this={closeButtonEl}>&times;</button
				>
			</header>

			<div class="modal-body" id={bodyId}>
				{@render children()}
			</div>

			{#if footer}
				<footer class="modal-footer">
					{@render footer()}
				</footer>
			{/if}
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
		overflow: hidden;
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
		gap: var(--size-3);
		padding: var(--size-3) var(--size-4);
		border-bottom: 1px solid var(--color-border-soft);
		flex-shrink: 0;
	}

	.header-main {
		display: flex;
		flex: 1;
		align-items: center;
		justify-content: space-between;
		gap: var(--size-3);
		min-width: 0;
	}

	.modal-header h2 {
		font-size: var(--font-size-3);
		font-weight: 600;
		margin: 0;
		color: var(--color-text-primary);
		min-width: 0;
	}

	.header-actions {
		flex-shrink: 0;
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
