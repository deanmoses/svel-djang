<script lang="ts">
	import { untrack } from 'svelte';
	import { goto, invalidateAll } from '$app/navigation';
	import client from '$lib/api/client';
	import {
		shouldShowMixedEditCitationWarning,
		type EditCitationSelection,
		withEditMetadata
	} from '$lib/edit-citation';
	import { getEditRedirectHref } from '$lib/edit-routes';
	import EditFormShell from '$lib/components/form/EditFormShell.svelte';
	import TextField from '$lib/components/form/TextField.svelte';
	import MarkdownTextArea from '$lib/components/form/MarkdownTextArea.svelte';
	import { buildManufacturerPatchBody, manufacturerToFormFields } from './manufacturer-edit';

	let { data } = $props();
	let mfr = $derived(data.manufacturer);

	// untrack: intentional one-time capture; re-synced explicitly after save
	let editFields = $state(untrack(() => manufacturerToFormFields(data.manufacturer)));
	let editNote = $state('');
	let editCitation = $state<EditCitationSelection | null>(null);
	let pendingBody = $derived(buildManufacturerPatchBody(editFields, mfr));
	let showMixedEditWarning = $derived(
		shouldShowMixedEditCitationWarning(pendingBody, editCitation)
	);

	let saveStatus = $state<'idle' | 'saving' | 'saved' | 'error'>('idle');
	let saveError = $state('');

	async function saveChanges() {
		const rawBody = pendingBody;
		if (!rawBody) return;
		const body = withEditMetadata(rawBody, editNote, editCitation);

		saveStatus = 'saving';
		saveError = '';

		const { data: updated, error } = await client.PATCH('/api/manufacturers/{slug}/claims/', {
			params: { path: { slug: mfr.slug } },
			body
		});

		if (updated) {
			const redirectHref = getEditRedirectHref('manufacturers', mfr.slug, updated.slug);
			editFields = manufacturerToFormFields(updated);
			editNote = '';
			editCitation = null;
			if (redirectHref) {
				await goto(redirectHref, { replaceState: true });
				return;
			}
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
	<TextField label="Slug" bind:value={editFields.slug} />
	<MarkdownTextArea label="Description" bind:value={editFields.description} />
	<TextField label="Website" bind:value={editFields.website} type="url" />
	<TextField label="Logo URL" bind:value={editFields.logo_url} type="url" />
</EditFormShell>
