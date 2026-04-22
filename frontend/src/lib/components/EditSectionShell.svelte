<script lang="ts">
	import type { Snippet } from 'svelte';
	import EditSectionMenu from '$lib/components/EditSectionMenu.svelte';
	import FocusContentShell from '$lib/components/FocusContentShell.svelte';
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

<FocusContentShell backHref={detailHref}>
	{#snippet heading()}
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
	{/snippet}

	{@render children()}
</FocusContentShell>

<style>
	.fallback-heading {
		font-size: var(--font-size-3);
		font-weight: 600;
		margin: 0;
	}
</style>
