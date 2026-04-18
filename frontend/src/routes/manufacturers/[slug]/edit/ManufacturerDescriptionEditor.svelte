<script lang="ts">
	import { untrack } from 'svelte';
	import MarkdownTextArea from '$lib/components/form/MarkdownTextArea.svelte';
	import type { SectionEditorProps } from '$lib/components/editors/editor-contract';
	import type { ManufacturerEditView } from './manufacturer-edit-types';
	import {
		saveManufacturerClaims,
		type FieldErrors,
		type SaveMeta,
		type SaveResult
	} from './save-manufacturer-claims';

	let {
		initialData,
		slug,
		onsaved,
		onerror,
		ondirtychange = () => {}
	}: SectionEditorProps<ManufacturerEditView> = $props();

	const original = untrack(() => initialData.description?.text ?? '');
	let description = $state(original);
	let fieldErrors = $state<FieldErrors>({});
	let dirty = $derived(description !== original);

	$effect(() => {
		ondirtychange(dirty);
	});

	export function isDirty(): boolean {
		return dirty;
	}

	export async function save(meta?: SaveMeta): Promise<void> {
		fieldErrors = {};
		if (!dirty) {
			onsaved();
			return;
		}

		const result: SaveResult = await saveManufacturerClaims(slug, {
			fields: { description },
			...meta
		});

		if (result.ok) {
			onsaved();
		} else {
			fieldErrors = result.fieldErrors;
			onerror(
				Object.keys(result.fieldErrors).length > 0 ? 'Please fix the errors below.' : result.error
			);
		}
	}
</script>

<div class="editor-fields">
	<MarkdownTextArea
		label="Description"
		bind:value={description}
		rows={8}
		error={fieldErrors.description ?? ''}
	/>
</div>

<style>
	.editor-fields {
		display: flex;
		flex-direction: column;
		gap: var(--size-3);
	}
</style>
