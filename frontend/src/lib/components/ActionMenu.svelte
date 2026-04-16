<script lang="ts">
	import type { Snippet } from 'svelte';

	type Props = {
		label: string;
		disabled?: boolean;
		children: Snippet;
	};

	let { label, disabled = false, children }: Props = $props();

	let open = $state(false);
	let triggerEl: HTMLButtonElement | undefined = $state();
	let menuEl: HTMLDivElement | undefined = $state();
	let pendingFocusTarget: 'first' | 'last' | null = $state(null);
	const uid = $props.id();
	const menuId = `${uid}-menu`;

	function getMenuItems() {
		return Array.from(menuEl?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? []);
	}

	function focusMenuItem(index: number) {
		const items = getMenuItems();
		if (items.length === 0) return;

		const normalizedIndex = ((index % items.length) + items.length) % items.length;

		for (const [itemIndex, item] of items.entries()) {
			item.tabIndex = itemIndex === normalizedIndex ? 0 : -1;
		}

		items[normalizedIndex].focus();
	}

	function openMenu({ focus }: { focus?: 'first' | 'last' } = {}) {
		if (disabled) return;
		pendingFocusTarget = focus ?? null;
		open = true;
	}

	function closeMenu({ restoreFocus = false }: { restoreFocus?: boolean } = {}) {
		open = false;
		if (restoreFocus) triggerEl?.focus();
	}

	function toggleMenu() {
		if (disabled) return;
		if (open) {
			closeMenu();
			return;
		}

		openMenu();
	}

	function handleTriggerKeydown(event: KeyboardEvent) {
		if (event.key === 'ArrowDown') {
			event.preventDefault();
			if (!open) openMenu({ focus: 'first' });
			return;
		}

		if (event.key === 'ArrowUp') {
			event.preventDefault();
			if (!open) openMenu({ focus: 'last' });
			return;
		}

		if ((event.key === 'Enter' || event.key === ' ') && !open) {
			event.preventDefault();
			openMenu({ focus: 'first' });
			return;
		}

		if (event.key === 'Escape' && open) {
			event.preventDefault();
			closeMenu({ restoreFocus: true });
		}
	}

	function handleMenuKeydown(event: KeyboardEvent) {
		const items = getMenuItems();
		if (items.length === 0) return;

		const currentIndex = items.findIndex((item) => item === document.activeElement);

		switch (event.key) {
			case 'ArrowDown':
				event.preventDefault();
				focusMenuItem(currentIndex < 0 ? 0 : currentIndex + 1);
				break;
			case 'ArrowUp':
				event.preventDefault();
				focusMenuItem(currentIndex < 0 ? items.length - 1 : currentIndex - 1);
				break;
			case 'Home':
				event.preventDefault();
				focusMenuItem(0);
				break;
			case 'End':
				event.preventDefault();
				focusMenuItem(items.length - 1);
				break;
			case 'Escape':
				event.preventDefault();
				closeMenu({ restoreFocus: true });
				break;
			case 'Tab':
				closeMenu();
				break;
		}
	}

	function handleMenuClick(event: MouseEvent) {
		const target = event.target;
		if (!(target instanceof Element)) return;
		if (target.closest('[role="menuitem"]')) closeMenu();
	}

	$effect(() => {
		if (disabled && open) {
			closeMenu();
		}
	});

	$effect(() => {
		if (!open || pendingFocusTarget == null) return;

		const items = getMenuItems();
		for (const item of items) item.tabIndex = -1;

		if (pendingFocusTarget === 'last') {
			focusMenuItem(items.length - 1);
		} else {
			focusMenuItem(0);
		}

		pendingFocusTarget = null;
	});

	$effect(() => {
		if (!open) return;

		function isInsideMenu(target: EventTarget | null) {
			return target instanceof Node && (triggerEl?.contains(target) || menuEl?.contains(target));
		}

		function handleKeydown(event: KeyboardEvent) {
			if (event.key === 'Escape') {
				event.preventDefault();
				closeMenu({ restoreFocus: true });
			}
		}

		function handlePointerDown(event: PointerEvent) {
			if (isInsideMenu(event.target)) return;
			closeMenu();
		}

		function handleFocusIn(event: FocusEvent) {
			if (isInsideMenu(event.target)) return;
			closeMenu();
		}

		document.addEventListener('keydown', handleKeydown);
		document.addEventListener('pointerdown', handlePointerDown);
		document.addEventListener('focusin', handleFocusIn);

		return () => {
			document.removeEventListener('keydown', handleKeydown);
			document.removeEventListener('pointerdown', handlePointerDown);
			document.removeEventListener('focusin', handleFocusIn);
		};
	});
</script>

<div class="action-menu">
	<button
		bind:this={triggerEl}
		type="button"
		class="trigger"
		{disabled}
		aria-haspopup="menu"
		aria-expanded={open}
		aria-controls={open ? menuId : undefined}
		onclick={toggleMenu}
		onkeydown={handleTriggerKeydown}
	>
		{label}
	</button>
	{#if open}
		<div
			bind:this={menuEl}
			id={menuId}
			class="menu"
			role="menu"
			tabindex="-1"
			aria-label={label}
			onkeydown={handleMenuKeydown}
			onclick={handleMenuClick}
		>
			{@render children()}
		</div>
	{/if}
</div>

<style>
	.action-menu {
		position: relative;
	}

	.trigger {
		color: var(--color-text-muted);
		cursor: pointer;
		background: none;
		border: none;
		padding: 0;
		margin: 0;
		font-size: var(--font-size-0);
		font-family: inherit;
	}

	.trigger::after {
		content: ' \25BE';
		font-size: 0.75em;
	}

	.trigger:hover,
	.trigger[aria-expanded='true'] {
		color: var(--color-accent);
	}

	.trigger:disabled {
		cursor: not-allowed;
		opacity: 0.5;
	}

	.trigger:disabled::after {
		opacity: 0.75;
	}

	.trigger:focus-visible {
		outline: 2px solid var(--color-accent);
		outline-offset: 2px;
	}

	.menu {
		position: absolute;
		right: 0;
		top: calc(100% + 4px);
		background: var(--color-background);
		border: 1px solid var(--color-border-soft);
		border-radius: var(--radius-2);
		padding: var(--size-1) 0;
		min-width: 7rem;
		z-index: 10;
		box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
	}
</style>
