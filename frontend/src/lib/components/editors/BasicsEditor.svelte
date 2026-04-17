<script lang="ts">
	import { untrack } from 'svelte';
	import SearchableSelect from '$lib/components/SearchableSelect.svelte';
	import TextField from '$lib/components/form/TextField.svelte';
	import NumberField from '$lib/components/form/NumberField.svelte';
	import MonthSelect from '$lib/components/form/MonthSelect.svelte';
	import TagInput from '$lib/components/form/TagInput.svelte';
	import { fetchFieldConstraints, fc, type FieldConstraints } from '$lib/field-constraints';
	import { diffScalarFields, stringSetChanged } from '$lib/edit-helpers';
	import type { SectionEditorProps } from './editor-contract';
	import {
		EMPTY_EDIT_OPTIONS,
		fetchModelEditOptions,
		type ModelEditOptions
	} from './model-edit-options';
	import {
		saveModelClaims,
		type FieldErrors,
		type SaveResult,
		type SaveMeta
	} from './save-model-claims';

	type BasicsModel = {
		name: string;
		slug: string;
		year?: number | null;
		month?: number | null;
		title?: { slug: string } | null;
		corporate_entity?: { slug: string } | null;
		abbreviations: string[];
	};

	let {
		initialData,
		slug,
		onsaved,
		onerror,
		ondirtychange = () => {}
	}: SectionEditorProps<BasicsModel> = $props();

	type BasicsFormFields = {
		name: string;
		slug: string;
		year: string | number;
		month: string | number;
		title: string;
		corporate_entity: string;
	};

	function extractFields(m: BasicsModel): BasicsFormFields {
		return {
			name: m.name,
			slug: m.slug,
			year: m.year ?? '',
			month: m.month ?? '',
			title: m.title?.slug ?? '',
			corporate_entity: m.corporate_entity?.slug ?? ''
		};
	}

	// untrack: intentional one-time capture; component re-mounts when modal reopens
	const original = untrack(() => extractFields(initialData));
	const originalAbbreviations = untrack(() => [...initialData.abbreviations]);
	let fields = $state<BasicsFormFields>({ ...original });
	let abbreviations = $state<string[]>(untrack(() => [...initialData.abbreviations]));
	let dirty = $derived.by(
		() =>
			Object.keys(diffScalarFields(fields, original)).length > 0 ||
			stringSetChanged(abbreviations, originalAbbreviations)
	);

	let fieldErrors = $state<FieldErrors>({});
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
		fieldErrors = {};
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
			fieldErrors = result.fieldErrors;
			onerror(
				Object.keys(result.fieldErrors).length > 0 ? 'Please fix the errors below.' : result.error
			);
		}
	}
</script>

<div class="basics-grid">
	<!--
		TODO: title is required (NOT NULL on MachineModel), but SearchableSelect's
		built-in ✕ button still lets users clear it locally. Saving triggers a
		backend 422 that renders inline, so the invariant holds — but the UX is
		"click clear, try to save, see error" instead of "can't clear at all".
		Follow-up: add a `required` prop to SearchableSelect that hides the ✕.
	-->
	<SearchableSelect
		label="Title"
		options={editOptions.titles ?? []}
		bind:selected={fields.title}
		error={fieldErrors.title ?? ''}
		showCounts={false}
		placeholder="Search titles..."
	/>
	<SearchableSelect
		label="Manufacturer"
		options={editOptions.corporate_entities ?? []}
		bind:selected={fields.corporate_entity}
		error={fieldErrors.corporate_entity ?? ''}
		allowZeroCount
		showCounts={false}
		placeholder="Search manufacturers..."
	/>
	<TextField label="Name" bind:value={fields.name} error={fieldErrors.name ?? ''} />
	<TextField label="Slug" bind:value={fields.slug} error={fieldErrors.slug ?? ''} />
	<NumberField
		label="Year"
		bind:value={fields.year}
		error={fieldErrors.year ?? ''}
		{...fc(constraints, 'year')}
	/>
	<MonthSelect label="Month" bind:value={fields.month} error={fieldErrors.month ?? ''} />
	<TagInput label="Abbreviations" bind:tags={abbreviations} placeholder="Type and press Enter" />
</div>

<style>
	.basics-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: var(--size-3);
	}
</style>
