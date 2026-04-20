<script lang="ts">
	import type { Snippet } from 'svelte';
	import EditSectionMenu from '$lib/components/EditSectionMenu.svelte';
	import type { EditSectionMenuItem } from '$lib/components/edit-section-menu';

	let {
		detailHref,
		switcherItems,
		currentSectionKey = undefined,
		editorDirty = false,
		fallbackHeading = 'Edit',
		children
	}: {
		detailHref: string;
		switcherItems: EditSectionMenuItem[];
		currentSectionKey?: string;
		editorDirty?: boolean;
		fallbackHeading?: string;
		children: Snippet;
	} = $props();
</script>

<div class="edit-shell">
	<header class="edit-header">
		<a href={detailHref} class="back-link">&larr; Back</a>
		<div class="heading-slot" aria-label={currentSectionKey ? undefined : fallbackHeading}>
			{#if currentSectionKey}
				<EditSectionMenu
					items={switcherItems}
					currentKey={currentSectionKey}
					disabled={editorDirty}
					variant="heading"
				/>
			{:else}
				<h1 class="fallback-heading">{fallbackHeading}</h1>
			{/if}
		</div>
	</header>

	{@render children()}
</div>

<style>
	.edit-shell {
		max-width: 48rem;
		margin: 0 auto;
		padding: var(--size-4);
	}

	.edit-header {
		position: relative;
		display: flex;
		align-items: center;
		justify-content: center;
		margin-bottom: var(--size-4);
		min-height: 2.5rem;
	}

	.back-link {
		position: absolute;
		left: 0;
		font-size: var(--font-size-1);
		color: var(--color-text-muted);
		text-decoration: none;
	}

	.back-link:hover {
		color: var(--color-text-primary);
	}

	.fallback-heading {
		font-size: var(--font-size-3);
		font-weight: 600;
		margin: 0;
	}
</style>
