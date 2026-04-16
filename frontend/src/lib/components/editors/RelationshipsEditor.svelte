<script lang="ts">
	import { untrack } from 'svelte';
	import SearchableSelect from '$lib/components/SearchableSelect.svelte';
	import { diffScalarFields } from '$lib/edit-helpers';
	import type { EditorDirtyChange } from './editor-contract';
	import {
		EMPTY_EDIT_OPTIONS,
		fetchModelEditOptions,
		type ModelEditOptions
	} from './model-edit-options';
	import { saveModelClaims, type SaveResult, type SaveMeta } from './save-model-claims';

	const HIERARCHY_FIELDS = [
		{ field: 'variant_of', label: 'Variant of' },
		{ field: 'converted_from', label: 'Converted from' },
		{ field: 'remake_of', label: 'Remake of' }
	] as const;

	type HierarchyRef = { slug: string; name?: string } | null | undefined;

	let {
		initialModel,
		slug,
		onsaved,
		onerror,
		ondirtychange = () => {}
	}: {
		initialModel: {
			title?: HierarchyRef;
			variant_of?: HierarchyRef;
			converted_from?: HierarchyRef;
			remake_of?: HierarchyRef;
		};
		slug: string;
		onsaved: () => void;
		onerror: (message: string) => void;
		ondirtychange?: EditorDirtyChange;
	} = $props();

	// Flatten nested FK objects to slug strings for form state
	const original = untrack(() => ({
		title: initialModel.title?.slug ?? '',
		variant_of: initialModel.variant_of?.slug ?? '',
		converted_from: initialModel.converted_from?.slug ?? '',
		remake_of: initialModel.remake_of?.slug ?? ''
	}));

	let fields = $state({ ...original });
	let dirty = $derived.by(() => Object.keys(diffScalarFields(fields, original)).length > 0);

	let editOptions = $state<ModelEditOptions>(EMPTY_EDIT_OPTIONS);

	let titleOptions = $derived(editOptions.titles ?? []);
	// Filter out the current model from the options list
	let modelOptions = $derived((editOptions.models ?? []).filter((o) => o.slug !== slug));

	$effect(() => {
		fetchModelEditOptions().then((opts) => {
			editOptions = opts;
		});
	});

	$effect(() => {
		ondirtychange(dirty);
	});

	export function isDirty(): boolean {
		return dirty;
	}

	export async function save(meta?: SaveMeta): Promise<void> {
		const changed = diffScalarFields(fields, original);

		if (!dirty) {
			onsaved();
			return;
		}

		const result: SaveResult = await saveModelClaims(slug, {
			fields: changed,
			...meta
		});

		if (result.ok) {
			onsaved();
		} else {
			onerror(result.error);
		}
	}
</script>

<div class="relationships-editor">
	<SearchableSelect
		label="Title"
		options={titleOptions}
		bind:selected={fields.title}
		allowZeroCount
		showCounts={false}
		placeholder="Search titles..."
	/>

	{#each HIERARCHY_FIELDS as { field, label } (field)}
		<SearchableSelect
			{label}
			options={modelOptions}
			bind:selected={fields[field]}
			allowZeroCount
			showCounts={false}
			placeholder="Search models..."
		/>
	{/each}
</div>

<style>
	.relationships-editor {
		display: flex;
		flex-direction: column;
		gap: var(--size-3);
	}
</style>
