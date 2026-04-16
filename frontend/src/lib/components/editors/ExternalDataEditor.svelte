<script lang="ts">
	import { untrack } from 'svelte';
	import Fieldset from '$lib/components/form/Fieldset.svelte';
	import NumberField from '$lib/components/form/NumberField.svelte';
	import TextField from '$lib/components/form/TextField.svelte';
	import { fetchFieldConstraints, fc, type FieldConstraints } from '$lib/field-constraints';
	import { diffScalarFields } from '$lib/edit-helpers';
	import type { EditorDirtyChange } from './editor-contract';
	import { saveModelClaims, type SaveResult, type SaveMeta } from './save-model-claims';

	type ExternalDataModel = {
		ipdb_id?: number | null;
		opdb_id?: string | null;
		pinside_id?: number | null;
		ipdb_rating?: number | null;
		pinside_rating?: number | null;
	};

	let {
		initialModel,
		slug,
		onsaved,
		onerror,
		ondirtychange = () => {}
	}: {
		initialModel: ExternalDataModel;
		slug: string;
		onsaved: () => void;
		onerror: (message: string) => void;
		ondirtychange?: EditorDirtyChange;
	} = $props();

	type ExternalDataFormFields = {
		ipdb_id: string | number;
		opdb_id: string;
		pinside_id: string | number;
		ipdb_rating: string | number;
		pinside_rating: string | number;
	};

	function extractFields(m: ExternalDataModel): ExternalDataFormFields {
		return {
			ipdb_id: m.ipdb_id ?? '',
			opdb_id: m.opdb_id ?? '',
			pinside_id: m.pinside_id ?? '',
			ipdb_rating: m.ipdb_rating ?? '',
			pinside_rating: m.pinside_rating ?? ''
		};
	}

	// untrack: intentional one-time capture; component re-mounts when modal reopens
	const original = untrack(() => extractFields(initialModel));
	let fields = $state<ExternalDataFormFields>({ ...original });
	let dirty = $derived.by(() => Object.keys(diffScalarFields(fields, original)).length > 0);

	let constraints = $state<FieldConstraints>({});

	$effect(() => {
		fetchFieldConstraints('model').then((c) => {
			constraints = c;
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

<div class="external-data-editor">
	<Fieldset legend="External Links">
		<div class="fields-grid">
			<NumberField label="IPDB ID" bind:value={fields.ipdb_id} {...fc(constraints, 'ipdb_id')} />
			<TextField label="OPDB ID" bind:value={fields.opdb_id} />
			<NumberField
				label="Pinside ID"
				bind:value={fields.pinside_id}
				{...fc(constraints, 'pinside_id')}
			/>
		</div>
	</Fieldset>

	<Fieldset legend="Ratings">
		<div class="fields-grid">
			<NumberField
				label="IPDB rating"
				bind:value={fields.ipdb_rating}
				{...fc(constraints, 'ipdb_rating')}
			/>
			<NumberField
				label="Pinside rating"
				bind:value={fields.pinside_rating}
				{...fc(constraints, 'pinside_rating')}
			/>
		</div>
	</Fieldset>
</div>

<style>
	.external-data-editor {
		display: flex;
		flex-direction: column;
		gap: var(--size-3);
	}

	.fields-grid {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: var(--size-3);
	}
</style>
