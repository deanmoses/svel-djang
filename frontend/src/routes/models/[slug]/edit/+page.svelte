<script lang="ts">
	import { untrack } from 'svelte';
	import { invalidateAll } from '$app/navigation';
	import client from '$lib/api/client';
	import EditFormShell from '$lib/components/form/EditFormShell.svelte';
	import TextField from '$lib/components/form/TextField.svelte';
	import NumberField from '$lib/components/form/NumberField.svelte';
	import MonthSelect from '$lib/components/form/MonthSelect.svelte';

	let { data } = $props();
	let model = $derived(data.model);

	function modelToFormFields(m: typeof model) {
		return {
			name: m.name,
			year: m.year ?? '',
			month: m.month ?? '',
			player_count: m.player_count ?? '',
			flipper_count: m.flipper_count ?? '',
			production_quantity: m.production_quantity,
			ipdb_id: m.ipdb_id ?? '',
			opdb_id: m.opdb_id ?? '',
			pinside_id: m.pinside_id ?? '',
			ipdb_rating: m.ipdb_rating ?? '',
			pinside_rating: m.pinside_rating ?? ''
		};
	}

	// untrack: intentional one-time capture; re-synced explicitly after save
	let editFields = $state(untrack(() => modelToFormFields(data.model)));

	let saveStatus = $state<'idle' | 'saving' | 'saved' | 'error'>('idle');
	let saveError = $state('');

	function getChangedFields(): Record<string, unknown> {
		const original = modelToFormFields(model);
		const changed: Record<string, unknown> = {};
		for (const key of Object.keys(editFields) as (keyof typeof editFields)[]) {
			// Number inputs return NaN when cleared; treat as empty
			let val: unknown = editFields[key];
			if (typeof val === 'number' && isNaN(val)) val = '';
			if (String(val) !== String(original[key])) {
				changed[key] = val === '' ? null : val;
			}
		}
		return changed;
	}

	async function saveChanges() {
		const fields = getChangedFields();
		if (Object.keys(fields).length === 0) return;

		saveStatus = 'saving';
		saveError = '';

		const { data: updated, error } = await client.PATCH('/api/models/{slug}/claims/', {
			params: { path: { slug: model.slug } },
			body: { fields }
		});

		if (updated) {
			editFields = modelToFormFields(updated);
			await invalidateAll();
			saveStatus = 'saved';
			setTimeout(() => (saveStatus = 'idle'), 3000);
		} else {
			saveStatus = 'error';
			saveError = error ? JSON.stringify(error) : 'Save failed.';
		}
	}
</script>

<EditFormShell {saveStatus} {saveError} onsave={saveChanges}>
	<TextField label="Name" bind:value={editFields.name} />

	<fieldset class="date-group">
		<legend>Date</legend>
		<div class="date-row">
			<NumberField label="Year" bind:value={editFields.year} min={1800} max={2100} />
			<MonthSelect label="Month" bind:value={editFields.month} />
		</div>
	</fieldset>

	<div class="row-2">
		<NumberField label="Players" bind:value={editFields.player_count} min={1} max={8} />
		<NumberField label="Flippers" bind:value={editFields.flipper_count} min={0} max={10} />
	</div>

	<NumberField label="Production quantity" bind:value={editFields.production_quantity} min={0} />

	<fieldset class="xref-group">
		<legend>Cross-reference IDs</legend>
		<div class="row-3">
			<NumberField label="IPDB ID" bind:value={editFields.ipdb_id} min={1} />
			<TextField label="OPDB ID" bind:value={editFields.opdb_id} />
			<NumberField label="Pinside ID" bind:value={editFields.pinside_id} min={1} />
		</div>
	</fieldset>

	<fieldset class="ratings-group">
		<legend>Ratings</legend>
		<div class="row-2">
			<NumberField
				label="IPDB rating"
				bind:value={editFields.ipdb_rating}
				min={0}
				max={10}
				step={0.01}
			/>
			<NumberField
				label="Pinside rating"
				bind:value={editFields.pinside_rating}
				min={0}
				max={10}
				step={0.01}
			/>
		</div>
	</fieldset>
</EditFormShell>

<style>
	.date-group,
	.xref-group,
	.ratings-group {
		border: 1px solid var(--color-border-soft);
		border-radius: var(--radius-2);
		padding: var(--size-3);
		margin: 0;
	}

	.date-group legend,
	.xref-group legend,
	.ratings-group legend {
		font-size: var(--font-size-1);
		font-weight: 500;
		color: var(--color-text-muted);
		padding: 0 var(--size-1);
	}

	.date-row,
	.row-2 {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: var(--size-3);
	}

	.row-3 {
		display: grid;
		grid-template-columns: 1fr 1fr 1fr;
		gap: var(--size-3);
	}
</style>
