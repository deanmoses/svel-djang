<script lang="ts">
	import { untrack } from 'svelte';
	import { invalidateAll } from '$app/navigation';
	import client from '$lib/api/client';
	import EditFormShell from '$lib/components/form/EditFormShell.svelte';
	import TextField from '$lib/components/form/TextField.svelte';
	import TextAreaField from '$lib/components/form/TextAreaField.svelte';

	let { data } = $props();
	let series = $derived(data.series);

	function toFormFields(s: typeof series) {
		return {
			name: s.name,
			description: s.description?.text ?? ''
		};
	}

	// untrack: intentional one-time capture; re-synced explicitly after save
	let editFields = $state(untrack(() => toFormFields(data.series)));

	let saveStatus = $state<'idle' | 'saving' | 'saved' | 'error'>('idle');
	let saveError = $state('');

	function getChangedFields(): Record<string, unknown> {
		const original = toFormFields(series);
		const changed: Record<string, unknown> = {};
		for (const key of Object.keys(editFields) as (keyof typeof editFields)[]) {
			if (String(editFields[key]) !== String(original[key])) {
				changed[key] = editFields[key] === '' ? null : editFields[key];
			}
		}
		return changed;
	}

	async function saveChanges() {
		const fields = getChangedFields();
		if (Object.keys(fields).length === 0) return;

		saveStatus = 'saving';
		saveError = '';

		const { data: updated, error } = await client.PATCH('/api/series/{slug}/claims/', {
			params: { path: { slug: series.slug } },
			body: { fields }
		});

		if (updated) {
			editFields = toFormFields(updated);
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
</EditFormShell>
