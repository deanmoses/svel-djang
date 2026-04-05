<script lang="ts">
	import { normalizeText } from '$lib/utils';

	let {
		options,
		selected = $bindable(null),
		multi = false,
		allowZeroCount = false,
		placeholder = 'Search...',
		label = ''
	}: {
		options: { slug: string; label: string; count: number }[];
		selected?: string | string[] | null;
		multi?: boolean;
		allowZeroCount?: boolean;
		placeholder?: string;
		label?: string;
	} = $props();

	function isDisabled(opt: { count: number }): boolean {
		return !allowZeroCount && opt.count === 0;
	}

	let query = $state('');
	let open = $state(false);
	let activeIndex = $state(-1);
	let inputEl: HTMLInputElement | undefined = $state();
	let listEl: HTMLUListElement | undefined = $state();

	let filteredOptions = $derived.by(() => {
		const q = normalizeText(query.trim());
		let opts = options;
		if (q) {
			opts = opts.filter((o) => normalizeText(o.label).includes(q));
		}
		// Sort: non-zero counts first (desc), then zero-count; within each group alphabetical
		return opts.slice().sort((a, b) => {
			if (a.count === 0 && b.count !== 0) return 1;
			if (a.count !== 0 && b.count === 0) return -1;
			if (a.count !== b.count) return b.count - a.count;
			return a.label.localeCompare(b.label);
		});
	});

	function isSelected(slug: string): boolean {
		if (multi && Array.isArray(selected)) {
			return selected.includes(slug);
		}
		return selected === slug;
	}

	function toggle(slug: string) {
		if (multi) {
			const arr = Array.isArray(selected) ? selected : [];
			if (arr.includes(slug)) {
				selected = arr.filter((s) => s !== slug);
			} else {
				selected = [...arr, slug];
			}
		} else {
			selected = selected === slug ? null : slug;
			open = false;
			query = '';
		}
	}

	function selectedLabel(): string {
		if (multi) {
			const arr = Array.isArray(selected) ? selected : [];
			if (arr.length === 1) {
				const opt = options.find((o) => o.slug === arr[0]);
				return opt?.label ?? '';
			}
			if (arr.length > 1) return `${arr.length} selected`;
			return '';
		}
		if (typeof selected === 'string') {
			const opt = options.find((o) => o.slug === selected);
			return opt?.label ?? '';
		}
		return '';
	}

	function handleKeydown(e: KeyboardEvent) {
		if (!open) {
			if (e.key === 'ArrowDown' || e.key === 'Enter') {
				open = true;
				activeIndex = 0;
				e.preventDefault();
			}
			return;
		}

		switch (e.key) {
			case 'ArrowDown':
				e.preventDefault();
				activeIndex = Math.min(activeIndex + 1, filteredOptions.length - 1);
				scrollActiveIntoView();
				break;
			case 'ArrowUp':
				e.preventDefault();
				activeIndex = Math.max(activeIndex - 1, 0);
				scrollActiveIntoView();
				break;
			case 'Enter':
				e.preventDefault();
				if (activeIndex >= 0 && activeIndex < filteredOptions.length) {
					const opt = filteredOptions[activeIndex];
					if (!isDisabled(opt)) toggle(opt.slug);
				}
				break;
			case 'Escape':
				e.preventDefault();
				open = false;
				query = '';
				inputEl?.blur();
				break;
		}
	}

	function scrollActiveIntoView() {
		requestAnimationFrame(() => {
			const active = listEl?.querySelector('[data-active="true"]');
			active?.scrollIntoView({ block: 'nearest' });
		});
	}

	function handleFocus() {
		open = true;
		activeIndex = -1;
	}

	// Reset activeIndex when filtered options change
	$effect(() => {
		void filteredOptions;
		activeIndex = -1;
	});

	// Click outside to close
	$effect(() => {
		if (!open) return;
		function onPointerDown(e: PointerEvent) {
			const target = e.target as Node;
			if (!inputEl?.closest('.searchable-select')?.contains(target)) {
				open = false;
				query = '';
			}
		}
		document.addEventListener('pointerdown', onPointerDown);
		return () => document.removeEventListener('pointerdown', onPointerDown);
	});

	const listboxId = `listbox-${Math.random().toString(36).slice(2, 8)}`;
</script>

