<script lang="ts">
	import { untrack } from 'svelte';
	import { invalidateAll } from '$app/navigation';
	import client from '$lib/api/client';
	import {
		shouldShowMixedEditCitationWarning,
		type EditCitationSelection,
		withEditMetadata
	} from '$lib/edit-citation';
	import SearchableSelect from '$lib/components/SearchableSelect.svelte';
	import EditFormShell from '$lib/components/form/EditFormShell.svelte';
	import TagInput from '$lib/components/form/TagInput.svelte';
	import TextField from '$lib/components/form/TextField.svelte';
	import MarkdownTextArea from '$lib/components/form/MarkdownTextArea.svelte';
	import { buildHierarchyPatchBody, hierarchyToFormFields } from '$lib/hierarchy-edit';

	let { data } = $props();
	let theme = $derived(data.theme);

	// --- Form state ---

	let editFields = $state(untrack(() => hierarchyToFormFields(data.theme)));
	let selectedParents = $state<string[]>(
		untrack(() => (data.theme.parents ?? []).map((p: { slug: string }) => p.slug))
	);
	let editAliases = $state<string[]>(untrack(() => [...(data.theme.aliases ?? [])]));
	let editNote = $state('');
	let editCitation = $state<EditCitationSelection | null>(null);
	let pendingBody = $derived(
		buildHierarchyPatchBody(
			{
				fields: editFields,
				parents: selectedParents,
				aliases: editAliases
			},
			theme
		)
	);
	let showMixedEditWarning = $derived(
		shouldShowMixedEditCitationWarning(pendingBody, editCitation)
	);

	// --- Parent options (loaded async) ---

	let parentOptions = $state<{ slug: string; label: string; count: number }[]>([]);

	$effect(() => {
		const slug = untrack(() => theme.slug);
		client.GET('/api/themes/').then(({ data: themes }) => {
			if (themes) {
				parentOptions = themes
					.filter((t) => t.slug !== slug)
					.map((t) => ({ slug: t.slug, label: t.name, count: 0 }));
			}
		});
	});

	// --- Save ---

	let saveStatus = $state<'idle' | 'saving' | 'saved' | 'error'>('idle');
	let saveError = $state('');

	async function saveChanges() {
		const rawBody = pendingBody;
		if (!rawBody) return;
		const body = withEditMetadata(rawBody, editNote, editCitation);

		saveStatus = 'saving';
		saveError = '';

		const { data: updated, error } = await client.PATCH('/api/themes/{slug}/claims/', {
			params: { path: { slug: theme.slug } },
			body
		});

		if (updated) {
			editFields = hierarchyToFormFields(updated);
			selectedParents = (updated.parents ?? []).map((p) => p.slug);
			editAliases = [...(updated.aliases ?? [])];
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
	<MarkdownTextArea label="Description" bind:value={editFields.description} rows={6} />

	<div class="field-group">
		<SearchableSelect
			label="Parents"
			options={parentOptions}
			bind:selected={selectedParents}
			multi
			allowZeroCount
			placeholder="Search themes..."
		/>
	</div>

	<TagInput
		label="Aliases"
		bind:tags={editAliases}
		placeholder="Type an alias and press Enter"
		optional
	/>
</EditFormShell>
