<script lang="ts">
	import { untrack } from 'svelte';
	import SearchableSelect from '$lib/components/SearchableSelect.svelte';
	import TextField from '$lib/components/form/TextField.svelte';
	import TagInput from '$lib/components/form/TagInput.svelte';
	import { diffScalarFields, stringSetChanged } from '$lib/edit-helpers';
	import type { SectionEditorProps } from './editor-contract';
	import { type FieldErrors, type SaveResult, type SaveMeta } from './save-claims-shared';
	import { saveTitleClaims } from './save-title-claims';
	import {
		fetchFranchiseOptions,
		fetchSeriesOptions,
		type TitleEditOption
	} from './title-edit-options';

	type BasicsTitle = {
		name: string;
		slug: string;
		franchise?: { slug: string } | null;
		series?: { slug: string } | null;
		abbreviations: string[];
	};

	let {
		initialData,
		slug,
		onsaved,
		onerror,
		ondirtychange = () => {}
	}: SectionEditorProps<BasicsTitle> = $props();

	type BasicsFormFields = {
		name: string;
		slug: string;
		franchise: string;
		series: string;
	};

	function extractFields(t: BasicsTitle): BasicsFormFields {
		return {
			name: t.name,
			slug: t.slug,
			franchise: t.franchise?.slug ?? '',
			series: t.series?.slug ?? ''
		};
	}

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

	let franchiseOptions = $state<TitleEditOption[]>([]);
	let seriesOptions = $state<TitleEditOption[]>([]);

	$effect(() => {
		fetchFranchiseOptions().then((opts) => (franchiseOptions = opts));
	});

	$effect(() => {
		fetchSeriesOptions().then((opts) => (seriesOptions = opts));
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

		const result: SaveResult = await saveTitleClaims(slug, {
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
	<TextField label="Name" bind:value={fields.name} error={fieldErrors.name ?? ''} />
	<TextField label="Slug" bind:value={fields.slug} error={fieldErrors.slug ?? ''} />
	<SearchableSelect
		label="Franchise"
		options={franchiseOptions}
		bind:selected={fields.franchise}
		error={fieldErrors.franchise ?? ''}
		allowZeroCount
		placeholder="Search franchises..."
	/>
	<SearchableSelect
		label="Series"
		options={seriesOptions}
		bind:selected={fields.series}
		error={fieldErrors.series ?? ''}
		allowZeroCount
		placeholder="Search series..."
	/>
	<div class="full-row">
		<TagInput label="Abbreviations" bind:tags={abbreviations} placeholder="Type and press Enter" />
	</div>
</div>

<style>
	.basics-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: var(--size-3);
	}

	.full-row {
		grid-column: 1 / -1;
	}
</style>