<div class="searchable-select">
	{#if label}
		<span class="filter-label">{label}</span>
	{/if}

	<div class="input-wrap">
		<input
			bind:this={inputEl}
			type="text"
			role="combobox"
			aria-expanded={open}
			aria-controls={listboxId}
			aria-activedescendant={activeIndex >= 0 ? `${listboxId}-${activeIndex}` : undefined}
			{placeholder}
			value={open ? query : selectedLabel() || ''}
			oninput={(e) => {
				query = e.currentTarget.value;
				if (!open) open = true;
			}}
			onfocus={handleFocus}
			onkeydown={handleKeydown}
		/>
		{#if !multi && selected}
			<button
				class="clear-btn"
				aria-label="Clear selection"
				onclick={(e) => {
					e.stopPropagation();
					selected = null;
					query = '';
				}}
			>
				×
			</button>
		{/if}
	</div>

	{#if multi && Array.isArray(selected) && selected.length > 0}
		<div class="selected-tags">
			{#each selected as slug (slug)}
				{@const opt = options.find((o) => o.slug === slug)}
				{#if opt}
					<span class="tag">
						{opt.label}
						<button
							class="tag-remove"
							aria-label={`Remove ${opt.label}`}
							onclick={() => toggle(slug)}
						>
							×
						</button>
					</span>
				{/if}
			{/each}
		</div>
	{/if}

	{#if open}
		<ul bind:this={listEl} id={listboxId} role="listbox" class="dropdown">
			{#each filteredOptions as opt, i (opt.slug)}
				<li
					id={`${listboxId}-${i}`}
					role="option"
					aria-selected={isSelected(opt.slug)}
					aria-disabled={isDisabled(opt)}
					data-active={i === activeIndex}
					class="option"
					class:selected={isSelected(opt.slug)}
					class:disabled={isDisabled(opt)}
					class:active={i === activeIndex}
					onpointerdown={(e) => {
						e.preventDefault();
						if (!isDisabled(opt)) toggle(opt.slug);
					}}
				>
					{#if multi}
						<span class="check">{isSelected(opt.slug) ? '✓' : ''}</span>
					{/if}
					<span class="option-label">{opt.label}</span>
					<span class="option-count">({opt.count})</span>
				</li>
			{:else}
				<li class="no-results">No matches</li>
			{/each}
		</ul>
	{/if}
</div>

<style>
	.searchable-select {
		position: relative;
	}

	.filter-label {
		display: block;
		font-size: var(--font-size-0);
		color: var(--color-text-muted);
		margin-bottom: var(--size-1);
	}

	.input-wrap {
		position: relative;
	}

	input {
		transition:
			border-color 0.15s var(--ease-2),
			box-shadow 0.15s var(--ease-2);
	}

	.clear-btn {
		position: absolute;
		right: var(--size-2);
		top: 50%;
		transform: translateY(-50%);
		background: none;
		border: none;
		color: var(--color-text-muted);
		cursor: pointer;
		font-size: var(--font-size-2);
		padding: 0 var(--size-1);
		line-height: 1;
	}

	.clear-btn:hover {
		color: var(--color-text-primary);
	}

	.selected-tags {
		display: flex;
		flex-wrap: wrap;
		gap: var(--size-1);
		margin-top: var(--size-1);
	}

	.tag {
		display: inline-flex;
		align-items: center;
		gap: var(--size-1);
		padding: var(--size-1) var(--size-2);
		font-size: var(--font-size-0);
		background-color: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: var(--radius-2);
	}

	.tag-remove {
		background: none;
		border: none;
		color: var(--color-text-muted);
		cursor: pointer;
		padding: 0;
		font-size: var(--font-size-1);
		line-height: 1;
	}

	.tag-remove:hover {
		color: var(--color-error);
	}

	.dropdown {
		position: absolute;
		z-index: 10;
		top: 100%;
		left: 0;
		right: 0;
		margin-top: var(--size-1);
		max-height: 18rem;
		overflow-y: auto;
		background-color: var(--color-surface);
		border: 1px solid var(--color-border);
		border-radius: var(--radius-2);
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
		list-style: none;
		padding: var(--size-1) 0;
	}

	.option {
		display: flex;
		align-items: center;
		gap: var(--size-2);
		padding: var(--size-2) var(--size-3);
		cursor: pointer;
		font-size: var(--font-size-1);
	}

	.option:hover,
	.option.active {
		background-color: var(--color-input-focus-ring);
	}

	.option.selected {
		font-weight: 600;
	}

	.option.disabled {
		color: var(--color-text-muted);
		opacity: 0.5;
		cursor: default;
	}

	.option.disabled:hover {
		background-color: transparent;
	}

	.check {
		width: 1rem;
		text-align: center;
		flex-shrink: 0;
	}

	.option-label {
		flex: 1;
		min-width: 0;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.option-count {
		color: var(--color-text-muted);
		font-size: var(--font-size-0);
		flex-shrink: 0;
	}

	.no-results {
		padding: var(--size-3);
		color: var(--color-text-muted);
		text-align: center;
		font-size: var(--font-size-1);
	}
</style>
