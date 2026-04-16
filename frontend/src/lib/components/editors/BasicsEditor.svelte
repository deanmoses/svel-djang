<script lang="ts">
	import { untrack } from 'svelte';
	import SearchableSelect from '$lib/components/SearchableSelect.svelte';
	import TextField from '$lib/components/form/TextField.svelte';
	import NumberField from '$lib/components/form/NumberField.svelte';
	import MonthSelect from '$lib/components/form/MonthSelect.svelte';
	import TagInput from '$lib/components/form/TagInput.svelte';
	import { fetchFieldConstraints, fc, type FieldConstraints } from '$lib/field-constraints';
	import { diffScalarFields, stringSetChanged } from '$lib/edit-helpers';
	import type { EditorDirtyChange } from './editor-contract';
	import {
		EMPTY_EDIT_OPTIONS,
		fetchModelEditOptions,
		type ModelEditOptions
	} from './model-edit-options';
	import { saveModelClaims, type SaveResult, type SaveMeta } from './save-model-claims';

	type BasicsModel = {
		name: string;
		slug: string;
		year?: number | null;
		month?: number | null;
		corporate_entity?: { slug: string } | null;
		abbreviations: string[];
	};

	let {
		initialModel,
		slug,
		onsaved,
		onerror,
		ondirtychange = () => {}
	}: {
		initialModel: BasicsModel;
		slug: string;
		onsaved: () => void;
		onerror: (message: string) => void;
		ondirtychange?: EditorDirtyChange;
	} = $props();

	type BasicsFormFields = {
		name: string;
		slug: string;
		year: string | number;
		month: string | number;
		corporate_entity: string;
	};

	function extractFields(m: BasicsModel): BasicsFormFields {
		return {
			name: m.name,
			slug: m.slug,
			year: m.year ?? '',
			month: m.month ?? '',
			corporate_entity: m.corporate_entity?.slug ?? ''
		};
	}

	// untrack: intentional one-time capture; component re-mounts when modal reopens
	const original = untrack(() => extractFields(initialModel));
	const originalAbbreviations = untrack(() => [...initialModel.abbreviations]);
	let fields = $state<BasicsFormFields>({ ...original });
	let abbreviations = $state<string[]>(untrack(() => [...initialModel.abbreviations]));
	let dirty = $derived.by(
		() =>
			Object.keys(diffScalarFields(fields, original)).length > 0 ||
			stringSetChanged(abbreviations, originalAbbreviations)
	);

	let editOptions = $state<ModelEditOptions>(EMPTY_EDIT_OPTIONS);
	let constraints = $state<FieldConstraints>({});

	$effect(() => {
		fetchFieldConstraints('model').then((c) => {
			constraints = c;
		});
	});

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
		const abbrevsChanged = stringSetChanged(abbreviations, originalAbbreviations);

		if (!dirty) {
			onsaved();
			return;
		}

		const result: SaveResult = await saveModelClaims(slug, {
			fields: Object.keys(changed).length > 0 ? changed : undefined,
			abbreviations: abbrevsChanged ? abbreviations : undefined,
			...meta
		});

		if (result.ok) {
			onsaved();
		} else {
			onerror(result.error);
		}
	}
</script>

<div class="basics-grid">
	<TextField label="Name" bind:value={fields.name} />
	<TextField label="Slug" bind:value={fields.slug} />
	<NumberField label="Year" bind:value={fields.year} {...fc(constraints, 'year')} />
	<MonthSelect label="Month" bind:value={fields.month} />
	<SearchableSelect
		label="Manufacturer"
		options={editOptions.corporate_entities ?? []}
		bind:selected={fields.corporate_entity}
		allowZeroCount
		showCounts={false}
		placeholder="Search manufacturers..."
	/>
	<TagInput label="Abbreviations" bind:tags={abbreviations} placeholder="Type and press Enter" />
</div>

<style>
	.basics-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: var(--size-3);
	}
</style>
