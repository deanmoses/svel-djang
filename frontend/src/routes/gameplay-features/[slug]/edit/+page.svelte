<script lang="ts">
	import { untrack } from 'svelte';
	import { invalidateAll } from '$app/navigation';
	import client from '$lib/api/client';
	import SearchableSelect from '$lib/components/SearchableSelect.svelte';
	import EditFormShell from '$lib/components/form/EditFormShell.svelte';
	import TextField from '$lib/components/form/TextField.svelte';
	import TextAreaField from '$lib/components/form/TextAreaField.svelte';

	let { data } = $props();
	let profile = $derived(data.profile);

	// --- Form state ---

	function toFormFields(p: typeof profile) {
		return {
			name: p.name,
			description: p.description?.text ?? ''
		};
	}

	// untrack: intentional one-time capture; re-synced explicitly after save
	let editFields = $state(untrack(() => toFormFields(data.profile)));
	let selectedParents = $state<string[]>(
		untrack(() => (data.profile.parents ?? []).map((p: { slug: string }) => p.slug))
	);
	let editNote = $state('');

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

	// --- Change detection ---

	function getChangedScalarFields(): Record<string, unknown> {
		const original = toFormFields(profile);
		const changed: Record<string, unknown> = {};
		for (const key of Object.keys(editFields) as (keyof typeof editFields)[]) {
			if (String(editFields[key]) !== String(original[key])) {
				changed[key] = editFields[key] === '' ? null : editFields[key];
			}
		}
		return changed;
	}

	function parentsChanged(): boolean {
		const original = (profile.parents ?? []).map((p: { slug: string }) => p.slug).sort();
		const current = [...selectedParents].sort();
		return JSON.stringify(original) !== JSON.stringify(current);
	}

	// --- Save ---

	let saveStatus = $state<'idle' | 'saving' | 'saved' | 'error'>('idle');
	let saveError = $state('');

	async function saveChanges() {
		const fields = getChangedScalarFields();
		const hasFields = Object.keys(fields).length > 0;
		const hasParents = parentsChanged();

		if (!hasFields && !hasParents) return;

		saveStatus = 'saving';
		saveError = '';

		const { data: updated, error } = await client.PATCH('/api/gameplay-features/{slug}/claims/', {
			params: { path: { slug: profile.slug } },
			body: {
				fields: hasFields ? fields : {},
				parents: hasParents ? selectedParents : null,
				note: editNote.trim()
			}
		});

		if (updated) {
			editFields = toFormFields(updated);
			selectedParents = (updated.parents ?? []).map((p) => p.slug);
			editNote = '';
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
	<TextAreaField label="Description" bind:value={editFields.description} rows={6} />

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

	<TextField
		label="Edit note"
		bind:value={editNote}
		placeholder="Why are you making this change?"
		optional
	/>
</EditFormShell>
