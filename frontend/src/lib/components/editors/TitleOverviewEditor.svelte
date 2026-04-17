<script lang="ts">
	import { untrack } from 'svelte';
	import MarkdownTextArea from '$lib/components/form/MarkdownTextArea.svelte';
	import type { SectionEditorProps } from './editor-contract';
	import { type FieldErrors, type SaveResult, type SaveMeta } from './save-claims-shared';
	import { saveTitleClaims } from './save-title-claims';

	let {
		initialData,
		slug,
		onsaved,
		onerror,
		ondirtychange = () => {}
	}: SectionEditorProps<string> = $props();

	let fieldErrors = $state<FieldErrors>({});

	const original = untrack(() => initialData);
	let description = $state(original);
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

		const result: SaveResult = await saveTitleClaims(slug, {
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

<div class="overview-editor">
	<MarkdownTextArea
		label="Description"
		bind:value={description}
		rows={8}
		error={fieldErrors.description ?? ''}
	/>
</div>

<style>
	.overview-editor {
		display: flex;
		flex-direction: column;
		gap: var(--size-3);
	}
</style>
