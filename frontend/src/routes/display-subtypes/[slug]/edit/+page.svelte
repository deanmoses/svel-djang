<script lang="ts">
	import { untrack } from 'svelte';
	import { invalidateAll } from '$app/navigation';
	import client from '$lib/api/client';
	import {
		shouldShowMixedEditCitationWarning,
		type EditCitationSelection,
		withEditMetadata
	} from '$lib/edit-citation';
	import EditFormShell from '$lib/components/form/EditFormShell.svelte';
	import TextField from '$lib/components/form/TextField.svelte';
	import MarkdownTextArea from '$lib/components/form/MarkdownTextArea.svelte';
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
	let editNote = $state('');
	let editCitation = $state<EditCitationSelection | null>(null);
	let pendingBody = $derived.by(() => {
		const fields = getChangedFields();
		return Object.keys(fields).length > 0 ? { fields } : null;
	});
	let showMixedEditWarning = $derived(
		shouldShowMixedEditCitationWarning(pendingBody, editCitation)
	);

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
		const rawBody = pendingBody;
		if (!rawBody) return;

		saveStatus = 'saving';
		saveError = '';

		const { data: updated, error } = await client.PATCH('/api/display-subtypes/{slug}/claims/', {
			params: { path: { slug: profile.slug } },
			body: withEditMetadata(rawBody, editNote, editCitation)
		});

		if (updated) {
			editFields = toFormFields(updated);
			editNote = '';
			editCitation = null;
			await invalidateAll();
			saveStatus = 'saved';
			setTimeout(() => (saveStatus = 'idle'), 3000);
		} else {
			saveStatus = 'error';
			saveError = error ? JSON.stringify(error) : 'Save failed.';
		}
	}
</script>

<EditFormShell
	{saveStatus}
	{saveError}
	onsave={saveChanges}
	bind:note={editNote}
	bind:citation={editCitation}
	{showMixedEditWarning}
>
	<TextField label="Name" bind:value={editFields.name} />
	<MarkdownTextArea label="Description" bind:value={editFields.description} />
	<NumberField label="Display Order" bind:value={editFields.display_order} />
</EditFormShell>
