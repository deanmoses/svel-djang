<script lang="ts">
	import { untrack } from 'svelte';
	import { goto, invalidateAll } from '$app/navigation';
	import client from '$lib/api/client';
	import {
		shouldShowMixedEditCitationWarning,
		type EditCitationSelection,
		withEditMetadata
	} from '$lib/edit-citation';
	import { diffScalarFields } from '$lib/edit-helpers';
	import { getEditRedirectHref } from '$lib/edit-routes';
	import EditFormShell from '$lib/components/form/EditFormShell.svelte';
	import TextField from '$lib/components/form/TextField.svelte';
	import MarkdownTextArea from '$lib/components/form/MarkdownTextArea.svelte';

	let { data } = $props();
	let franchise = $derived(data.franchise);

	function toFormFields(f: typeof franchise) {
		return {
			slug: f.slug,
			name: f.name,
			description: f.description?.text ?? ''
		};
	}

	// untrack: intentional one-time capture; re-synced explicitly after save
	let editFields = $state(untrack(() => toFormFields(data.franchise)));
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
		return diffScalarFields(editFields, toFormFields(franchise));
	}

	async function saveChanges() {
		const rawBody = pendingBody;
		if (!rawBody) return;

		saveStatus = 'saving';
		saveError = '';

		const { data: updated, error } = await client.PATCH('/api/franchises/{slug}/claims/', {
			params: { path: { slug: franchise.slug } },
			body: withEditMetadata(rawBody, editNote, editCitation)
		});

		if (updated) {
			const redirectHref = getEditRedirectHref('franchises', franchise.slug, updated.slug);
			editFields = toFormFields(updated);
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
</EditFormShell>
