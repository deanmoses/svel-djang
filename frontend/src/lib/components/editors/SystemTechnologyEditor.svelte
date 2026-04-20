<script lang="ts">
	import { untrack } from 'svelte';
	import SearchableSelect from '$lib/components/SearchableSelect.svelte';
	import { diffScalarFields } from '$lib/edit-helpers';
	import type { SectionEditorProps } from './editor-contract';
	import type { FieldErrors, SaveMeta, SaveResult } from './save-claims-shared';
	import {
		fetchTechnologySubgenerationOptions,
		type SystemEditOption
	} from './system-edit-options';

	type TechnologyFields = {
		technology_subgeneration: string;
	};

	type SaveFn = (
		slug: string,
		body: { fields: Partial<TechnologyFields> } & SaveMeta
	) => Promise<SaveResult>;

	type InitialData = {
		technology_subgeneration?: { slug: string } | null;
	};

	let {
		initialData,
		slug,
		save: saveFn,
		onsaved,
		onerror,
		ondirtychange = () => {}
	}: SectionEditorProps<InitialData> & { save: SaveFn } = $props();

	const original = untrack(() => ({
		technology_subgeneration: initialData.technology_subgeneration?.slug ?? ''
	}));
	let fields = $state<TechnologyFields>({ ...original });
	let fieldErrors = $state<FieldErrors>({});
	let options = $state<SystemEditOption[]>([]);
	let dirty = $derived(Object.keys(diffScalarFields(fields, original)).length > 0);

	$effect(() => {
		fetchTechnologySubgenerationOptions().then((opts) => (options = opts));
	});

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

		const changed = diffScalarFields(fields, original);
		const result = await saveFn(slug, { fields: changed, ...meta });

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

<SearchableSelect
	label="Technology subgeneration"
	{options}
	bind:selected={fields.technology_subgeneration}
	error={fieldErrors.technology_subgeneration ?? ''}
	allowZeroCount
	showCounts={false}
	placeholder="Select technology subgeneration..."
/>
