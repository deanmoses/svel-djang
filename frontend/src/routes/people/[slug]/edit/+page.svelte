<script lang="ts">
	import { untrack } from 'svelte';
	import { invalidateAll } from '$app/navigation';
	import client from '$lib/api/client';
	import EditFormShell from '$lib/components/form/EditFormShell.svelte';
	import TextField from '$lib/components/form/TextField.svelte';
	import TextAreaField from '$lib/components/form/TextAreaField.svelte';
	import NumberField from '$lib/components/form/NumberField.svelte';
	import MonthSelect from '$lib/components/form/MonthSelect.svelte';

	let { data } = $props();
	let person = $derived(data.person);

	function personToFormFields(p: typeof person) {
		return {
			name: p.name,
			description: p.description?.text ?? '',
			nationality: p.nationality ?? '',
			birth_year: p.birth_year ?? '',
			birth_month: p.birth_month ?? '',
			birth_day: p.birth_day ?? '',
			death_year: p.death_year ?? '',
			death_month: p.death_month ?? '',
			death_day: p.death_day ?? '',
			birth_place: p.birth_place ?? '',
			photo_url: p.photo_url ?? ''
		};
	}

	// untrack: intentional one-time capture; re-synced explicitly after save
	let editFields = $state(untrack(() => personToFormFields(data.person)));

	let saveStatus = $state<'idle' | 'saving' | 'saved' | 'error'>('idle');
	let saveError = $state('');

	function getChangedFields(): Record<string, unknown> {
		const original = personToFormFields(person);
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

		const { data: updated, error } = await client.PATCH('/api/people/{slug}/claims/', {
			params: { path: { slug: person.slug } },
			body: { fields }
		});

		if (updated) {
			editFields = personToFormFields(updated);
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
	<TextField label="Nationality" bind:value={editFields.nationality} />

	<fieldset class="date-group">
		<legend>Born</legend>
		<div class="date-row">
			<NumberField label="Year" bind:value={editFields.birth_year} min={1800} max={2100} />
			<MonthSelect label="Month" bind:value={editFields.birth_month} />
			<NumberField label="Day" bind:value={editFields.birth_day} min={1} max={31} />
		</div>
	</fieldset>

	<TextField label="Birth place" bind:value={editFields.birth_place} />

	<fieldset class="date-group">
		<legend>Died</legend>
		<div class="date-row">
			<NumberField label="Year" bind:value={editFields.death_year} min={1800} max={2100} />
			<MonthSelect label="Month" bind:value={editFields.death_month} />
			<NumberField label="Day" bind:value={editFields.death_day} min={1} max={31} />
		</div>
	</fieldset>

	<TextField label="Photo URL" bind:value={editFields.photo_url} type="url" />
	<TextAreaField label="Bio" bind:value={editFields.description} rows={8} />
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
		grid-template-columns: 1fr 1fr 1fr;
		gap: var(--size-3);
	}
</style>
