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
	import NumberField from '$lib/components/form/NumberField.svelte';
	import MonthSelect from '$lib/components/form/MonthSelect.svelte';
	import { fetchFieldConstraints, fc, type FieldConstraints } from '$lib/field-constraints';
	import { buildPersonPatchBody, personToFormFields } from './person-edit';

	let { data } = $props();
	let person = $derived(data.person);

	// untrack: intentional one-time capture; re-synced explicitly after save
	let editFields = $state(untrack(() => personToFormFields(data.person)));
	let editNote = $state('');
	let editCitation = $state<EditCitationSelection | null>(null);
	let pendingBody = $derived(buildPersonPatchBody(editFields, person));
	let showMixedEditWarning = $derived(
		shouldShowMixedEditCitationWarning(pendingBody, editCitation)
	);

	let constraints = $state<FieldConstraints>({});

	$effect(() => {
		fetchFieldConstraints('person').then((c) => {
			constraints = c;
		});
	});

	let saveStatus = $state<'idle' | 'saving' | 'saved' | 'error'>('idle');
	let saveError = $state('');

	async function saveChanges() {
		const rawBody = pendingBody;
		if (!rawBody) return;
		const body = withEditMetadata(rawBody, editNote, editCitation);

		saveStatus = 'saving';
		saveError = '';

		const { data: updated, error } = await client.PATCH('/api/people/{slug}/claims/', {
			params: { path: { slug: person.slug } },
			body
		});

		if (updated) {
			const redirectHref = getEditRedirectHref('people', person.slug, updated.slug);
			editFields = personToFormFields(updated);
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
	<TextField label="Nationality" bind:value={editFields.nationality} />

	<fieldset class="date-group">
		<legend>Born</legend>
		<div class="date-row">
			<NumberField
				label="Year"
				bind:value={editFields.birth_year}
				{...fc(constraints, 'birth_year')}
			/>
			<MonthSelect label="Month" bind:value={editFields.birth_month} />
			<NumberField
				label="Day"
				bind:value={editFields.birth_day}
				{...fc(constraints, 'birth_day')}
			/>
		</div>
	</fieldset>

	<TextField label="Birth place" bind:value={editFields.birth_place} />

	<fieldset class="date-group">
		<legend>Died</legend>
		<div class="date-row">
			<NumberField
				label="Year"
				bind:value={editFields.death_year}
				{...fc(constraints, 'death_year')}
			/>
			<MonthSelect label="Month" bind:value={editFields.death_month} />
			<NumberField
				label="Day"
				bind:value={editFields.death_day}
				{...fc(constraints, 'death_day')}
			/>
		</div>
	</fieldset>

	<TextField label="Photo URL" bind:value={editFields.photo_url} type="url" />
	<MarkdownTextArea label="Bio" bind:value={editFields.description} rows={8} />
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
