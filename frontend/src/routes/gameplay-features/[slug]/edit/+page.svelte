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
	let profile = $derived(data.profile);

	// --- Form state ---

	// untrack: intentional one-time capture; re-synced explicitly after save
	let editFields = $state(untrack(() => hierarchyToFormFields(data.profile)));
	let selectedParents = $state<string[]>(
		untrack(() => (data.profile.parents ?? []).map((p: { slug: string }) => p.slug))
	);
	let editAliases = $state<string[]>(untrack(() => [...(data.profile.aliases ?? [])]));
	let editNote = $state('');
	let editCitation = $state<EditCitationSelection | null>(null);
	let pendingBody = $derived(
		buildHierarchyPatchBody(
			{
				fields: editFields,
				parents: selectedParents,
				aliases: editAliases
			},
			profile
		)
	);
	let showMixedEditWarning = $derived(
		shouldShowMixedEditCitationWarning(pendingBody, editCitation)
	);

	// --- Parent options (loaded async) ---

	let parentOptions = $state<{ slug: string; label: string; count: number }[]>([]);

	// Load once on mount; use untrack to avoid re-fetching after every save.
	$effect(() => {
		const slug = untrack(() => profile.slug);
		client.GET('/api/gameplay-features/').then(({ data: features }) => {
			if (features) {
				parentOptions = features
					.filter((f) => f.slug !== slug)
					.map((f) => ({ slug: f.slug, label: f.name, count: f.model_count }));
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

		const { data: updated, error } = await client.PATCH('/api/gameplay-features/{slug}/claims/', {
			params: { path: { slug: profile.slug } },
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
			placeholder="Search features..."
		/>
	</div>

	<TagInput
		label="Aliases"
		bind:tags={editAliases}
		placeholder="Type an alias and press Enter"
		optional
	/>
</EditFormShell>
