<script lang="ts">
	import { untrack } from 'svelte';
	import { invalidateAll } from '$app/navigation';
	import client from '$lib/api/client';
	import EditFormShell from '$lib/components/form/EditFormShell.svelte';
	import TextField from '$lib/components/form/TextField.svelte';
	import TextAreaField from '$lib/components/form/TextAreaField.svelte';
	import NumberField from '$lib/components/form/NumberField.svelte';

	let { data } = $props();
	let mfr = $derived(data.manufacturer);

	function mfrToFormFields(m: typeof mfr) {
		return {
			name: m.name,
			description: m.description?.text ?? '',
			year_start: m.year_start ?? '',
			year_end: m.year_end ?? '',
			country: m.country ?? '',
			headquarters: m.headquarters ?? '',
			logo_url: m.logo_url ?? '',
			website: m.website ?? ''
		};
	}

	// untrack: intentional one-time capture; re-synced explicitly after save
	let editFields = $state(untrack(() => mfrToFormFields(data.manufacturer)));

	let saveStatus = $state<'idle' | 'saving' | 'saved' | 'error'>('idle');
	let saveError = $state('');

	function getChangedFields(): Record<string, unknown> {
		const original = mfrToFormFields(mfr);
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

		const { data: updated, error } = await client.PATCH('/api/manufacturers/{slug}/claims/', {
			params: { path: { slug: mfr.slug } },
			body: { fields }
		});

		if (updated) {
			editFields = mfrToFormFields(updated);
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
	<TextAreaField label="Description" bind:value={editFields.description} />

	<fieldset class="date-group">
		<legend>Years active</legend>
		<div class="date-row">
			<NumberField label="Founded" bind:value={editFields.year_start} min={1800} max={2100} />
			<NumberField label="Dissolved" bind:value={editFields.year_end} min={1800} max={2100} />
		</div>
	</fieldset>

	<TextField label="Country" bind:value={editFields.country} />
	<TextField label="Headquarters" bind:value={editFields.headquarters} />
	<TextField label="Website" bind:value={editFields.website} type="url" />
	<TextField label="Logo URL" bind:value={editFields.logo_url} type="url" />
</EditFormShell>

<style>
	.date-group {
		border: 1px solid var(--color-border-soft);
		border-radius: var(--radius-2);
		padding: var(--size-3);
		margin: 0;
	}

	.date-group legend {
		font-size: var(--font-size-1);
		font-weight: 500;
		color: var(--color-text-muted);
		padding: 0 var(--size-1);
	}

	.date-row {
		display: grid;
		grid-template-columns: 1fr 1fr;
		gap: var(--size-3);
	}
</style>
