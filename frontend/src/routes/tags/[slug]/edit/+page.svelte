<script lang="ts">
	import { untrack } from 'svelte';
	import { invalidateAll } from '$app/navigation';
	import client from '$lib/api/client';
	import EditFormShell from '$lib/components/form/EditFormShell.svelte';
	import TextField from '$lib/components/form/TextField.svelte';
	import TextAreaField from '$lib/components/form/TextAreaField.svelte';
	import NumberField from '$lib/components/form/NumberField.svelte';

	let { data } = $props();
	let profile = $derived(data.profile);

	function toFormFields(p: typeof profile) {
		return {
			name: p.name,
			description: p.description?.text ?? '',
			display_order: p.display_order ?? ''
		};
	}

	// untrack: intentional one-time capture; re-synced explicitly after save
	let editFields = $state(untrack(() => toFormFields(data.profile)));

	let saveStatus = $state<'idle' | 'saving' | 'saved' | 'error'>('idle');
	let saveError = $state('');

	function getChangedFields(): Record<string, unknown> {
		const original = toFormFields(profile);
		const changed: Record<string, unknown> = {};
		for (const key of Object.keys(editFields) as (keyof typeof editFields)[]) {
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

		const { data: updated, error } = await client.PATCH('/api/tags/{slug}/claims/', {
			params: { path: { slug: profile.slug } },
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
	<NumberField label="Display Order" bind:value={editFields.display_order} />
</EditFormShell>
