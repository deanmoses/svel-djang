<script lang="ts">
	import type { Snippet } from 'svelte';
	import type { SaveMeta } from '$lib/components/editors/save-model-claims';
	import EditSectionMenu from '$lib/components/EditSectionMenu.svelte';
	import type { EditSectionMenuItem } from '$lib/components/edit-section-menu';
	import Modal from '$lib/components/Modal.svelte';
	import SectionEditorForm from '$lib/components/SectionEditorForm.svelte';

	let {
		heading,
		open,
		error = '',
		showCitation = true,
		showMixedEditWarning = false,
		switcherItems = [],
		currentSectionKey = undefined,
		switcherDisabled = false,
		onclose,
		onsave,
		children
	}: {
		heading: string;
		open: boolean;
		error?: string;
		showCitation?: boolean;
		showMixedEditWarning?: boolean;
		switcherItems?: EditSectionMenuItem[];
		currentSectionKey?: string;
		switcherDisabled?: boolean;
		onclose: () => void;
		onsave: (meta: SaveMeta) => void;
		children: Snippet;
	} = $props();

	let formRef: SectionEditorForm | undefined = $state();

	// Reset note/citation state when the modal opens
	$effect(() => {
		if (open) {
			formRef?.resetMeta();
		}
	});

	function close() {
		onclose();
	}
</script>

<Modal title={`Edit ${heading}`} {open} onclose={close}>
	{#snippet headerActions()}
		{#if switcherItems.length > 0}
			<EditSectionMenu
				items={switcherItems}
				currentKey={currentSectionKey}
				disabled={switcherDisabled}
			/>
		{/if}
	{/snippet}
	<SectionEditorForm
		bind:this={formRef}
		{error}
		{showCitation}
		{showMixedEditWarning}
		oncancel={close}
		{onsave}
	>
		{@render children()}
	</SectionEditorForm>
</Modal>
